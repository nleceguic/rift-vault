"""Modal con historial de contraseñas anteriores de una cuenta."""

import customtkinter as ctk
from datetime import datetime, timezone

from app.config import COLORS, FONTS
from app.core.account import Account
from app.ui.anim import dialog_fade_in

_MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun",
              "jul", "ago", "sep", "oct", "nov", "dic"]

_CLIPBOARD_TTL = 5   # segundos antes de limpiar al copiar desde el historial


def _format_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return f"{dt.day} {_MONTHS_ES[dt.month - 1]} {dt.year}  {dt.strftime('%H:%M')}"
    except Exception:
        return iso


def _get_history_service():
    from app.core.service_registry import ServiceRegistry
    from app.core.password_history_service import PasswordHistoryService
    return ServiceRegistry.instance().get(PasswordHistoryService)


class PasswordHistoryDialog(ctk.CTkToplevel):

    def __init__(self, parent, account: Account):
        super().__init__(parent)
        self._account = account

        self.title("Historial de contraseñas")
        self.geometry("400x460")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_primary"])

        self.grab_set()
        self.focus_set()
        self.bind("<Escape>", lambda _: self.destroy())

        self._reveal_states: dict[int, bool] = {}
        self._copy_jobs:     dict[int, int]  = {}

        self._build()
        self.after(50, self._center)
        dialog_fade_in(self)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Historial de contraseñas",
            font=FONTS["heading"],
            text_color=COLORS["accent"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text=f"{self._account.alias}  ·  {self._account.username}",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        ctk.CTkFrame(self, height=1, fg_color=COLORS["border"]).grid(
            row=0, column=0, sticky="ew", padx=0, pady=(56, 0)
        )

        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent_dim"],
        )
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 8))
        self._scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            self,
            text="Cerrar",
            font=FONTS["body"],
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"],
            height=36,
            command=self.destroy,
        ).grid(row=2, column=0, padx=20, pady=(0, 16), sticky="ew")

        self._populate()

    def _populate(self):
        history = _get_history_service().get_history(self._account.id)

        if not history:
            ctk.CTkLabel(
                self._scroll,
                text="No hay contraseñas anteriores registradas.",
                font=FONTS["body"],
                text_color=COLORS["text_secondary"],
                anchor="center",
            ).grid(row=0, column=0, pady=40)
            return

        for idx, entry in enumerate(history):
            self._build_entry(idx, entry)

    def _build_entry(self, idx: int, entry: dict):
        self._reveal_states[idx] = False
        plain = entry["password"]
        masked = "•" * min(len(plain), 16)

        card = ctk.CTkFrame(
            self._scroll,
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=8,
        )
        card.grid(row=idx, column=0, sticky="ew", pady=(0, 6))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text=_format_date(entry["changed_at"]),
            font=("Consolas", 9),
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(8, 2))

        pw_var = ctk.StringVar(value=masked)
        pw_label = ctk.CTkLabel(
            card,
            textvariable=pw_var,
            font=("Consolas", 12),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        pw_label.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))

        reveal_text = ctk.StringVar(value="Ver")
        reveal_btn = ctk.CTkButton(
            card,
            textvariable=reveal_text,
            font=FONTS["small"],
            fg_color=COLORS["bg_secondary"],
            text_color=COLORS["text_secondary"],
            hover_color=COLORS["border"],
            width=40, height=26, corner_radius=6,
            command=lambda i=idx, v=pw_var, t=reveal_text, p=plain, m=masked:
                self._toggle_reveal(i, v, t, p, m),
        )
        reveal_btn.grid(row=1, column=1, padx=(4, 2), pady=(0, 8))

        copy_text = ctk.StringVar(value="Copiar")
        copy_btn = ctk.CTkButton(
            card,
            textvariable=copy_text,
            font=FONTS["small"],
            fg_color=COLORS["bg_secondary"],
            text_color=COLORS["text_secondary"],
            hover_color=COLORS["border"],
            width=52, height=26, corner_radius=6,
            command=lambda i=idx, p=plain, t=copy_text: self._copy(i, p, t),
        )
        copy_btn.grid(row=1, column=2, padx=(0, 8), pady=(0, 8))

    def _toggle_reveal(self, idx: int, pw_var, reveal_text, plain: str, masked: str):
        self._reveal_states[idx] = not self._reveal_states[idx]
        if self._reveal_states[idx]:
            pw_var.set(plain)
            reveal_text.set("Ocultar")
        else:
            pw_var.set(masked)
            reveal_text.set("Ver")

    def _copy(self, idx: int, plain: str, copy_text):
        self.clipboard_clear()
        self.clipboard_append(plain)
        self.update()
        copy_text.set("OK")

        if idx in self._copy_jobs:
            try:
                self.after_cancel(self._copy_jobs[idx])
            except Exception:
                pass

        def _restore():
            if self.winfo_exists():
                copy_text.set("Copiar")
            self._copy_jobs.pop(idx, None)

        self._copy_jobs[idx] = self.after(_CLIPBOARD_TTL * 1000, _restore)

    def _center(self):
        self.update_idletasks()
        pw = self.master.winfo_width()
        ph = self.master.winfo_height()
        px = self.master.winfo_x()
        py = self.master.winfo_y()
        w  = self.winfo_width()
        h  = self.winfo_height()
        x  = px + (pw - w) // 2
        y  = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
