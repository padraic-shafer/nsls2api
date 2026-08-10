import configparser
import os
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
        """Get the configuration file path"""
        config_user_home = os.path.expanduser("~")
        return Path(config_user_home) / ".config" / "nsls2"

    @classmethod
    def read(cls) -> configparser.ConfigParser:
        """Read the configuration file"""
        config = configparser.ConfigParser()
        config_filepath = cls.get_filepath()
        config.read(config_filepath)
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
