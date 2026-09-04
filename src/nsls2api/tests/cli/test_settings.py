"""Tests for nsls2api.cli.settings — config path and read/write.

Migration and legacy fallback tests live in test_settings_migration.py.
"""

from __future__ import annotations

import configparser
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from nsls2api.cli.settings import Config, ConfigKey


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_home(tmp_path: Path):
    """Redirect Path.home() to tmp_path. Env vars are controlled per-test."""
    return patch.object(Path, "home", return_value=tmp_path)


# ---------------------------------------------------------------------------
# get_filepath — path resolution
# ---------------------------------------------------------------------------

class TestGetFilepath:
    def test_default_posix_path(self, tmp_path: Path):
        """Without XDG_CONFIG_HOME, resolves to ~/.config/nsls2/api/cli.ini."""
        with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_CONFIG_HOME", None)
            result = Config.get_filepath()
        assert result == tmp_path / ".config" / "nsls2" / "api" / "cli.ini"

    def test_respects_xdg_config_home(self, tmp_path: Path):
        """XDG_CONFIG_HOME is honoured when set."""
        xdg = str(tmp_path / "xdg")
        with _patch_home(tmp_path), patch.dict(os.environ, {"XDG_CONFIG_HOME": xdg}):
            result = Config.get_filepath()
        assert result == tmp_path / "xdg" / "nsls2" / "api" / "cli.ini"

    def test_blank_xdg_config_home_falls_back(self, tmp_path: Path):
        """A blank XDG_CONFIG_HOME is treated as unset."""
        with _patch_home(tmp_path), patch.dict(os.environ, {"XDG_CONFIG_HOME": "   "}):
            result = Config.get_filepath()
        assert result == tmp_path / ".config" / "nsls2" / "api" / "cli.ini"


# ---------------------------------------------------------------------------
# set_value / read — basic round-trip
# ---------------------------------------------------------------------------

class TestSetValueRead:
    def test_set_creates_dirs_and_file(self, tmp_path: Path):
        """set_value creates the nsls2/api/ directory and writes cli.ini."""
        with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_CONFIG_HOME", None)
            Config.set_value("api", ConfigKey.BASE_URL, "https://example.com")
            filepath = Config.get_filepath()

        assert filepath.exists()
        assert filepath.parent.is_dir()
        cfg = configparser.ConfigParser()
        cfg.read(filepath)
        assert cfg.get("api", "base_url") == "https://example.com"

    def test_get_value_round_trip(self, tmp_path: Path):
        with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_CONFIG_HOME", None)
            Config.set_value("api", ConfigKey.TOKEN, "tok123")
            result = Config.get_value("api", ConfigKey.TOKEN)
        assert result == "tok123"

    def test_get_value_missing_returns_none(self, tmp_path: Path):
        with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_CONFIG_HOME", None)
            result = Config.get_value("api", ConfigKey.BASE_URL)
        assert result is None


# ---------------------------------------------------------------------------
# Windows branch of get_filepath()
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform != "win32", reason="Only run on Windows")
class TestGetFilepathWindows:
    """These tests patch sys.platform and run only on Windows."""

    def test_windows_path_with_appdata(self, tmp_path: Path, monkeypatch):
        """With APPDATA set, uses %APPDATA%/nsls2/api/cli.ini."""
        appdata = str(tmp_path / "AppData" / "Roaming")
        monkeypatch.setenv("APPDATA", appdata)
        result = Config.get_filepath()
        assert result == tmp_path / "AppData" / "Roaming" / "nsls2" / "api" / "cli.ini"

    def test_windows_path_without_appdata(self, tmp_path: Path, monkeypatch):
        """Without APPDATA, falls back to Path.home()/AppData/Roaming/..."""
        monkeypatch.delenv("APPDATA", raising=False)
        with _patch_home(tmp_path):
            result = Config.get_filepath()
        assert result == tmp_path / "AppData" / "Roaming" / "nsls2" / "api" / "cli.ini"


class TestGetFilepathWindowsSimulated:
    """Simulate the Windows branch on all platforms via sys.platform patching."""

    def test_windows_path_with_appdata_simulated(self, tmp_path: Path, monkeypatch):
        """Patch sys.platform to win32; APPDATA set → uses APPDATA path."""
        appdata = str(tmp_path / "AppData" / "Roaming")
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", appdata)
        result = Config.get_filepath()
        assert result == tmp_path / "AppData" / "Roaming" / "nsls2" / "api" / "cli.ini"

    def test_windows_path_without_appdata_simulated(self, tmp_path: Path, monkeypatch):
        """Patch sys.platform to win32; no APPDATA → falls back to home."""
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.delenv("APPDATA", raising=False)
        with _patch_home(tmp_path):
            result = Config.get_filepath()
        assert result == tmp_path / "AppData" / "Roaming" / "nsls2" / "api" / "cli.ini"
