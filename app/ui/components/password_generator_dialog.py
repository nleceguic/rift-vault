"""Modal para generar contraseñas seguras con evaluación de fortaleza."""

import customtkinter as ctk
from typing import Callable

from app.core.password_generator import generate, evaluate, STRENGTH_LABELS
from app.config import COLORS, FONTS
from app.ui.anim import dialog_fade_in

# Color de barra de fortaleza por nivel (1-5)
_STRENGTH_COLORS = {
    1: COLORS["danger"],
    2: ("#E67E22", "#E67E22"),
    3: ("#D4AC0D", "#D4AC0D"),
    4: COLORS["success"],
    5: ("#27AE60", "#27AE60"),
}


class PasswordGeneratorDialog(ctk.CTkToplevel):
    """on_insert(password) se llama al confirmar la contraseña generada."""

    def __init__(
        self,
        parent,
        on_insert: Callable[[str], None],
    ):
        super().__init__(parent)
        self._on_insert = on_insert

        self.title("Generador de contraseñas")
        self.geometry("420x410")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_primary"])

        self.grab_set()
        self.focus_set()
        self.bind("<Escape>", lambda _: self.destroy())

        self._length_var       = ctk.IntVar(value=16)
        self._use_upper_var    = ctk.BooleanVar(value=True)
        self._use_digits_var   = ctk.BooleanVar(value=True)
        self._use_symbols_var  = ctk.BooleanVar(value=True)
        self._no_ambiguous_var = ctk.BooleanVar(value=False)
        self._current_password = ""

        self._build()
        self._generate()
        self.after(50, self._center)
        dialog_fade_in(self)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="Generador de contraseñas",
            font=FONTS["heading"],
            text_color=COLORS["accent"],
        ).grid(row=0, column=0, pady=(20, 12), padx=24, sticky="w")

        preview_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            border_width=2,
            corner_radius=8,
        )
        preview_frame.grid(row=1, column=0, padx=24, sticky="ew")
        preview_frame.grid_columnconfigure(0, weight=1)

        self._pass_label = ctk.CTkLabel(
            preview_frame,
            text="",
            font=("Consolas", 14, "bold"),
            text_color=COLORS["text_primary"],
            anchor="center",
        )
        self._pass_label.grid(row=0, column=0, padx=12, pady=(10, 6), sticky="ew")

        self._strength_bar = ctk.CTkProgressBar(
            preview_frame,
            height=6,
            corner_radius=3,
            progress_color=COLORS["accent"],
        )
        self._strength_bar.set(0)
        self._strength_bar.grid(row=1, column=0, padx=12, pady=(0, 4), sticky="ew")

        self._strength_label = ctk.CTkLabel(
            preview_frame,
            text="",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="center",
        )
        self._strength_label.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="ew")

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=2, column=0, padx=24, pady=(14, 0), sticky="ew")
        controls.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            controls,
            text="Longitud:",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        ).grid(row=0, column=0, sticky="w")

        self._length_value_label = ctk.CTkLabel(
            controls,
            text="16",
            font=("Consolas", 11, "bold"),
            text_color=COLORS["accent"],
            width=28,
            anchor="e",
        )
        self._length_value_label.grid(row=0, column=2, sticky="e")

        self._slider = ctk.CTkSlider(
            controls,
            from_=8,
            to=64,
            number_of_steps=56,
            variable=self._length_var,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            progress_color=COLORS["accent_dim"],
            command=self._on_slider,
        )
        self._slider.grid(row=0, column=1, padx=(10, 8), sticky="ew")

        checks = ctk.CTkFrame(self, fg_color="transparent")
        checks.grid(row=3, column=0, padx=24, pady=(10, 0), sticky="ew")
        checks.grid_columnconfigure((0, 1), weight=1)

        checkbox_defs = [
            ("Mayúsculas",      self._use_upper_var),
            ("Números",         self._use_digits_var),
            ("Símbolos",        self._use_symbols_var),
            ("Evitar ambiguos", self._no_ambiguous_var),
        ]

        for i, (text, var) in enumerate(checkbox_defs):
            ctk.CTkCheckBox(
                checks,
                text=text,
                variable=var,
                font=FONTS["small"],
                text_color=COLORS["text_primary"],
                checkmark_color="#000000",
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                border_color=COLORS["border"],
                command=self._on_option_change,
            ).grid(row=i // 2, column=i % 2, sticky="w",
                   padx=(0, 8), pady=(0 if i < 2 else 0, 4))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=24, pady=(16, 20), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(
            btn_frame,
            text="Nueva",
            font=FONTS["body"],
            fg_color=COLORS["bg_secondary"],
            text_color=COLORS["text_primary"],
            hover_color=COLORS["border"],
            height=36,
            command=self._generate,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))

        ctk.CTkButton(
            btn_frame,
            text="Copiar",
            font=FONTS["body"],
            fg_color=COLORS["bg_secondary"],
            text_color=COLORS["text_primary"],
            hover_color=COLORS["border"],
            height=36,
            command=self._copy,
        ).grid(row=0, column=1, sticky="ew", padx=4)

        ctk.CTkButton(
            btn_frame,
            text="Usar contraseña",
            font=FONTS["body"],
            fg_color=COLORS["accent"],
            text_color="#000000",
            hover_color=COLORS["accent_hover"],
            height=36,
            command=self._use,
        ).grid(row=0, column=2, sticky="ew", padx=(4, 0))

    def _generate(self):
        self._current_password = generate(
            length       = self._length_var.get(),
            use_upper    = self._use_upper_var.get(),
            use_digits   = self._use_digits_var.get(),
            use_symbols  = self._use_symbols_var.get(),
            no_ambiguous = self._no_ambiguous_var.get(),
        )
        self._refresh_display()

    def _refresh_display(self):
        pw = self._current_password
        result = evaluate(pw)

        self._pass_label.configure(text=pw)

        level   = result["level"]
        entropy = result["entropy"]
        label   = result["label"]

        progress = min(level / 5, 1.0)
        color    = _STRENGTH_COLORS.get(level, COLORS["accent"])

        self._strength_bar.set(progress)
        self._strength_bar.configure(progress_color=color)
        self._strength_label.configure(
            text=f"{label}  ({entropy:.0f} bits)" if label else "",
            text_color=color,
        )

    def _on_slider(self, _value):
        self._length_value_label.configure(text=str(self._length_var.get()))
        self._generate()

    def _on_option_change(self):
        self._generate()

    def _copy(self):
        if self._current_password:
            self.clipboard_clear()
            self.clipboard_append(self._current_password)

    def _use(self):
        if self._current_password:
            self._on_insert(self._current_password)
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
