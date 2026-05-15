"""Detección y lanzamiento del cliente de League of Legends / Riot Client."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_RIOT_EXE   = "RiotClientServices.exe"
_LEAGUE_EXE = "LeagueClient.exe"

_RIOT_ARGS = [
    "--launch-product=league_of_legends",
    "--launch-patchline=live",
]

_CANDIDATE_BASE_DIRS: list[str] = [
    r"C:\Riot Games",
    r"D:\Riot Games",
    r"E:\Riot Games",
    os.path.expandvars(r"%ProgramFiles%\Riot Games"),
    os.path.expandvars(r"%ProgramFiles(x86)%\Riot Games"),
    os.path.expandvars(r"%LOCALAPPDATA%\Riot Games"),
]

# (subdirectorio_dentro_del_base, nombre_ejecutable) — en orden de preferencia
_EXE_SUBPATHS: list[tuple[str, str]] = [
    ("Riot Client",       _RIOT_EXE),
    ("",                  _RIOT_EXE),
    ("League of Legends", _LEAGUE_EXE),
    ("",                  _LEAGUE_EXE),
]


def _registry_dirs() -> list[str]:
    """Devuelve directorios de instalación encontrados en el registro de Windows."""
    dirs: list[str] = []
    if sys.platform != "win32":
        return dirs
    try:
        import winreg
        candidates = [
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\WOW6432Node\Riot Games, Inc\League of Legends"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\Riot Games, Inc\League of Legends"),
            (winreg.HKEY_CURRENT_USER,
             r"Software\Riot Games, Inc\League of Legends"),
        ]
        for hive, key_path in candidates:
            try:
                with winreg.OpenKey(hive, key_path) as k:
                    val, _ = winreg.QueryValueEx(k, "InstallDir")
                    if val:
                        dirs.append(str(val))
                        dirs.append(str(Path(val).parent))
            except OSError:
                continue
    except ImportError:
        pass
    return dirs


class LauncherService:
    """Localiza y lanza el cliente de League of Legends / Riot Client."""

    def __init__(self, settings=None) -> None:
        self._settings = settings

    def find_client(self) -> str | None:
        """Devuelve la ruta del ejecutable: ruta configurada → rutas comunes → registro."""
        if self._settings:
            custom = (self._settings.launcher_path or "").strip()
            if custom and Path(custom).is_file():
                return custom

        search_dirs = list(_CANDIDATE_BASE_DIRS) + _registry_dirs()

        for base in search_dirs:
            for subdir, exe in _EXE_SUBPATHS:
                p = Path(base) / subdir / exe if subdir else Path(base) / exe
                if p.is_file():
                    return str(p)

        return None

    def launch(self, path: str | None = None) -> tuple[bool, str]:
        """
        Lanza el cliente de League of Legends.
        Devuelve (éxito, mensaje).
        """
        exe = path or self.find_client()

        if not exe:
            return False, (
                "No se encontró el cliente de League of Legends.\n"
                "Configura la ruta en Ajustes → Lanzador."
            )

        if not Path(exe).is_file():
            return False, f"El archivo no existe:\n{exe}"

        try:
            args = [exe]
            if Path(exe).name.lower() == _RIOT_EXE.lower():
                args += _RIOT_ARGS
            subprocess.Popen(args)
            return True, "Cliente iniciado."
        except Exception as exc:
            return False, f"Error al iniciar el cliente:\n{exc}"

    def is_client_running(self) -> bool:
        """
        Comprueba si el cliente ya está en ejecución.
        Usa `tasklist` en Windows para no requerir dependencias externas.
        """
        if sys.platform != "win32":
            return False
        try:
            result = subprocess.run(
                ["tasklist"],
                capture_output=True, text=True, timeout=4,
            )
            out = result.stdout.lower()
            return _RIOT_EXE.lower() in out or _LEAGUE_EXE.lower() in out
        except Exception:
            return False
