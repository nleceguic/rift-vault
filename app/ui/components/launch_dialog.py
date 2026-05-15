"""Modal de lanzamiento rápido: copia credenciales y abre el cliente de Riot."""

import customtkinter as ctk

from app.config import COLORS, FONTS
from app.core.account import Account
from app.ui.anim import dialog_fade_in


def _get_account_service():
    from app.core.service_registry import ServiceRegistry
    from app.core.account_service import AccountService
    return ServiceRegistry.instance().get(AccountService)


def _get_launcher():
    from app.core.service_registry import ServiceRegistry
    from app.core.launcher_service import LauncherService
    return ServiceRegistry.instance().get(LauncherService)


class LaunchDialog(ctk.CTkToplevel):

    def __init__(self, parent, account: Account):
        super().__init__(parent)
        self._account  = account
        self._launcher = _get_launcher()
        self._client_path: str | None = self._launcher.find_client()

        self.title("Lanzar cuenta")
        self.geometry("400x340")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_primary"])

        self.grab_set()
        self.focus_set()
        self.bind("<Escape>", lambda _: self.destroy())

        self._build()
        self.after(50, self._center)
        dialog_fade_in(self)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="Lanzar cuenta",
            font=FONTS["heading"], text_color=COLORS["accent"],
        ).grid(row=0, column=0, padx=24, pady=(20, 2), sticky="w")

        ctk.CTkLabel(
            self,
            text=f"@{self._account.alias}  ·  {self._account.region}"
                 f"  ·  {self._account.username}",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, padx=24, pady=(0, 10), sticky="w")

        creds = ctk.CTkFrame(
            self, fg_color=COLORS["bg_card"],
            corner_radius=8, border_width=1, border_color=COLORS["border"],
        )
        creds.grid(row=2, column=0, padx=24, sticky="ew")
        creds.grid_columnconfigure(0, weight=1)

        self._copy_user_btn = self._cred_row(
            creds, row=0,
            label=f"Usuario:  {self._account.username}",
            pad_top=10, pad_bot=4,
            command=self._copy_username,
        )
        self._copy_pass_btn = self._cred_row(
            creds, row=1,
            label="Contraseña:  ••••••••••••",
            pad_top=4, pad_bot=10,
            command=self._copy_password,
        )

        status_card = ctk.CTkFrame(
            self, fg_color=COLORS["bg_card"],
            corner_radius=8, border_width=1, border_color=COLORS["border"],
        )
        status_card.grid(row=3, column=0, padx=24, pady=(8, 0), sticky="ew")
        status_card.grid_columnconfigure(0, weight=1)

        if self._client_path:
            from pathlib import Path
            exe_name   = Path(self._client_path).name
            status_txt = f"✓  {exe_name}"
            status_col = COLORS["success"]
            hint_txt   = self._client_path
        else:
            status_txt = "✗  Cliente no encontrado"
            status_col = COLORS["danger"]
            hint_txt   = "Configura la ruta en Ajustes → Lanzador"

        ctk.CTkLabel(
            status_card, text=status_txt,
            font=FONTS["small"], text_color=status_col, anchor="w",
        ).grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")

        ctk.CTkLabel(
            status_card, text=hint_txt,
            font=("Consolas", 9), text_color=COLORS["text_secondary"],
            anchor="w", wraplength=340,
        ).grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

        self._status_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            self, textvariable=self._status_var,
            font=FONTS["small"], text_color=COLORS["text_secondary"],
            height=18,
        ).grid(row=4, column=0, padx=24, pady=(6, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=5, column=0, padx=24, pady=(6, 20), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_frame, text="Cancelar",
            font=FONTS["body"],
            fg_color=COLORS["bg_card"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"],
            height=38, command=self.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._launch_btn = ctk.CTkButton(
            btn_frame, text="▶  Abrir League",
            font=FONTS["body"],
            fg_color=COLORS["accent"]       if self._client_path else COLORS["bg_secondary"],
            text_color="#000000"            if self._client_path else COLORS["text_secondary"],
            hover_color=COLORS["accent_hover"] if self._client_path else COLORS["bg_secondary"],
            height=38,
            state="normal" if self._client_path else "disabled",
            command=self._do_launch,
        )
        self._launch_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _cred_row(
        self, parent, row: int, label: str,
        pad_top: int, pad_bot: int, command,
    ) -> ctk.CTkButton:
        """Fila de credencial: etiqueta a la izquierda, botón Copiar a la derecha."""
        row_frame = ctk.CTkFrame(parent, fg_color="transparent")
        row_frame.grid(row=row, column=0, sticky="ew",
                       padx=12, pady=(pad_top, pad_bot))
        row_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            row_frame, text=label,
            font=FONTS["mono"], text_color=COLORS["text_primary"], anchor="w",
        ).grid(row=0, column=0, sticky="w")

        btn = ctk.CTkButton(
            row_frame, text="Copiar",
            font=FONTS["small"],
            fg_color=COLORS["bg_secondary"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["border"],
            width=68, height=28, corner_radius=6,
            command=command,
        )
        btn.grid(row=0, column=1, padx=(8, 0))
        return btn

    def _copy_username(self):
        self._copy_to_clipboard(self._account.username, self._copy_user_btn)

    def _copy_password(self):
        try:
            pw = _get_account_service().get_decrypted_password(self._account.id)
        except Exception:
            return
        self._copy_to_clipboard(pw, self._copy_pass_btn)

    def _copy_to_clipboard(self, text: str, btn: ctk.CTkButton):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        btn.configure(text="✓ OK", text_color=COLORS["success"])
        self.after(
            2000,
            lambda: btn.configure(
                text="Copiar", text_color=COLORS["text_secondary"]
            ) if self.winfo_exists() else None,
        )

    def _do_launch(self):
        self._launch_btn.configure(state="disabled")
        ok, msg = self._launcher.launch(self._client_path)
        if ok:
            self._status_var.set("✓ " + msg)
            self.after(1400, self.destroy)
        else:
            first_line = msg.split("\n")[0]
            self._status_var.set("✗ " + first_line)
            self._launch_btn.configure(state="normal")

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
