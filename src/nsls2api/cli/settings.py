import configparser
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Any

from nsls2api.cli import settings_migration


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
            appdata = os.environ.get("APPDATA", "").strip()
            base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        else:
            xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
            base = Path(xdg) if xdg else Path.home() / ".config"
        return base / "nsls2" / "api" / "cli.ini"

    @classmethod
    def read(cls) -> configparser.ConfigParser:
        """Read the configuration file, migrating legacy config if present.

        If migration was skipped or failed and the new config file does not yet
        exist, fall back to reading the legacy bare file so existing settings
        (base_url, token) are not silently dropped.
        """
        config_filepath = cls.get_filepath()
        settings_migration.migrate_legacy_config(config_filepath)
        config = configparser.ConfigParser()
        if config_filepath.is_file():
            config.read(config_filepath)
        else:
            settings_migration.read_legacy_fallback(config, config_filepath)
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
