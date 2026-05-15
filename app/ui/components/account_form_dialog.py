"""Modal para crear o editar una cuenta de LoL."""

import customtkinter as ctk
from typing import Optional, Callable

from app.core.account import Account, VALID_REGIONS, NOTES_MAX_CHARS
from app.config import COLORS, FONTS
from app.ui.components.tag_autocomplete import TagAutocompleteEntry
from app.ui.components.password_generator_dialog import PasswordGeneratorDialog
from app.ui.anim import dialog_fade_in


class AccountFormDialog(ctk.CTkToplevel):
    """
    Ventana modal para anadir o editar una cuenta de LoL.
    Bloquea la ventana principal mientras esta abierta (grab_set).
    """

    def __init__(
        self,
        parent,
        on_submit:       Callable[[dict], None],
        account:         Optional[Account] = None,
        available_tags:  Optional[list] = None,
    ):
        super().__init__(parent)
        self._on_submit       = on_submit
        self._account         = account
        self._is_edit         = account is not None
        self._available_tags  = available_tags or []
        self._pass_visible    = False
        self._pass_entry_ref  = None

        title = "Editar cuenta" if self._is_edit else "Anadir cuenta"
        self.title(title)
        self.geometry("420x580")
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
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text="Editar cuenta" if self._is_edit else "Nueva cuenta",
            font=FONTS["heading"],
            text_color=COLORS["accent"],
        ).grid(row=0, column=0, pady=(20, 4), padx=24, sticky="w")

        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_primary"],
            corner_radius=0,
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent_dim"],
        )
        scroll.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        form = ctk.CTkFrame(scroll, fg_color="transparent")
        form.grid(row=0, column=0, sticky="ew", padx=20, pady=(4, 16))
        form.grid_columnconfigure(0, weight=1)

        self._alias_var    = ctk.StringVar(value=self._account.alias    if self._is_edit else "")
        self._username_var = ctk.StringVar(value=self._account.username if self._is_edit else "")
        self._password_var = ctk.StringVar(value="")
        self._region_var   = ctk.StringVar(value=self._account.region   if self._is_edit else "EUW")
        self._tags_var     = ctk.StringVar(value=", ".join(self._account.tags) if self._is_edit else "")
        self._riot_id_var  = ctk.StringVar(value=self._account.riot_id  if self._is_edit else "")

        pass_placeholder = "Dejar vacio para mantener la actual" if self._is_edit else None

        for slot, label_text, var in [
            (0, "Alias *",    self._alias_var),
            (1, "Username *", self._username_var),
        ]:
            ctk.CTkLabel(
                form, text=label_text,
                font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
            ).grid(row=slot * 2, column=0, sticky="w", pady=(8, 2))
            ctk.CTkEntry(
                form, textvariable=var,
                font=FONTS["body"],
                fg_color=COLORS["bg_card"], border_color=COLORS["border"],
                height=36,
            ).grid(row=slot * 2 + 1, column=0, sticky="ew")

        ctk.CTkLabel(
            form, text="Contrasena *",
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        ).grid(row=4, column=0, sticky="w", pady=(8, 2))

        pass_row = ctk.CTkFrame(form, fg_color="transparent")
        pass_row.grid(row=5, column=0, sticky="ew")
        pass_row.grid_columnconfigure(0, weight=1)

        self._pass_entry_ref = ctk.CTkEntry(
            pass_row, textvariable=self._password_var,
            font=FONTS["body"],
            fg_color=COLORS["bg_card"], border_color=COLORS["border"],
            show="*",
            placeholder_text=pass_placeholder or "",
            height=36,
        )
        self._pass_entry_ref.grid(row=0, column=0, sticky="ew")

        self._toggle_btn = ctk.CTkButton(
            pass_row, text="Mostrar",
            font=FONTS["small"],
            fg_color=COLORS["bg_secondary"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["border"],
            width=68, height=36, corner_radius=6,
            command=self._toggle_password,
        )
        self._toggle_btn.grid(row=0, column=1, padx=(6, 0))

        ctk.CTkButton(
            pass_row, text="Gen.",
            font=FONTS["small"],
            fg_color=COLORS["accent_dim"], text_color=COLORS["text_primary"],
            hover_color=COLORS["accent"],
            width=46, height=36, corner_radius=6,
            command=self._open_generator,
        ).grid(row=0, column=2, padx=(4, 0))

        ctk.CTkLabel(
            form, text="Tags",
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        ).grid(row=6, column=0, sticky="w", pady=(8, 2))

        self._tags_autocomplete = TagAutocompleteEntry(
            form,
            available_tags=self._available_tags,
            textvariable=self._tags_var,
            placeholder_text="Escribe y presiona Enter o coma",
        )
        self._tags_autocomplete.grid(row=7, column=0, sticky="ew")

        notes_header = ctk.CTkFrame(form, fg_color="transparent")
        notes_header.grid(row=8, column=0, sticky="ew", pady=(8, 2))
        notes_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            notes_header, text="Notas",
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._notes_counter = ctk.CTkLabel(
            notes_header, text=f"0 / {NOTES_MAX_CHARS}",
            font=("Consolas", 9), text_color=COLORS["text_secondary"], anchor="e",
        )
        self._notes_counter.grid(row=0, column=1, sticky="e")

        self._notes_box = ctk.CTkTextbox(
            form,
            height=68,
            font=FONTS["body"],
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            border_width=2,
            wrap="word",
        )
        self._notes_box.grid(row=9, column=0, sticky="ew")

        notes_initial = self._account.notes if self._is_edit else ""
        if notes_initial:
            self._notes_box.insert("1.0", notes_initial)
        self._notes_box._textbox.edit_modified(False)
        self._notes_box._textbox.bind("<<Modified>>", self._on_notes_modified)
        self._update_notes_counter()

        ctk.CTkLabel(
            form, text="Region *",
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        ).grid(row=10, column=0, sticky="w", pady=(8, 2))

        ctk.CTkOptionMenu(
            form,
            values=VALID_REGIONS,
            variable=self._region_var,
            font=FONTS["body"],
            fg_color=COLORS["bg_card"],
            button_color=COLORS["accent_dim"],
            button_hover_color=COLORS["accent"],
            dropdown_fg_color=COLORS["bg_card"],
            height=36,
        ).grid(row=11, column=0, sticky="ew")

        ctk.CTkLabel(
            form, text="Riot ID (opcional)",
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        ).grid(row=12, column=0, sticky="w", pady=(8, 2))

        ctk.CTkEntry(
            form, textvariable=self._riot_id_var,
            font=FONTS["body"],
            fg_color=COLORS["bg_card"], border_color=COLORS["border"],
            placeholder_text="GameName#TAG  (ej: Faker#KR1)",
            height=36,
        ).grid(row=13, column=0, sticky="ew")

        ctk.CTkLabel(
            form,
            text="Vincula la cuenta con la API de Riot para ver nivel y rango.",
            font=("Segoe UI", 9), text_color=COLORS["text_secondary"], anchor="w",
            wraplength=340,
        ).grid(row=14, column=0, sticky="w", pady=(2, 0))

        self._error_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            self,
            textvariable=self._error_var,
            font=FONTS["small"],
            text_color=COLORS["danger"],
            wraplength=370,
            height=20,
        ).grid(row=2, column=0, padx=24, pady=(4, 0), sticky="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=24, pady=(6, 20), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_frame, text="Cancelar",
            font=FONTS["body"],
            fg_color=COLORS["bg_card"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"],
            height=38, command=self.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            btn_frame,
            text="Guardar" if self._is_edit else "Anadir",
            font=FONTS["body"],
            fg_color=COLORS["accent"], text_color="#000000",
            hover_color=COLORS["accent_hover"],
            height=38, command=self._submit,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _on_notes_modified(self, _event=None):
        if self._notes_box._textbox.edit_modified():
            text = self._notes_box.get("1.0", "end-1c")
            if len(text) > NOTES_MAX_CHARS:
                self._notes_box.delete(f"1.0+{NOTES_MAX_CHARS}c", "end")
            self._update_notes_counter()
            self._notes_box._textbox.edit_modified(False)

    def _update_notes_counter(self):
        count = len(self._notes_box.get("1.0", "end-1c"))
        warn  = count >= NOTES_MAX_CHARS - 30
        color = COLORS["danger"] if count >= NOTES_MAX_CHARS else (
                COLORS["accent_dim"] if warn else COLORS["text_secondary"])
        self._notes_counter.configure(
            text=f"{count} / {NOTES_MAX_CHARS}",
            text_color=color,
        )

    def _open_generator(self):
        def _insert(password: str):
            self._password_var.set(password)
            if not self._pass_visible:
                self._pass_entry_ref.configure(show="*")
        PasswordGeneratorDialog(self, on_insert=_insert)

    def _toggle_password(self):
        self._pass_visible = not self._pass_visible
        self._pass_entry_ref.configure(show="" if self._pass_visible else "*")
        self._toggle_btn.configure(text="Ocultar" if self._pass_visible else "Mostrar")

    def _submit(self):
        alias    = self._alias_var.get().strip()
        username = self._username_var.get().strip()
        password = self._password_var.get()

        if not alias or not username:
            self._error_var.set("Alias y username son obligatorios.")
            return
        if not self._is_edit and not password:
            self._error_var.set("La contrasena es obligatoria.")
            return

        self._error_var.set("")

        data = {
            "alias":    alias,
            "username": username,
            "password": password,
            "region":   self._region_var.get(),
            "tags":     [t.strip() for t in self._tags_var.get().split(",") if t.strip()],
            "notes":    self._notes_box.get("1.0", "end-1c").strip(),
            "riot_id":  self._riot_id_var.get().strip(),
        }

        self._on_submit(data)
        self.destroy()

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
