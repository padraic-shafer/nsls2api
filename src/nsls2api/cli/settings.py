import configparser
import os
import shutil
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any


class ApiEnvironment(str, Enum):
    PRODUCTION = "https://api.nsls2.bnl.gov"
    DEVELOPMENT = "https://api-dev.nsls2.bnl.gov"
    LOCAL = "http://127.0.0.1:8000"


class ConfigKey(str, Enum):
    """Enum for configuration keys to ensure consistency"""

    BASE_URL = "base_url"
    TOKEN = "token"


class Config:
    """Centralized configuration management"""

    @staticmethod
    def get_filepath() -> Path:
        """Get the configuration file path ($XDG_CONFIG_HOME/nsls2/api/cli.ini).

        Respects XDG_CONFIG_HOME if set; falls back to ~/.config on POSIX and
        %APPDATA% on Windows.
        """
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "")
            base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        else:
            xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
            base = Path(xdg) if xdg else Path.home() / ".config"
        return base / "nsls2" / "api" / "cli.ini"

    @staticmethod
    def _legacy_filepath() -> Path:
        """Returns the old (pre-migration) config path: ~/.config/nsls2 (a bare file)."""
        return Path.home() / ".config" / "nsls2"

    @classmethod
    def migrate_legacy_config(cls) -> Path | None:
        """Migrate the legacy bare-file config to the new location, if applicable.

        If ``~/.config/nsls2`` exists as a **regular file** (the old format) and
        the new config file does not yet exist, move the legacy file to the new
        location, creating intermediate directories as needed.

        Because the legacy file occupies the same name (``nsls2``) that must
        become a *directory* for the new path, migration stages the legacy file
        to a temporary sibling location first (via :func:`tempfile.mkstemp`) to
        free the name before calling ``mkdir``.

        Returns the new path if migration occurred, ``None`` otherwise.

        Emits a warning to stderr and returns ``None`` (without raising) if the
        move fails for any reason (e.g. permissions), so a migration failure
        never breaks a normal CLI command.
        """
        legacy = cls._legacy_filepath()
        new = cls.get_filepath()

        # Already migrated (or user already has a new-style config) — nothing to do.
        if new.exists():
            return None

        # Only migrate a plain FILE.  If legacy is a directory, skip silently.
        if not legacy.is_file():
            return None

        # Check writability before attempting the move.
        if not os.access(legacy, os.W_OK):
            print(
                f"Warning: nsls2api config migration skipped — "
                f"'{legacy}' is not writable. "
                f"To migrate manually:\n"
                f"  1. Move '{legacy}' aside (e.g. rename it to '{legacy}.bak')\n"
                f"  2. Create the directory '{new.parent}'\n"
                f"  3. Move the saved file into place as '{new}'",
                file=sys.stderr,
            )
            return None

        # Stage the legacy file to a temp sibling so the 'nsls2' name is freed
        # before we try to create a directory with that same name.
        fd, tmp_name = tempfile.mkstemp(dir=legacy.parent, prefix=".nsls2-migrate-")
        os.close(fd)
        tmp = Path(tmp_name)
        staged = False  # True once legacy.replace(tmp) succeeds and tmp holds the data
        try:
            legacy.replace(tmp)                             # free the 'nsls2' name
            staged = True
            new.parent.mkdir(parents=True, exist_ok=True)  # 'nsls2' can now be a dir
            shutil.move(str(tmp), str(new))                 # cross-device safe final move
        except OSError as exc:
            if not staged:
                # Staging step failed — legacy is still intact; discard empty temp file.
                tmp.unlink(missing_ok=True)
                print(
                    f"Warning: nsls2api config migration failed ({exc}). "
                    f"Your settings remain at '{legacy}'. "
                    f"To migrate manually:\n"
                    f"  1. Move '{legacy}' aside (e.g. rename it to '{legacy}.bak')\n"
                    f"  2. Create the directory '{new.parent}'\n"
                    f"  3. Move the saved file into place as '{new}'",
                    file=sys.stderr,
                )
            else:
                # Staging succeeded (tmp holds the data); a later step failed.
                # new.parent.mkdir() may have created ~/.config/nsls2/api/ and
                # ~/.config/nsls2/ (which occupies the legacy name as a directory).
                # Remove those empty dirs so the legacy name is free to receive the
                # file again.  rmtree is limited to new.parent (the api/ subtree);
                # legacy.rmdir() only succeeds when the dir is empty — if it
                # unexpectedly holds other content it raises and we fall through
                # to the "settings at tmp" message, never deleting real data.
                restored = False
                try:
                    if new.parent.is_dir():
                        shutil.rmtree(new.parent, ignore_errors=True)  # …/nsls2/api
                    if legacy.is_dir():
                        legacy.rmdir()                                  # empty …/nsls2
                    tmp.replace(legacy)
                    restored = True
                except OSError:
                    pass
                if restored:
                    print(
                        f"Warning: nsls2api config migration failed ({exc}). "
                        f"Your settings remain at '{legacy}'. "
                        f"To migrate manually:\n"
                        f"  1. Move '{legacy}' aside (e.g. rename it to '{legacy}.bak')\n"
                        f"  2. Create the directory '{new.parent}'\n"
                        f"  3. Move the saved file into place as '{new}'",
                        file=sys.stderr,
                    )
                else:
                    # Rollback also failed — settings are at the temp path.
                    print(
                        f"Warning: nsls2api config migration failed ({exc}) and "
                        f"could not be rolled back. "
                        f"Your settings are at '{tmp}'. "
                        f"To recover:\n"
                        f"  1. Create the directory '{new.parent}'\n"
                        f"  2. Move '{tmp}' into place as '{new}'",
                        file=sys.stderr,
                    )
            return None

        return new

    @classmethod
    def read(cls) -> configparser.ConfigParser:
        """Read the configuration file, migrating legacy config if present.

        If migration was skipped or failed and the new config file does not yet
        exist, fall back to reading the legacy bare file so existing settings
        (base_url, token) are not silently dropped.
        """
        cls.migrate_legacy_config()
        config = configparser.ConfigParser()
        new = cls.get_filepath()
        if new.exists():
            config.read(new)
        else:
            legacy = cls._legacy_filepath()
            if legacy.is_file():
                config.read(legacy)  # back-compat: unmigrated settings still honored
        return config

    @classmethod
    def get_value(cls, section: str, key: str) -> str | None:
        """Get a value from the configuration"""
        try:
            config = cls.read()
            return config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None

    @classmethod
    def set_value(cls, section: str, key: str, value: Any) -> None:
        """Set a value in the configuration"""
        config = cls.read()

        if section not in config:
            config[section] = {}

        config[section][key] = str(value)

        # Create the directory if it doesn't exist
        config_filepath = cls.get_filepath()
        os.makedirs(config_filepath.parent, exist_ok=True)

        with open(config_filepath, "w") as config_file:
            config.write(config_file)

    @classmethod
    def remove_value(cls, section: str, key: str) -> None:
        """Remove a value from the configuration"""
        config = cls.read()

        try:
            if section in config and key in config[section]:
                config.remove_option(section, key)
                # If section becomes empty, remove it too
                if not config.options(section):
                    config.remove_section(section)

                config_filepath = cls.get_filepath()
                with open(config_filepath, "w") as config_file:
                    config.write(config_file)
        except Exception as e:
            raise ConfigError(f"Error removing configuration value: {e}")


def get_base_url() -> str:
    """Get the current API base URL"""
    url = Config.get_value("api", ConfigKey.BASE_URL)
    return url if url else ApiEnvironment.PRODUCTION.value


def get_token() -> str | None:
    """Get the API token"""
    return Config.get_value("api", ConfigKey.TOKEN)


def set_token(token: str) -> None:
    """Set the API token"""
    Config.set_value("api", ConfigKey.TOKEN, token)


def remove_token() -> None:
    """Remove the API token"""
    Config.remove_value("api", ConfigKey.TOKEN)


class ConfigError(Exception):
    """Configuration related errors"""
    # No additional methods or attributes are needed for this class.
