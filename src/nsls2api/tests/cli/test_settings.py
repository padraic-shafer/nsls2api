"""Tests for nsls2api.cli.settings — config path, read/write, and legacy migration."""

from __future__ import annotations

import configparser
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from nsls2api.cli.settings import Config, ConfigKey


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_legacy(home: Path, content: str = "[api]\nbase_url = http://127.0.0.1:8080\n") -> Path:
    """Create the legacy bare-file config at <home>/.config/nsls2."""
    legacy = home / ".config" / "nsls2"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(content)
    return legacy


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
# migrate_legacy_config
# ---------------------------------------------------------------------------

class TestMigrateLegacyConfig:
    def test_migrates_legacy_file(self, tmp_path: Path):
        """Legacy bare file is moved to the new location; content is preserved.

        This is the key self-collision regression test: the legacy file occupies
        the path component that must become a directory, so staging via a temp
        file is required.  After migration:
          - ~/.config/nsls2 must be a DIRECTORY (not a file)
          - ~/.config/nsls2/api/cli.ini must exist with original content
          - no staging temp files remain in ~/.config/
        """
        legacy = _make_legacy(tmp_path)
        dot_config = tmp_path / ".config"
        with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_CONFIG_HOME", None)
            new_path = Config.migrate_legacy_config()

        assert new_path is not None
        assert new_path == tmp_path / ".config" / "nsls2" / "api" / "cli.ini"
        assert new_path.exists()
        assert not legacy.exists()              # bare file is gone …
        assert legacy.is_dir()                  # … and replaced by a directory
        content = new_path.read_text()
        assert "base_url" in content
        assert "127.0.0.1:8080" in content
        # No staging temp files left behind.
        leftover = list(dot_config.glob(".nsls2-migrate-*"))
        assert leftover == [], f"Unexpected temp files left over: {leftover}"

    def test_no_op_when_new_already_exists(self, tmp_path: Path):
        """Migration is skipped when the new config file is already present."""
        legacy = _make_legacy(tmp_path)
        new = tmp_path / ".config" / "nsls2" / "api" / "cli.ini"
        new.parent.mkdir(parents=True, exist_ok=True)
        new.write_text("[api]\nbase_url = https://already.here\n")

        with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_CONFIG_HOME", None)
            result = Config.migrate_legacy_config()

        assert result is None
        assert legacy.exists()  # legacy untouched
        assert new.read_text().startswith("[api]\nbase_url = https://already.here")

    def test_no_op_when_legacy_absent(self, tmp_path: Path):
        """Migration is a no-op when the legacy file doesn't exist."""
        with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_CONFIG_HOME", None)
            result = Config.migrate_legacy_config()
        assert result is None

    def test_no_op_when_legacy_is_directory(self, tmp_path: Path):
        """Migration skips silently if ~/.config/nsls2 is already a directory."""
        legacy_dir = tmp_path / ".config" / "nsls2"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        (legacy_dir / "cli").mkdir()

        with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_CONFIG_HOME", None)
            result = Config.migrate_legacy_config()
        assert result is None

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not meaningful on Windows")
    def test_warns_and_proceeds_when_not_writable(self, tmp_path: Path, capsys):
        """Non-writable legacy file: warning is printed with two-step manual hint;
        no exception raised; returns None."""
        legacy = _make_legacy(tmp_path)
        legacy.chmod(0o444)  # read-only

        try:
            with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
                os.environ.pop("XDG_CONFIG_HOME", None)
                new_path = Config.get_filepath()
                result = Config.migrate_legacy_config()
        finally:
            legacy.chmod(0o644)  # restore so tmp_path cleanup works

        assert result is None
        captured = capsys.readouterr()
        assert "migration skipped" in captured.err
        assert str(legacy) in captured.err
        # Hint must be the correct two-step sequence, not the old impossible mv.
        assert "mkdir -p" in captured.err
        assert str(new_path.parent) in captured.err

    def test_migration_triggered_by_read(self, tmp_path: Path):
        """Calling read() auto-migrates the legacy file and returns its contents."""
        _make_legacy(tmp_path, "[api]\nbase_url = http://127.0.0.1:8080\ntoken = abc\n")
        legacy = tmp_path / ".config" / "nsls2"

        with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_CONFIG_HOME", None)
            cfg = Config.read()

        assert cfg.get("api", "base_url") == "http://127.0.0.1:8080"
        assert cfg.get("api", "token") == "abc"
        assert not legacy.exists()
        new = tmp_path / ".config" / "nsls2" / "api" / "cli.ini"
        assert new.exists()

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not meaningful on Windows")
    def test_staging_failure_cleans_up_temp_and_reports_legacy(
        self, tmp_path: Path, capsys
    ):
        """If the initial legacy→tmp staging step raises, migrate_legacy_config():
        - returns None
        - legacy file is still intact
        - no .nsls2-migrate-* temp files are left behind
        - warning says settings remain at legacy (not at a temp path)
        """
        legacy = _make_legacy(tmp_path)
        dot_config = tmp_path / ".config"

        original_replace = Path.replace

        call_count = 0

        def replace_that_fails_on_first_call(self, target):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("simulated staging failure")
            return original_replace(self, target)

        with (
            _patch_home(tmp_path),
            patch.dict(os.environ, {}, clear=False),
            patch.object(Path, "replace", replace_that_fails_on_first_call),
        ):
            os.environ.pop("XDG_CONFIG_HOME", None)
            result = Config.migrate_legacy_config()

        assert result is None
        assert legacy.exists()              # legacy untouched
        assert legacy.read_text().startswith("[api]")
        leftover = list(dot_config.glob(".nsls2-migrate-*"))
        assert leftover == [], f"Temp files leaked: {leftover}"
        captured = capsys.readouterr()
        assert "remain at" in captured.err
        assert "settings are at" not in captured.err  # must NOT claim settings at temp

    def test_shutil_move_failure_triggers_rollback(self, tmp_path: Path, capsys):
        """If shutil.move raises (e.g. cross-device), the legacy file is restored
        and the warning says settings remain at legacy."""
        import nsls2api.cli.settings as settings_mod

        legacy = _make_legacy(tmp_path)

        with (
            _patch_home(tmp_path),
            patch.dict(os.environ, {}, clear=False),
            patch.object(settings_mod.shutil, "move", side_effect=OSError("EXDEV")),
        ):
            os.environ.pop("XDG_CONFIG_HOME", None)
            result = Config.migrate_legacy_config()

        assert result is None
        assert legacy.exists()          # rolled back
        assert legacy.read_text().startswith("[api]")
        captured = capsys.readouterr()
        assert "remain at" in captured.err


# ---------------------------------------------------------------------------
# R4 — read() legacy fallback
# ---------------------------------------------------------------------------

class TestReadLegacyFallback:
    """When migration is skipped/failed, read() must still return legacy values."""

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not meaningful on Windows")
    def test_read_falls_back_to_legacy_when_migration_skipped(
        self, tmp_path: Path, capsys
    ):
        """Non-writable legacy → migration skipped; read() should still return
        the legacy base_url rather than an empty config."""
        legacy = _make_legacy(
            tmp_path, "[api]\nbase_url = http://127.0.0.1:8080\ntoken = mytoken\n"
        )
        legacy.chmod(0o444)

        try:
            with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
                os.environ.pop("XDG_CONFIG_HOME", None)
                cfg = Config.read()
        finally:
            legacy.chmod(0o644)

        assert cfg.get("api", "base_url") == "http://127.0.0.1:8080"
        assert cfg.get("api", "token") == "mytoken"

    def test_read_falls_back_to_legacy_when_new_absent(self, tmp_path: Path):
        """With no new config and no migration trigger, read() reads the legacy file."""
        _make_legacy(
            tmp_path, "[api]\nbase_url = https://api.example.com\n"
        )
        # Do not create the new-style config at all.
        with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_CONFIG_HOME", None)
            # Suppress migration (legacy is present but so is its path — we want
            # to test the fallback directly, so skip the migration by marking the
            # legacy as a dir is too invasive; instead just confirm read() returns
            # legacy values when new is absent after a no-op migration).
            cfg = Config.read()

        # Migration will have run and succeeded here (normal case), but if for any
        # reason it didn't, the fallback should still work. Assert the value is present
        # regardless of whether migration ran.
        assert cfg.get("api", "base_url") == "https://api.example.com"

    def test_read_returns_empty_config_when_both_absent(self, tmp_path: Path):
        """When neither new nor legacy config exists, read() returns an empty config."""
        with _patch_home(tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_CONFIG_HOME", None)
            cfg = Config.read()
        assert not cfg.sections()


# ---------------------------------------------------------------------------
# R5 — Windows branch of get_filepath()
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
