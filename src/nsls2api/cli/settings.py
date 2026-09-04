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
        the new config file does not yet exist, copy the content to the new
        location and remove the legacy file only after the new file is confirmed
        written.

        In the default (no-XDG) case the legacy file occupies the path component
        ``nsls2`` that must become a *directory* for the new path.  The legacy
        file is removed just before ``mkdir`` so the name is free; the content is
        already preserved in a temporary copy made at the start of migration.

        Returns the new path if migration occurred, ``None`` otherwise.

        Emits a warning to stderr and returns ``None`` (without raising) if
        migration fails for any reason, so a failure never breaks a normal CLI
        command.
        """
        legacy = cls._legacy_filepath()
        new = cls.get_filepath()

        # Already migrated (or user already has a new-style config) — nothing to do.
        if new.exists():
            return None

        # Only migrate a plain FILE.  If legacy is a directory, skip silently.
        if not legacy.is_file():
            return None

        # Rename (the staging step) requires write+execute on the containing
        # directory, not on the file itself.
        if not os.access(legacy.parent, os.W_OK | os.X_OK):
            print(
                f"Warning: nsls2api config migration skipped — "
                f"'{legacy.parent}' is not writable. "
                f"To migrate manually:\n"
                f"  1. Move '{legacy}' aside (e.g. rename it to '{legacy}.bak')\n"
                f"  2. Create the directory '{new.parent}'\n"
                f"  3. Move the saved file into place as '{new}'",
                file=sys.stderr,
            )
            return None

        # Step 1 — copy legacy content to a temp sibling.  Legacy stays in place
        # until migration succeeds; a failure here leaves everything unchanged.
        fd, tmp_name = tempfile.mkstemp(dir=legacy.parent, prefix=".nsls2-migrate-")
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            shutil.copy2(legacy, tmp)
        except OSError as exc:
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
            return None

        # Step 2 — move tmp to the new location, handling the name-collision case.
        #
        # When XDG_CONFIG_HOME is not set, new == ~/.config/nsls2/api/cli.ini, so
        # legacy (~/.config/nsls2, a file) sits exactly where the 'nsls2' directory
        # component of new.parent must be created.  We must remove the legacy file
        # before mkdir can succeed; since tmp already holds a full copy, this is safe.
        #
        # When XDG_CONFIG_HOME points elsewhere, new lives in a different tree and
        # there is no collision; legacy is left untouched until after the new file
        # is successfully written.
        new_under_legacy = legacy in new.parents
        legacy_removed = False
        try:
            if new_under_legacy:
                legacy.unlink()           # free the 'nsls2' name; tmp holds the copy
                legacy_removed = True
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(tmp), str(new))   # cross-device safe
        except OSError as exc:
            # Recovery: restore legacy from tmp when possible.
            if legacy_removed and not legacy.exists():
                # The legacy name is free — move tmp straight back.
                try:
                    shutil.move(str(tmp), str(legacy))
                    print(
                        f"Warning: nsls2api config migration failed ({exc}). "
                        f"Your settings remain at '{legacy}'. "
                        f"To migrate manually:\n"
                        f"  1. Move '{legacy}' aside (e.g. rename it to '{legacy}.bak')\n"
                        f"  2. Create the directory '{new.parent}'\n"
                        f"  3. Move the saved file into place as '{new}'",
                        file=sys.stderr,
                    )
                except OSError:
                    print(
                        f"Warning: nsls2api config migration failed ({exc}) and "
                        f"could not be recovered. "
                        f"Your settings are at '{tmp}'. "
                        f"To recover:\n"
                        f"  1. Create the directory '{new.parent}'\n"
                        f"  2. Move '{tmp}' into place as '{new}'",
                        file=sys.stderr,
                    )
            else:
                # Legacy was not removed (XDG case, or copy step) — settings intact.
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
            return None

        # Step 3 — migration succeeded.
        # XDG case: legacy was not removed in step 2; delete it now.
        if not new_under_legacy:
            legacy.unlink(missing_ok=True)
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
