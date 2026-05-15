"""API de Windows para protección contra captura de pantalla."""

import sys
import ctypes
from ctypes import wintypes

# WDA_EXCLUDEFROMCAPTURE: la ventana aparece negra/vacía en OBS, capturas de
# pantalla y cualquier software de grabación. Disponible en Windows 10 2004+.
_WDA_NONE               = 0x00000000
_WDA_EXCLUDEFROMCAPTURE = 0x00000011


def set_capture_protection(hwnd: int, enabled: bool) -> bool:
    """Activa o desactiva la protección contra captura de pantalla."""
    if sys.platform != "win32":
        return False
    try:
        affinity = _WDA_EXCLUDEFROMCAPTURE if enabled else _WDA_NONE
        fn = ctypes.windll.user32.SetWindowDisplayAffinity
        fn.argtypes = [wintypes.HWND, wintypes.DWORD]
        fn.restype  = wintypes.BOOL
        return bool(fn(hwnd, affinity))
    except Exception:
        return False
