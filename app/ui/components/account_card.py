"""Tarjeta visual de cuenta con timer de limpieza de portapapeles."""

import customtkinter as ctk
from typing import Callable

from app.core.account import Account
from app.core.event_bus import EventBus
from app.config import COLORS, FONTS
from app.ui.components.tooltip import Tooltip

# Importación diferida para evitar ciclos: se resuelve en tiempo de uso
def _get_service():
    from app.core.service_registry import ServiceRegistry
    from app.core.account_service import AccountService
    return ServiceRegistry.instance().get(AccountService)

def _get_riot_service():
    try:
        from app.core.service_registry import ServiceRegistry
        from app.core.riot_api_service import RiotApiService
        return ServiceRegistry.instance().get(RiotApiService)
    except Exception:
        return None

def _get_launcher_service():
    try:
        from app.core.service_registry import ServiceRegistry
        from app.core.launcher_service import LauncherService
        return ServiceRegistry.instance().get(LauncherService)
    except Exception:
        return None

_CLIPBOARD_TTL = 30

def _resolve_ctk_color(color) -> str:
    if isinstance(color, (list, tuple)):
        return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
    return str(color)

def _lerp_hex(c1: str, c2: str, t: float) -> str:
    r = round(int(c1[1:3], 16) + (int(c2[1:3], 16) - int(c1[1:3], 16)) * t)
    g = round(int(c1[3:5], 16) + (int(c2[3:5], 16) - int(c1[3:5], 16)) * t)
    b = round(int(c1[5:7], 16) + (int(c2[5:7], 16) - int(c1[5:7], 16)) * t)
    return f"#{r:02x}{g:02x}{b:02x}"

_STATUS_COLORS = {
    "active":    COLORS["success"],
    "not_found": ("#E67E22", "#E67E22"),
    "error":     COLORS["text_secondary"],
    "unknown":   COLORS["text_secondary"],
}


class AccountCard(ctk.CTkFrame):

    _FEEDBACK_MS = 1500

    def __init__(self, parent, account, on_edit, on_delete, **kwargs):
        super().__init__(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["bg_primary"],  # starts invisible; animate_in() fades it in
            **kwargs,
        )
        self._account        = account
        self._on_edit        = on_edit
        self._on_delete      = on_delete
        self._bus            = EventBus.instance()
        self._copy_btns      = {}
        self._restore_jobs   = {}
        self._clipboard_job  = None
        self._clipboard_key  = None
        self._anim_jobs      = []

        self._build()
        self._bind_hover()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="@", font=FONTS["heading"],
                     text_color=COLORS["accent_dim"]).grid(row=0, column=0, padx=(0, 4))
        ctk.CTkLabel(
            top, text=self._account.alias,
            font=FONTS["heading"], text_color=COLORS["accent"], anchor="w",
        ).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            top, text=self._account.region,
            font=FONTS["small"], text_color=COLORS["text_secondary"],
            fg_color=COLORS["bg_secondary"], corner_radius=4, width=36,
        ).grid(row=0, column=2, padx=(4, 0))

        ctk.CTkLabel(
            self, text=self._account.username,
            font=FONTS["mono"], text_color=COLORS["text_primary"], anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))

        tags_frame = ctk.CTkFrame(self, fg_color="transparent", height=28)
        tags_frame.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 8))
        tags_frame.grid_propagate(False)

        for tag in self._account.tags[:4]:
            ctk.CTkLabel(
                tags_frame, text=f"#{tag}",
                font=FONTS["small"], text_color=COLORS["accent_dim"],
                fg_color=COLORS["bg_secondary"], corner_radius=4,
            ).pack(side="left", padx=(0, 4))

        ctk.CTkFrame(self, height=1, fg_color=COLORS["border"]).grid(
            row=3, column=0, sticky="ew", padx=8)

        copy_row = ctk.CTkFrame(self, fg_color="transparent")
        copy_row.grid(row=4, column=0, sticky="ew", padx=8, pady=(6, 2))
        copy_row.grid_columnconfigure((0, 1, 2), weight=1)

        copy_actions = [
            ("user", "User", self._copy_username, "Copiar username (se limpia en 30s)"),
            ("pass", "Pass", self._copy_password, "Copiar contrasena (se limpia en 30s)"),
            ("both", "Todo", self._copy_both,     "Copiar usuario y contrasena"),
        ]

        for col, (key, label, cmd, tip) in enumerate(copy_actions):
            btn = ctk.CTkButton(
                copy_row, text=label,
                font=FONTS["small"],
                fg_color=COLORS["bg_secondary"],
                text_color=COLORS["text_secondary"],
                hover_color=COLORS["border"],
                height=26, corner_radius=6,
                command=cmd,
            )
            btn.grid(row=0, column=col, sticky="ew",
                     padx=(0 if col == 0 else 3, 3 if col < 2 else 0))
            self._copy_btns[key] = btn
            Tooltip(btn, tip)

        ctk.CTkFrame(self, height=1, fg_color=COLORS["border"]).grid(
            row=5, column=0, sticky="ew", padx=8)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=6, column=0, sticky="ew", padx=8, pady=8)
        actions.grid_columnconfigure((0, 1, 2), weight=1)

        edit_btn = ctk.CTkButton(
            actions, text="Editar",
            font=FONTS["small"], fg_color="transparent",
            text_color=COLORS["text_secondary"], hover_color=COLORS["bg_secondary"],
            height=28, corner_radius=6,
            command=lambda: self._on_edit(self._account),
        )
        edit_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        Tooltip(edit_btn, "Editar esta cuenta")

        hist_btn = ctk.CTkButton(
            actions, text="Historial",
            font=FONTS["small"], fg_color="transparent",
            text_color=COLORS["text_secondary"], hover_color=COLORS["bg_secondary"],
            height=28, corner_radius=6,
            command=self._open_history,
        )
        hist_btn.grid(row=0, column=1, sticky="ew", padx=3)
        Tooltip(hist_btn, "Ver contraseñas anteriores")

        del_btn = ctk.CTkButton(
            actions, text="Eliminar",
            font=FONTS["small"], fg_color="transparent",
            text_color=COLORS["danger"], hover_color=COLORS["bg_secondary"],
            height=28, corner_radius=6,
            command=lambda: self._on_delete(self._account),
        )
        del_btn.grid(row=0, column=2, sticky="ew", padx=(3, 0))
        Tooltip(del_btn, "Eliminar esta cuenta")

        ctk.CTkFrame(self, height=1, fg_color=COLORS["border"]).grid(
            row=7, column=0, sticky="ew", padx=8)

        launch_row = ctk.CTkFrame(self, fg_color="transparent")
        launch_row.grid(row=8, column=0, sticky="ew", padx=8, pady=(4, 4))
        launch_row.grid_columnconfigure(0, weight=1)

        launch_btn = ctk.CTkButton(
            launch_row, text="▶  Lanzar",
            font=FONTS["small"],
            fg_color=COLORS["accent"], text_color="#000000",
            hover_color=COLORS["accent_hover"],
            height=28, corner_radius=6,
            command=self._open_launch_dialog,
        )
        launch_btn.grid(row=0, column=0, sticky="ew")
        Tooltip(launch_btn, "Abrir League con esta cuenta")

        self._riot_row = ctk.CTkFrame(self, fg_color="transparent")
        self._riot_row.grid(row=10, column=0, sticky="ew", padx=8, pady=(0, 6))
        self._riot_row.grid_columnconfigure(0, weight=1)
        self._riot_row.grid_remove()

        self._riot_sep = ctk.CTkFrame(self, height=1, fg_color=COLORS["border"])
        self._riot_sep.grid(row=9, column=0, sticky="ew", padx=8)
        self._riot_sep.grid_remove()

        self._riot_status_var = ctk.StringVar(value="")
        self._refresh_riot_section()

    def animate_in(self):
        """Smooth border fade-in. Call this after the card becomes visible."""
        for job in self._anim_jobs:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._anim_jobs.clear()

        start = _resolve_ctk_color(COLORS["bg_primary"])
        end   = _resolve_ctk_color(COLORS["border"])
        steps, interval = 8, 18  # 144 ms total
        for i in range(steps + 1):
            color = _lerp_hex(start, end, i / steps)
            job = self.after(
                i * interval,
                lambda c=color: self.configure(border_color=c) if self.winfo_exists() else None,
            )
            self._anim_jobs.append(job)

    def _refresh_riot_section(self):
        riot = _get_riot_service()
        if not riot or not riot.is_configured():
            return
        if not self._account.riot_id:
            return

        for w in self._riot_row.winfo_children():
            w.destroy()

        cached = riot.get_cached(self._account.id)
        self._riot_sep.grid()
        self._riot_row.grid()

        if cached:
            status = cached.get("status", "unknown")
            color  = _STATUS_COLORS.get(status, COLORS["text_secondary"])

            if status == "active":
                level = cached.get("level", 0)
                rank  = cached.get("rank", "")
                text  = f"Nv. {level}"
                if rank:
                    text += f"  ·  {rank}"
            elif status == "not_found":
                text  = "⚠ Cuenta no encontrada"
                color = _STATUS_COLORS["not_found"]
            else:
                msg  = cached.get("message", "")
                text = f"Error{': ' + msg[:28] if msg else ''}"

            ctk.CTkLabel(
                self._riot_row, text=text,
                font=("Consolas", 10), text_color=color, anchor="w",
            ).grid(row=0, column=0, sticky="w")
        else:
            ctk.CTkLabel(
                self._riot_row, text="Sin datos de Riot",
                font=("Consolas", 10), text_color=COLORS["text_secondary"], anchor="w",
            ).grid(row=0, column=0, sticky="w")

        refresh_btn = ctk.CTkButton(
            self._riot_row, text="↻",
            font=("Consolas", 12),
            fg_color="transparent",
            text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"],
            width=26, height=20, corner_radius=4,
            command=self._fetch_riot_data,
        )
        refresh_btn.grid(row=0, column=1, padx=(4, 0))
        Tooltip(refresh_btn, "Actualizar datos de Riot")

    def _fetch_riot_data(self):
        riot = _get_riot_service()
        if not riot or not self._account.riot_id:
            return
        riot.fetch(self._account.id, self._account.riot_id, self._account.region)
        if self.winfo_exists():
            self._refresh_riot_section()

    def _open_history(self):
        from app.ui.components.password_history_dialog import PasswordHistoryDialog
        PasswordHistoryDialog(self.winfo_toplevel(), self._account)

    def _open_launch_dialog(self):
        from app.ui.components.launch_dialog import LaunchDialog
        LaunchDialog(self.winfo_toplevel(), self._account)

    def _copy_username(self):
        self._copy_to_clipboard(self._account.username, "user", "username")

    def _copy_password(self):
        # Descifrar solo en el momento de copiar; el texto plano no se guarda
        plaintext = _get_service().get_decrypted_password(self._account.id)
        self._copy_to_clipboard(plaintext, "pass", "password")

    def _copy_both(self):
        plaintext = _get_service().get_decrypted_password(self._account.id)
        self._copy_to_clipboard(
            f"{self._account.username} {plaintext}", "both", "both")

    def _copy_to_clipboard(self, text, key, field):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self._bus.emit("clipboard.armed", alias=self._account.alias, field=field)
        from app.hooks.hooks_registry import HooksRegistry
        HooksRegistry.instance().fire("after_copy", field=field, alias=self._account.alias)
        self._show_feedback(key, "OK")
        self._start_clipboard_timer(key)

    def _start_clipboard_timer(self, key):
        self._cancel_clipboard_timer()
        self._clipboard_key = key
        self._tick_clipboard(key, _CLIPBOARD_TTL)

    def _tick_clipboard(self, key, remaining):
        if not self.winfo_exists():
            return
        btn = self._copy_btns.get(key)
        if not btn or not btn.winfo_exists():
            return

        if remaining <= 0:
            try:
                self.clipboard_clear()
                self.update()
            except Exception:
                pass
            self._bus.emit("clipboard.cleared")
            self._clipboard_job = None
            self._clipboard_key = None
            originals = {"user": "User", "pass": "Pass", "both": "Todo"}
            if btn.winfo_exists():
                btn.configure(text=originals.get(key, ""),
                              text_color=COLORS["text_secondary"])
            return

        if remaining <= 10:
            btn.configure(text=f"{remaining}s", text_color=COLORS["accent_dim"])

        self._clipboard_job = self.after(
            1000, lambda: self._tick_clipboard(key, remaining - 1))

    def _cancel_clipboard_timer(self):
        if self._clipboard_job:
            try:
                self.after_cancel(self._clipboard_job)
            except Exception:
                pass
            self._clipboard_job = None

        if self._clipboard_key:
            originals = {"user": "User", "pass": "Pass", "both": "Todo"}
            btn = self._copy_btns.get(self._clipboard_key)
            if btn and btn.winfo_exists():
                btn.configure(text=originals.get(self._clipboard_key, ""),
                              text_color=COLORS["text_secondary"])
            self._clipboard_key = None

    def _show_feedback(self, key, message):
        btn = self._copy_btns.get(key)
        if not btn:
            return
        if key in self._restore_jobs:
            try:
                self.after_cancel(self._restore_jobs[key])
            except Exception:
                pass
        btn.configure(text=message, text_color=COLORS["success"])
        originals = {"user": "User", "pass": "Pass", "both": "Todo"}
        orig = originals.get(key, "")
        job = self.after(
            self._FEEDBACK_MS,
            lambda: btn.configure(
                text=orig, text_color=COLORS["text_secondary"]
            ) if btn.winfo_exists() else None,
        )
        self._restore_jobs[key] = job

    def _bind_hover(self):
        self.bind("<Enter>", self._on_hover_enter)
        self.bind("<Leave>", self._on_hover_leave)

    def _on_hover_enter(self, _event=None):
        for job in self._anim_jobs:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._anim_jobs.clear()
        self.configure(border_color=COLORS["accent_dim"])

    def _on_hover_leave(self, _event=None):
        self.configure(border_color=COLORS["border"])
