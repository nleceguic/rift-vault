"""
test_config.py – Tests de configuración de rutas.

Verifica que RIFT_VAULT_DATA_DIR sobreescribe el directorio por defecto
y que todos los paths derivados apuntan al nuevo directorio.
"""

import importlib
import os
import sys

import pytest


def _reload_config(monkeypatch, data_dir: str | None):
    """Recarga app.config con el env var dado (o sin él si None)."""
    if data_dir is not None:
        monkeypatch.setenv("RIFT_VAULT_DATA_DIR", data_dir)
    else:
        monkeypatch.delenv("RIFT_VAULT_DATA_DIR", raising=False)

    # Forzar recarga del módulo para que el import-time vuelva a evaluar os.environ
    if "app.config" in sys.modules:
        del sys.modules["app.config"]

    import app.config as cfg
    return cfg


class TestDataDirEnvVar:
    def test_default_dir_contains_rift_vault(self, monkeypatch):
        cfg = _reload_config(monkeypatch, None)
        assert ".rift_vault" in cfg.DATA_DIR

    def test_env_var_overrides_data_dir(self, monkeypatch, tmp_path):
        custom = str(tmp_path / "custom_data")
        cfg = _reload_config(monkeypatch, custom)
        assert cfg.DATA_DIR == custom

    def test_derived_paths_use_custom_dir(self, monkeypatch, tmp_path):
        custom = str(tmp_path / "mydata")
        cfg = _reload_config(monkeypatch, custom)
        assert cfg.SQLITE_FILE.startswith(custom)
        assert cfg.KEY_FILE.startswith(custom)
        assert cfg.SETTINGS_FILE.startswith(custom)
        assert cfg.LOG_FILE.startswith(custom)

    def test_empty_env_var_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("RIFT_VAULT_DATA_DIR", "")
        if "app.config" in sys.modules:
            del sys.modules["app.config"]
        import app.config as cfg
        assert ".rift_vault" in cfg.DATA_DIR

    def test_env_var_cleared_restores_default(self, monkeypatch, tmp_path):
        custom = str(tmp_path / "tmp_data")
        _reload_config(monkeypatch, custom)
        cfg2 = _reload_config(monkeypatch, None)
        assert ".rift_vault" in cfg2.DATA_DIR
