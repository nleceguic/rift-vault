"""Modal para cambiar la contraseña maestra con recifrado completo."""

import customtkinter as ctk

from app.config import COLORS, FONTS
from app.ui.anim import dialog_fade_in


class ChangePasswordDialog(ctk.CTkToplevel):
    """Diálogo modal para cambiar la contraseña maestra de Rift Vault."""

    def __init__(self, parent, registry):
        super().__init__(parent)
        self._registry = registry

        self.title("Cambiar contraseña maestra")
        self.geometry("420x480")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_primary"])
        self.grab_set()
        self.focus_set()
        self.bind("<Escape>", lambda _: self.destroy())

        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        x = px + (pw - self.winfo_width())  // 2
        y = py + (ph - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        self._build()
        dialog_fade_in(self, delay_ms=10)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="Cambiar contraseña maestra",
            font=FONTS["heading"], text_color=COLORS["text_primary"],
        ).grid(row=0, column=0, padx=28, pady=(24, 4), sticky="w")

        ctk.CTkLabel(
            self,
            text="Introduce tu contraseña actual y elige una nueva.\n"
                 "Todas tus cuentas serán re-cifradas automáticamente.",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
            wraplength=370, justify="left",
        ).grid(row=1, column=0, padx=28, pady=(0, 20), sticky="w")

        self._old_var = ctk.StringVar()
        self._old_entry = self._make_field(
            row=2, label="Contraseña actual", var=self._old_var,
        )

        self._new_var = ctk.StringVar()
        self._new_entry = self._make_field(
            row=4, label="Nueva contraseña", var=self._new_var,
        )

        self._confirm_var = ctk.StringVar()
        self._confirm_entry = self._make_field(
            row=6, label="Confirmar nueva contraseña", var=self._confirm_var,
        )

        self._progress = ctk.CTkProgressBar(
            self, fg_color=COLORS["bg_secondary"],
            progress_color=COLORS["accent"], height=4, corner_radius=2,
        )
        self._progress.set(0)

        self._status_var = ctk.StringVar(value="")
        self._status_label = ctk.CTkLabel(
            self, textvariable=self._status_var,
            font=FONTS["small"], text_color=COLORS["danger"],
            wraplength=370,
        )
        self._status_label.grid(row=8, column=0, padx=28, pady=(8, 0))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=9, column=0, padx=28, pady=(16, 24), sticky="ew")
        btn_row.grid_columnconfigure((0, 1), weight=1)

        self._submit_btn = ctk.CTkButton(
            btn_row, text="Cambiar contraseña",
            font=FONTS["body"],
            fg_color=COLORS["accent"], text_color="#000000",
            hover_color=COLORS["accent_hover"],
            height=40, corner_radius=8,
            command=self._submit,
        )
        self._submit_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            btn_row, text="Cancelar",
            font=FONTS["body"],
            fg_color=COLORS["bg_card"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"],
            height=40, corner_radius=8,
            command=self.destroy,
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

        self._old_entry.bind("<Return>", lambda _: self._new_entry.focus_set())
        self._new_entry.bind("<Return>", lambda _: self._confirm_entry.focus_set())
        self._confirm_entry.bind("<Return>", lambda _: self._submit())
        self._old_entry.focus_set()

    def _make_field(self, row: int, label: str, var: ctk.StringVar) -> ctk.CTkEntry:
        ctk.CTkLabel(
            self, text=label,
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        ).grid(row=row, column=0, padx=28, pady=(0, 4), sticky="w")

        entry = ctk.CTkEntry(
            self, textvariable=var,
            show="*", font=FONTS["body"],
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            height=40,
        )
        entry.grid(row=row + 1, column=0, padx=28, pady=(0, 12), sticky="ew")
        return entry

    def _submit(self):
        old     = self._old_var.get().strip()
        new     = self._new_var.get()
        confirm = self._confirm_var.get()

        # Validaciones locales (sin PBKDF2 aún)
        if not old:
            self._set_error("Introduce tu contraseña actual.")
            return
        if not new:
            self._set_error("La nueva contraseña no puede estar vacía.")
            return
        if len(new) < 8:
            self._set_error("La nueva contraseña debe tener al menos 8 caracteres.")
            return
        if new != confirm:
            self._set_error("Las contraseñas nuevas no coinciden.")
            return
        if old == new:
            self._set_error("La nueva contraseña debe ser diferente a la actual.")
            return

        self._set_loading(True)
        self.after(80, lambda: self._do_change(old, new))

    def _do_change(self, old: str, new: str):
        try:
            ok = self._registry.crypto.change_password(
                old, new, storage=self._registry.storage
            )
        except Exception as e:
            self._set_loading(False)
            self._set_error(f"Error inesperado: {e}")
            return

        self._set_loading(False)

        if not ok:
            self._set_error("La contraseña actual es incorrecta.")
            self._old_var.set("")
            self._old_entry.configure(border_color=COLORS["danger"])
            self._old_entry.focus_set()
            return

        self._status_label.configure(text_color=COLORS["success"])
        self._status_var.set("Contraseña cambiada correctamente.")
        self._submit_btn.configure(state="disabled")
        self.after(1800, self.destroy)

    def _set_error(self, message: str):
        self._status_label.configure(text_color=COLORS["danger"])
        self._status_var.set(message)

    def _set_loading(self, loading: bool):
        if loading:
            self._status_var.set("")
            self._submit_btn.configure(state="disabled", text="Cambiando...")
            self._progress.grid(row=7, column=0, padx=28, pady=(8, 0), sticky="ew")
            self._progress.configure(mode="indeterminate")
            self._progress.start()
        else:
            self._progress.stop()
            self._progress.grid_remove()
            self._submit_btn.configure(state="normal", text="Cambiar contraseña")
