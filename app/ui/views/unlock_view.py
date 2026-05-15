"""Pantalla de desbloqueo y configuración inicial de Rift Vault."""

import logging
import threading
from datetime import datetime

import tkinter as tk
import customtkinter as ctk
from typing import Callable

from app.core.crypto_service import CryptoService
from app.config import COLORS, FONTS, APP_VERSION, LOGO_PATH

logger = logging.getLogger(__name__)


class _Spinner(tk.Canvas):
    def __init__(self, parent, size=28):
        dark = ctk.get_appearance_mode() == "Dark"
        bg      = COLORS["bg_card"][1]   if dark else COLORS["bg_card"][0]
        fg      = COLORS["accent"][1]    if dark else COLORS["accent"][0]
        super().__init__(parent, width=size, height=size,
                         bg=bg, highlightthickness=0, bd=0)
        pad = size * 0.12
        self._arc = self.create_arc(
            pad, pad, size - pad, size - pad,
            start=90, extent=270,
            outline=fg, width=3, style="arc",
        )
        self._angle = 90
        self._job = None
        self._fg = fg
        self._bg = bg
        self.itemconfig(self._arc, outline=bg)  # invisible por defecto

    def start(self):
        self.itemconfig(self._arc, outline=self._fg)
        self._tick()

    def stop(self):
        if self._job:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        self.itemconfig(self._arc, outline=self._bg)  # vuelve a invisible

    def _tick(self):
        self._angle = (self._angle - 15) % 360
        self.itemconfig(self._arc, start=self._angle)
        self._job = self.after(20, self._tick)


_DELAYS = {3: 2, 4: 5}
_DELAY_DEFAULT = 15

_MONTHS_ES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]


def _format_last_unlock(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return f"{dt.day} {_MONTHS_ES[dt.month - 1]} {dt.year} a las {dt.strftime('%H:%M')}"
    except Exception:
        return ""


class UnlockView(ctk.CTkFrame):

    def __init__(self, parent, crypto, on_unlocked, last_unlock_at: str | None = None, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_primary"], **kwargs)
        self._crypto          = crypto
        self._on_unlocked     = on_unlocked
        self._last_unlock_at  = last_unlock_at
        self._is_setup        = not crypto.is_configured
        self._attempts        = 0
        self._countdown_job   = None
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(
            self, fg_color=COLORS["bg_card"],
            corner_radius=16, border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=0, column=0, padx=80, pady=40, ipadx=20, ipady=12)
        card.grid_columnconfigure(0, weight=1)
        self._card = card

        try:
            from PIL import Image
            _img = Image.open(LOGO_PATH)
            _w, _h = _img.size
            _s = min(160 / _w, 160 / _h)
            _logo_img = ctk.CTkImage(light_image=_img, dark_image=_img,
                                     size=(int(_w * _s), int(_h * _s)))
        except Exception:
            _logo_img = None
        ctk.CTkLabel(
            card, text="",
            image=_logo_img,
        ).grid(row=0, column=0, pady=(16, 6))

        # Row 1: última sesión (solo en unlock si hay dato)
        if not self._is_setup and self._last_unlock_at:
            formatted = _format_last_unlock(self._last_unlock_at)
            if formatted:
                ctk.CTkLabel(
                    card, text=f"Última sesión: {formatted}",
                    font=FONTS["small"], text_color=COLORS["text_secondary"],
                ).grid(row=1, column=0, pady=(0, 8))

        # Row 2: label contraseña — Row 3: entry contraseña
        self._password_var = ctk.StringVar()
        pass_label_text = "Crea tu contrasena maestra" if self._is_setup else "Introduce tu contrasena maestra"
        ctk.CTkLabel(
            card,
            text=pass_label_text,
            font=FONTS["body"], text_color=COLORS["text_secondary"], anchor="w",
        ).grid(row=2, column=0, sticky="w", padx=24, pady=(0, 4))

        self._pass_entry = ctk.CTkEntry(
            card, textvariable=self._password_var,
            show="*", font=FONTS["body"],
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            height=40,
            placeholder_text="Minimo 8 caracteres" if self._is_setup else "",
        )
        self._pass_entry.grid(row=3, column=0, sticky="ew", padx=24)
        self._pass_entry.bind("<Return>", lambda _: self._submit())

        # Rows 4-5: confirmar contraseña (solo setup)
        self._confirm_var = ctk.StringVar()
        if self._is_setup:
            ctk.CTkLabel(
                card, text="Confirmar contrasena *",
                font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
            ).grid(row=4, column=0, sticky="w", padx=24, pady=(12, 4))

            self._confirm_entry = ctk.CTkEntry(
                card, textvariable=self._confirm_var,
                show="*", font=FONTS["body"],
                fg_color=COLORS["bg_secondary"],
                border_color=COLORS["border"],
                height=40,
            )
            self._confirm_entry.grid(row=5, column=0, sticky="ew", padx=24)
            self._confirm_entry.bind("<Return>", lambda _: self._submit())

        # Row 6: error (dinámico)
        self._error_var = ctk.StringVar(value="")
        self._error_label = ctk.CTkLabel(
            card, textvariable=self._error_var,
            font=FONTS["small"], text_color=COLORS["danger"], wraplength=340,
        )

        # Row 7: botón submit
        self._submit_btn = ctk.CTkButton(
            card,
            text="Crear contrasena y entrar" if self._is_setup else "Desbloquear",
            font=FONTS["body"], fg_color=COLORS["accent"],
            text_color="#000000", hover_color=COLORS["accent_hover"],
            height=42, corner_radius=8,
            command=self._submit,
        )
        self._submit_btn.grid(row=7, column=0, sticky="ew", padx=24, pady=(6, 8))

        # Row 8: spinner — siempre en el grid para no mover el layout
        self._progress = _Spinner(card, size=28)
        self._progress.grid(row=8, column=0, pady=(4, 4))

        note = (
            "AVISO: Esta contrasena cifra todas tus credenciales. No existe forma de recuperarla si la olvidas."
            if self._is_setup else
            "Tus contrasenas, seguras detras del nexo."
        )
        ctk.CTkLabel(
            card, text=note,
            font=FONTS["small"], text_color=COLORS["text_secondary"], wraplength=340,
        ).grid(row=9, column=0, pady=(4, 0))

        ctk.CTkLabel(
            card, text=f"v{APP_VERSION}",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
        ).grid(row=10, column=0, pady=(4, 0))

        self._pass_entry.focus_set()

    def _submit(self):
        if self._is_setup:
            self._handle_setup()
        else:
            self._handle_unlock()

    def _handle_setup(self):
        password = self._password_var.get()
        confirm  = self._confirm_var.get()

        if len(password) < 8:
            self._set_error("La contrasena debe tener al menos 8 caracteres.")
            self._pass_entry.configure(border_color=COLORS["danger"])
            return
        if password != confirm:
            self._set_error("Las contrasenas no coinciden.")
            self._confirm_entry.configure(border_color=COLORS["danger"])
            return

        self._start_progress("Configurando cifrado...")
        threading.Thread(target=self._do_setup, args=(password,), daemon=True).start()

    def _do_setup(self, password):
        try:
            self._crypto.setup(password)
            err = None
        except Exception as e:
            err = str(e)
        self.after(0, lambda: self._on_setup_done(err))

    def _on_setup_done(self, err):
        self._stop_progress()
        if err is None:
            logger.info("Primera configuración de contraseña maestra completada.")
            self._on_unlocked()
        else:
            logger.error("Error durante la configuración inicial: %s", err)
            self._set_error(f"Error: {err}")

    def _handle_unlock(self):
        password = self._password_var.get()
        if not password:
            self._set_error("Introduce tu contrasena maestra.")
            return

        self._start_progress("Verificando...")
        threading.Thread(target=self._do_unlock, args=(password,), daemon=True).start()

    def _do_unlock(self, password):
        success = self._crypto.unlock(password)
        self.after(0, lambda: self._on_unlock_result(success))

    def _on_unlock_result(self, success):
        self._stop_progress()

        if success:
            logger.info("Sesión desbloqueada correctamente.")
            self._on_unlocked()
            return

        self._attempts += 1
        self._password_var.set("")
        self._pass_entry.configure(border_color=COLORS["danger"])

        delay = _DELAYS.get(self._attempts,
                            _DELAY_DEFAULT if self._attempts >= 5 else 0)

        if delay:
            logger.warning("Desbloqueo fallido (intento %d) — penalización %ds.", self._attempts, delay)
            self._set_error(
                f"Contrasena incorrecta ({self._attempts} intentos). "
                f"Espera {delay} segundos."
            )
            self._start_countdown(delay)
        else:
            logger.warning("Desbloqueo fallido (intento %d).", self._attempts)
            self._set_error(f"Contrasena incorrecta ({self._attempts} intentos).")

    def _start_countdown(self, seconds):
        self._submit_btn.configure(state="disabled")
        self._tick_countdown(seconds)

    def _tick_countdown(self, remaining):
        if remaining <= 0:
            self._submit_btn.configure(
                state="normal", text="Desbloquear",
                fg_color=COLORS["accent"],
            )
            self._set_error(f"Puedes intentarlo de nuevo ({self._attempts} intentos fallidos).")
            self._pass_entry.focus_set()
            return

        self._submit_btn.configure(
            text=f"Espera {remaining}s...",
            fg_color=COLORS["accent_dim"],
        )
        self._countdown_job = self.after(
            1000, lambda: self._tick_countdown(remaining - 1)
        )

    def _start_progress(self, message):
        self._set_error("")
        self._pass_entry.configure(border_color=COLORS["border"])
        self._submit_btn.configure(state="disabled", text=message)
        self._progress.start()

    def _stop_progress(self):
        self._progress.stop()
        btn_text = "Crear contrasena y entrar" if self._is_setup else "Desbloquear"
        self._submit_btn.configure(state="normal", text=btn_text)

    def cleanup(self):
        """Cancela jobs pendientes antes de que el padre destruya este widget."""
        if self._countdown_job:
            try:
                self.after_cancel(self._countdown_job)
            except Exception:
                pass
            self._countdown_job = None
        try:
            self._progress.stop()
        except Exception:
            pass

    def _set_error(self, message):
        self._error_var.set(message)
        if message:
            self._error_label.grid(row=6, column=0, pady=(4, 0))
        else:
            self._error_label.grid_remove()
            self._pass_entry.configure(border_color=COLORS["border"])