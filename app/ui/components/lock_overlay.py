"""
lock_overlay.py – Pantalla de bloqueo por inactividad.

Se muestra como una ventana sin decoraciones que cubre completamente la
ventana principal. El usuario debe reintroducir la contraseña maestra para
continuar. Usa grab_set() para bloquear toda interacción con la app subyacente.
"""

import threading

import customtkinter as ctk
from typing import Callable

from app.config import COLORS, FONTS, APP_VERSION, LOGO_PATH

_DELAYS      = {3: 2, 4: 5}   # intentos → segundos de espera
_DELAY_MAX   = 15              # a partir del 5.º intento


class LockOverlay(ctk.CTkToplevel):
    """
    Overlay de bloqueo de sesión. Se posiciona encima de la ventana padre
    y bloquea toda interacción hasta que se introduzca la contraseña correcta.
    """

    def __init__(self, parent, crypto, on_unlocked: Callable[[], None]):
        super().__init__(parent)
        self._crypto       = crypto
        self._on_unlocked  = on_unlocked
        self._attempts     = 0
        self._countdown_job = None

        self.overrideredirect(True)
        self.configure(fg_color=COLORS["bg_primary"])

        self.grab_set()
        self.lift()
        try:
            self.attributes("-alpha", 0.0)
        except Exception:
            pass

        self._build()

        self.after(10, self._cover_parent)
        self.after(30, self._fade_in)
        self.master.bind("<Configure>", self._on_parent_configure, add=True)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_card"],
            corner_radius=16,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=0, column=0, padx=0, pady=0, ipadx=32, ipady=24)
        card.grid_columnconfigure(0, weight=1)

        try:
            from PIL import Image
            _img = Image.open(LOGO_PATH)
            _w, _h = _img.size
            _s = min(64 / _w, 64 / _h)
            _logo_img = ctk.CTkImage(light_image=_img, dark_image=_img,
                                     size=(int(_w * _s), int(_h * _s)))
        except Exception:
            _logo_img = None
        ctk.CTkLabel(
            card, text="Rift Vault",
            image=_logo_img, compound="top",
            font=("Segoe UI", 32, "bold"), text_color=COLORS["accent"],
        ).grid(row=0, column=0, pady=(0, 4))

        ctk.CTkLabel(
            card, text="Sesion bloqueada por inactividad",
            font=FONTS["body"], text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, pady=(0, 20))

        ctk.CTkLabel(
            card, text="Contrasena maestra",
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        ).grid(row=2, column=0, sticky="w", padx=24, pady=(0, 4))

        self._pass_var = ctk.StringVar()
        self._pass_entry = ctk.CTkEntry(
            card, textvariable=self._pass_var,
            show="*", font=FONTS["body"],
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            height=40,
        )
        self._pass_entry.grid(row=3, column=0, sticky="ew", padx=24)
        self._pass_entry.bind("<Return>", lambda _: self._submit())

        self._progress = ctk.CTkProgressBar(
            card, fg_color=COLORS["bg_secondary"],
            progress_color=COLORS["accent"], height=4, corner_radius=2,
        )
        self._progress.set(0)

        self._error_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            card, textvariable=self._error_var,
            font=FONTS["small"], text_color=COLORS["danger"], wraplength=320,
        ).grid(row=5, column=0, pady=(8, 0))

        self._unlock_btn = ctk.CTkButton(
            card, text="Desbloquear",
            font=FONTS["body"],
            fg_color=COLORS["accent"], text_color="#000000",
            hover_color=COLORS["accent_hover"],
            height=42, corner_radius=8,
            command=self._submit,
        )
        self._unlock_btn.grid(row=6, column=0, sticky="ew", padx=24, pady=(16, 24))

        ctk.CTkLabel(
            card, text=f"v{APP_VERSION}",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
        ).grid(row=7, column=0, pady=(0, 8))

        self._pass_entry.focus_set()

    def _submit(self):
        password = self._pass_var.get()
        if not password:
            self._error_var.set("Introduce tu contrasena maestra.")
            return

        self._start_progress("Verificando...")
        threading.Thread(target=self._do_unlock, args=(password,), daemon=True).start()

    def _do_unlock(self, password: str):
        success = self._crypto.unlock(password)
        self.after(0, lambda: self._on_unlock_result(success))

    def _on_unlock_result(self, success: bool):
        self._stop_progress()

        if success:
            self.master.unbind("<Configure>")
            self._fade_out()
            return

        self._attempts += 1
        self._pass_var.set("")
        self._pass_entry.configure(border_color=COLORS["danger"])

        delay = _DELAYS.get(self._attempts,
                            _DELAY_MAX if self._attempts >= 5 else 0)
        if delay:
            self._error_var.set(
                f"Contrasena incorrecta ({self._attempts} intentos). "
                f"Espera {delay}s."
            )
            self._start_countdown(delay)
        else:
            self._error_var.set(f"Contrasena incorrecta ({self._attempts} intentos).")

    def _start_countdown(self, seconds: int):
        self._unlock_btn.configure(state="disabled")
        self._tick_countdown(seconds)

    def _tick_countdown(self, remaining: int):
        if remaining <= 0:
            self._unlock_btn.configure(
                state="normal", text="Desbloquear",
                fg_color=COLORS["accent"],
            )
            self._error_var.set(
                f"Puedes intentarlo de nuevo ({self._attempts} intentos fallidos)."
            )
            self._pass_entry.focus_set()
            return

        self._unlock_btn.configure(
            text=f"Espera {remaining}s...",
            fg_color=COLORS["accent_dim"],
        )
        self._countdown_job = self.after(
            1000, lambda: self._tick_countdown(remaining - 1)
        )

    def _start_progress(self, message: str):
        self._error_var.set("")
        self._pass_entry.configure(border_color=COLORS["border"])
        self._unlock_btn.configure(state="disabled", text=message)
        self._progress.grid(row=4, column=0, sticky="ew", padx=24, pady=(12, 0))
        self._progress.configure(mode="indeterminate")
        self._progress.start()

    def _stop_progress(self):
        self._progress.stop()
        self._progress.grid_remove()
        self._unlock_btn.configure(state="normal", text="Desbloquear")

    def _fade_in(self, step: int = 0, steps: int = 10, interval: int = 16):
        try:
            self.attributes("-alpha", step / steps)
        except Exception:
            return
        if step < steps:
            self.after(interval, lambda: self._fade_in(step + 1, steps, interval))

    def _fade_out(self, step: int = 10, steps: int = 10, interval: int = 14):
        try:
            self.attributes("-alpha", step / steps)
        except Exception:
            self._dismiss()
            return
        if step > 0:
            self.after(interval, lambda: self._fade_out(step - 1, steps, interval))
        else:
            self._dismiss()

    def _dismiss(self):
        try:
            self.destroy()
        except Exception:
            pass
        self._on_unlocked()

    def _cover_parent(self):
        """Hace que el overlay cubra exactamente la ventana padre."""
        try:
            self.master.update_idletasks()
            w = self.master.winfo_width()
            h = self.master.winfo_height()
            x = self.master.winfo_x()
            y = self.master.winfo_y()
            self.geometry(f"{w}x{h}+{x}+{y}")
            self.lift()
            self._pass_entry.focus_set()
        except Exception:
            pass

    def _on_parent_configure(self, _event):
        """Reposiciona el overlay si la ventana padre se mueve o redimensiona."""
        self.after(5, self._cover_parent)
