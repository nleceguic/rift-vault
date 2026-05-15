"""Configuracion global de colores, fuentes, rutas y constantes de Rift Vault."""

APP_NAME    = "Rift Vault"
APP_VERSION = "1.0"
APP_SLOGAN  = "Tus contrasenas, seguras detras del nexo."

WINDOW_WIDTH      = 920
WINDOW_HEIGHT     = 600
WINDOW_MIN_WIDTH  = 760
WINDOW_MIN_HEIGHT = 500

DEFAULT_COLOR_THEME = "dark-blue"

COLORS = {
    "bg_primary":     ("#F2EDE0", "#0D0D14"),
    "bg_secondary":   ("#E8E1D0", "#13131F"),
    "bg_card":        ("#FDFAF3", "#1A1A2E"),
    "accent":         ("#B8891E", "#C89B3C"),
    "accent_hover":   ("#D4A030", "#E8B84B"),
    "accent_dim":     ("#8A6A28", "#8A6A28"),
    "text_primary":   ("#1C1C2A", "#E8E0D5"),
    "text_secondary": ("#5A5A6E", "#8A8A9A"),
    "danger":         ("#C0392B", "#C0392B"),
    "danger_hover":   ("#A93226", "#A93226"),
    "success":        ("#218C50", "#27AE60"),
    "border":         ("#D0C8B0", "#2A2A3E"),
}

FONTS = {
    "title":   ("Segoe UI", 22, "bold"),
    "heading": ("Segoe UI", 14, "bold"),
    "body":    ("Segoe UI", 12),
    "small":   ("Segoe UI", 10),
    "mono":    ("Consolas", 11),
}

#  Rutas de datos
#  RIFT_VAULT_DATA_DIR sobreescribe el directorio por defecto (~/.rift_vault).
#  Útil para modo portable (USB), entornos CI o instalaciones multi-perfil:
#    set RIFT_VAULT_DATA_DIR=D:\rift_portable\data   (Windows)
#    export RIFT_VAULT_DATA_DIR=/mnt/usb/rift_data   (Linux/Mac)
import os
import sys

def _resource(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, relative)

LOGO_PATH = _resource("logo.png")
DATA_DIR      = os.environ.get("RIFT_VAULT_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".rift_vault")
ACCOUNTS_FILE  = os.path.join(DATA_DIR, "accounts.json")   # legado; activo hasta migración
SQLITE_FILE    = os.path.join(DATA_DIR, "accounts.db")
KEY_FILE       = os.path.join(DATA_DIR, "master.key")
SETTINGS_FILE  = os.path.join(DATA_DIR, "settings.json")
LOG_FILE       = os.path.join(DATA_DIR, "rift_vault.log")

SIDEBAR_WIDTH = 200

NAV_ITEMS = [
    {"id": "home",     "label": "  Inicio",   "view": "home"},
    {"id": "accounts", "label": "  Cuentas",  "view": "accounts"},
    {"id": "settings", "label": "  Ajustes",  "view": "settings"},
]
