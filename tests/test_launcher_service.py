"""
test_launcher_service.py – Tests for LauncherService.

Coverage:
  - find_client: user config path, common dirs scan, registry fallback
  - launch: success (Riot Client args injected), success (LeagueClient no args),
            missing file, bad path, no client found
  - is_client_running: process found, not found
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.core.launcher_service import LauncherService, _RIOT_EXE, _LEAGUE_EXE, _RIOT_ARGS


# ── Helpers ───────────────────────────────────────────────────────────────────

class _MockSettings:
    def __init__(self, launcher_path: str = ""):
        self.launcher_path = launcher_path


# ── find_client ───────────────────────────────────────────────────────────────

class TestFindClient:

    def test_returns_custom_path_when_valid(self, tmp_path):
        exe = tmp_path / "RiotClientServices.exe"
        exe.write_text("dummy")
        svc = LauncherService(settings=_MockSettings(str(exe)))
        assert svc.find_client() == str(exe)

    def test_ignores_custom_path_when_not_a_file(self, tmp_path):
        nonexistent = str(tmp_path / "does_not_exist.exe")
        svc = LauncherService(settings=_MockSettings(nonexistent))
        # no common dirs exist in tmp either → None
        with patch("app.core.launcher_service._CANDIDATE_BASE_DIRS", []):
            with patch("app.core.launcher_service._registry_dirs", return_value=[]):
                result = svc.find_client()
        assert result is None

    def test_finds_exe_in_candidate_dir(self, tmp_path):
        riot_client_dir = tmp_path / "Riot Client"
        riot_client_dir.mkdir()
        exe = riot_client_dir / _RIOT_EXE
        exe.write_text("dummy")

        svc = LauncherService(settings=_MockSettings(""))
        with patch(
            "app.core.launcher_service._CANDIDATE_BASE_DIRS", [str(tmp_path)]
        ):
            with patch("app.core.launcher_service._registry_dirs", return_value=[]):
                result = svc.find_client()
        assert result == str(exe)

    def test_finds_league_exe_in_candidate_dir(self, tmp_path):
        league_dir = tmp_path / "League of Legends"
        league_dir.mkdir()
        exe = league_dir / _LEAGUE_EXE
        exe.write_text("dummy")

        svc = LauncherService(settings=_MockSettings(""))
        with patch(
            "app.core.launcher_service._CANDIDATE_BASE_DIRS", [str(tmp_path)]
        ):
            with patch("app.core.launcher_service._registry_dirs", return_value=[]):
                result = svc.find_client()
        assert result == str(exe)

    def test_finds_exe_via_registry_fallback(self, tmp_path):
        exe = tmp_path / _RIOT_EXE
        exe.write_text("dummy")

        svc = LauncherService(settings=_MockSettings(""))
        with patch("app.core.launcher_service._CANDIDATE_BASE_DIRS", []):
            with patch(
                "app.core.launcher_service._registry_dirs",
                return_value=[str(tmp_path)],
            ):
                result = svc.find_client()
        assert result == str(exe)

    def test_returns_none_when_nothing_found(self):
        svc = LauncherService(settings=_MockSettings(""))
        with patch("app.core.launcher_service._CANDIDATE_BASE_DIRS", []):
            with patch("app.core.launcher_service._registry_dirs", return_value=[]):
                result = svc.find_client()
        assert result is None

    def test_no_settings_falls_through_to_candidate_dirs(self, tmp_path):
        exe = tmp_path / _RIOT_EXE
        exe.write_text("dummy")
        svc = LauncherService(settings=None)
        with patch("app.core.launcher_service._CANDIDATE_BASE_DIRS", [str(tmp_path)]):
            with patch("app.core.launcher_service._registry_dirs", return_value=[]):
                result = svc.find_client()
        assert result == str(exe)


# ── launch ────────────────────────────────────────────────────────────────────

class TestLaunch:

    def test_riot_client_called_with_args(self, tmp_path):
        exe = tmp_path / _RIOT_EXE
        exe.write_text("dummy")

        with patch("subprocess.Popen") as mock_popen:
            svc = LauncherService()
            ok, msg = svc.launch(str(exe))

        assert ok is True
        assert "iniciado" in msg.lower()
        call_args = mock_popen.call_args[0][0]
        assert call_args[0] == str(exe)
        for arg in _RIOT_ARGS:
            assert arg in call_args

    def test_league_client_called_without_riot_args(self, tmp_path):
        exe = tmp_path / _LEAGUE_EXE
        exe.write_text("dummy")

        with patch("subprocess.Popen") as mock_popen:
            svc = LauncherService()
            ok, msg = svc.launch(str(exe))

        assert ok is True
        call_args = mock_popen.call_args[0][0]
        assert call_args == [str(exe)]

    def test_launch_auto_finds_client(self, tmp_path):
        exe = tmp_path / _RIOT_EXE
        exe.write_text("dummy")

        svc = LauncherService(settings=_MockSettings(str(exe)))
        with patch("subprocess.Popen"):
            ok, _ = svc.launch()  # path=None → calls find_client()

        assert ok is True

    def test_returns_false_when_no_client_found(self):
        svc = LauncherService(settings=_MockSettings(""))
        with patch("app.core.launcher_service._CANDIDATE_BASE_DIRS", []):
            with patch("app.core.launcher_service._registry_dirs", return_value=[]):
                ok, msg = svc.launch()
        assert ok is False
        assert "no se encontró" in msg.lower()

    def test_returns_false_when_path_not_a_file(self, tmp_path):
        svc = LauncherService()
        ok, msg = svc.launch(str(tmp_path / "ghost.exe"))
        assert ok is False
        assert "no existe" in msg.lower()

    def test_returns_false_on_popen_exception(self, tmp_path):
        exe = tmp_path / _RIOT_EXE
        exe.write_text("dummy")

        with patch("subprocess.Popen", side_effect=OSError("permission denied")):
            svc = LauncherService()
            ok, msg = svc.launch(str(exe))

        assert ok is False
        assert "error" in msg.lower()


# ── is_client_running ─────────────────────────────────────────────────────────

class TestIsClientRunning:

    def _run_result(self, stdout: str):
        r = MagicMock()
        r.stdout = stdout
        return r

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_detects_riot_client_running(self):
        svc = LauncherService()
        with patch(
            "subprocess.run",
            return_value=self._run_result(f"Image Name: {_RIOT_EXE.lower()}\n"),
        ):
            assert svc.is_client_running() is True

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_detects_league_client_running(self):
        svc = LauncherService()
        with patch(
            "subprocess.run",
            return_value=self._run_result(f"{_LEAGUE_EXE.lower()} running\n"),
        ):
            assert svc.is_client_running() is True

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_returns_false_when_not_running(self):
        svc = LauncherService()
        with patch(
            "subprocess.run",
            return_value=self._run_result("notepad.exe\nchrome.exe\n"),
        ):
            assert svc.is_client_running() is False

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_returns_false_on_exception(self):
        svc = LauncherService()
        with patch("subprocess.run", side_effect=Exception("timeout")):
            assert svc.is_client_running() is False

    def test_returns_false_on_non_windows(self):
        svc = LauncherService()
        with patch("sys.platform", "linux"):
            assert svc.is_client_running() is False


# ── _registry_dirs (module function) ─────────────────────────────────────────

class TestRegistryDirs:

    def test_returns_empty_list_on_non_windows(self):
        from app.core.launcher_service import _registry_dirs
        with patch("sys.platform", "linux"):
            result = _registry_dirs()
        assert result == []

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_reads_install_dir_from_registry(self, tmp_path):
        """Smoke test: real registry call won't fail even if key is absent."""
        from app.core.launcher_service import _registry_dirs
        result = _registry_dirs()
        assert isinstance(result, list)

    def test_handles_import_error_gracefully(self):
        from app.core.launcher_service import _registry_dirs
        with patch.dict("sys.modules", {"winreg": None}):
            # Should not raise; winreg ImportError handled internally
            result = _registry_dirs()
        assert isinstance(result, list)
