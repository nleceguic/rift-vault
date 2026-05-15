"""
tooltip.py – Tooltip reutilizable para cualquier widget CTk.

Uso:
    btn = ctk.CTkButton(...)
    Tooltip(btn, text="Copia el username al portapapeles")

El tooltip aparece 500ms después de entrar en el widget
y desaparece al salir o al hacer clic.
"""

import customtkinter as ctk
from app.config import COLORS, FONTS


class Tooltip:
    """
    Tooltip flotante que se ancla cerca del widget objetivo.
    No hereda de ningún widget — se adjunta externamente.
    """

    _DELAY_MS = 500
    _PAD_X    = 8
    _PAD_Y    = 4

    def __init__(self, widget, text: str):
        self._widget   = widget
        self._text     = text
        self._tip_win  = None
        self._job      = None

        widget.bind("<Enter>",   self._schedule, add="+")
        widget.bind("<Leave>",   self._cancel,   add="+")
        widget.bind("<Button>",  self._cancel,   add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._job = self._widget.after(self._DELAY_MS, self._show)

    def _cancel(self, _event=None):
        if self._job:
            self._widget.after_cancel(self._job)
            self._job = None
        self._hide()

    def _show(self):
        if self._tip_win or not self._text:
            return

        x = self._widget.winfo_rootx() + 8
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4

        self._tip_win = tw = ctk.CTkToplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        tw.configure(fg_color=COLORS["bg_secondary"])

        ctk.CTkLabel(
            tw,
            text=self._text,
            font=FONTS["small"],
            text_color=COLORS["text_primary"],
            fg_color=COLORS["bg_secondary"],
            corner_radius=6,
            padx=self._PAD_X,
            pady=self._PAD_Y,
        ).pack()

    def _hide(self):
        if self._tip_win:
            self._tip_win.destroy()
            self._tip_win = None
