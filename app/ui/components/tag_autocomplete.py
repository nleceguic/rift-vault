"""
tag_autocomplete.py – Entrada de tags con chips removibles y autocompletado.

Comportamiento:
  • Los tags confirmados aparecen como chips con botón ×.
  • El usuario escribe el siguiente tag en el campo de texto.
  • Separadores aceptados: coma (,) y Enter.
  • Backspace en campo vacío elimina el último chip.
  • Dropdown de sugerencias basado en los tags disponibles.
  • La var externa (textvariable) siempre refleja el estado completo.
"""

import customtkinter as ctk
from app.config import COLORS, FONTS

_MAX_SUGGESTIONS = 6


class TagAutocompleteEntry(ctk.CTkFrame):
    """
    Drop-in replacement de CTkEntry para campos de tags.

    Uso:
        entry = TagAutocompleteEntry(parent, available_tags=[...], textvariable=var)
        entry.grid(...)
        value = var.get()   # "ranked, smurf, ..."
    """

    def __init__(
        self,
        parent,
        available_tags:   list[str] = None,
        textvariable:     ctk.StringVar = None,
        height:           int = 36,
        placeholder_text: str = "Escribe y presiona Enter o coma",
        **kwargs,
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self._available_original: list[str] = list(available_tags or [])
        self._available_lower:    list[str] = [t.lower() for t in self._available_original]

        # Var externa — mantenida en sincronía
        self._var         = textvariable if textvariable is not None else ctk.StringVar()
        # Var interna — solo el texto del campo (prefijo actual)
        self._input_var   = ctk.StringVar()
        self._tags: list[str] = [t.strip() for t in self._var.get().split(",") if t.strip()]

        self._dropdown:    ctk.CTkFrame | None = None
        self._suggestions: list[str] = []
        self._btns:        list[ctk.CTkButton] = []
        self._sel_idx:     int = -1
        self._suppressing: bool = False
        self._height       = height

        self._wrapper = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_card"],
            border_width=2,
            border_color=COLORS["border"],
            corner_radius=8,
        )
        self._wrapper.grid(row=0, column=0, sticky="ew")
        self._wrapper.grid_columnconfigure(0, weight=1)

        # Fila de chips (row 0, colapsada cuando no hay tags)
        self._chips_row = ctk.CTkFrame(self._wrapper, fg_color="transparent")
        self._chips_row.grid(row=0, column=0, sticky="ew", padx=6)

        self._entry = ctk.CTkEntry(
            self._wrapper,
            textvariable=self._input_var,
            font=FONTS["body"],
            fg_color="transparent",
            border_width=0,
            placeholder_text=placeholder_text,
            height=height,
        )
        self._entry.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 2))

        self._input_var.trace_add("write", self._on_input_change)
        self._entry.bind("<Down>",      self._nav_down)
        self._entry.bind("<Up>",        self._nav_up)
        self._entry.bind("<Return>",    self._on_return)
        self._entry.bind("<Escape>",    lambda e: self._hide())
        self._entry.bind("<FocusOut>",  lambda e: self.after(150, self._hide))
        self._entry.bind("<BackSpace>", self._on_backspace)

        self._refresh_chips()

    def get(self) -> str:
        """Devuelve todos los tags (confirmados + prefijo parcial si existe)."""
        partial  = self._input_var.get().strip()
        all_tags = self._tags + ([partial] if partial else [])
        return ", ".join(all_tags)

    def set_available_tags(self, tags: list[str]) -> None:
        self._available_original = list(tags)
        self._available_lower    = [t.lower() for t in tags]

    def _add_tag(self, tag: str) -> None:
        tag = tag.strip()
        if not tag or tag.lower() in {t.lower() for t in self._tags}:
            return
        self._tags.append(tag)
        self._refresh_chips()
        self._sync_var()

    def _remove_tag(self, tag: str) -> None:
        self._tags = [t for t in self._tags if t.lower() != tag.lower()]
        self._refresh_chips()
        self._sync_var()
        self._entry.focus_set()

    def _sync_var(self) -> None:
        """Mantiene la var externa sincronizada con el estado interno."""
        partial  = self._input_var.get().strip()
        all_tags = self._tags + ([partial] if partial else [])
        self._suppressing = True
        self._var.set(", ".join(all_tags))
        self._suppressing = False

    def _refresh_chips(self) -> None:
        for widget in self._chips_row.winfo_children():
            widget.destroy()

        for tag in self._tags:
            chip = ctk.CTkFrame(
                self._chips_row,
                fg_color=COLORS["bg_secondary"],
                corner_radius=12,
                border_width=1,
                border_color=COLORS["accent_dim"],
            )
            chip.pack(side="left", padx=(0, 4), pady=4)

            ctk.CTkLabel(
                chip, text=tag,
                font=FONTS["small"], text_color=COLORS["accent"],
            ).pack(side="left", padx=(8, 2), pady=(2, 2))

            ctk.CTkButton(
                chip, text="×",
                font=("Segoe UI", 11),
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
                hover_color=COLORS["danger"],
                hover=True,
                width=20, height=20, corner_radius=10,
                command=lambda t=tag: self._remove_tag(t),
            ).pack(side="left", padx=(0, 4), pady=(2, 2))

    def _on_input_change(self, *_) -> None:
        if self._suppressing:
            return
        text = self._input_var.get()

        if "," in text:
            parts = [p.strip() for p in text.split(",")]
            for tag in parts[:-1]:
                if tag:
                    self._add_tag(tag)
            self._suppressing = True
            self._input_var.set(parts[-1].lstrip())
            self._suppressing = False
            self._hide()
            return

        self._sync_var()

        prefix = text.strip()
        if not prefix:
            self._hide()
            return

        already = {t.lower() for t in self._tags}
        suggestions = [
            orig for orig, low in zip(self._available_original, self._available_lower)
            if low.startswith(prefix.lower()) and low not in already
        ]
        if suggestions:
            self._show(suggestions[:_MAX_SUGGESTIONS])
        else:
            self._hide()

    def _on_return(self, _event):
        if self._sel_idx >= 0 and self._suggestions:
            self._select(self._suggestions[self._sel_idx])
            return "break"
        text = self._input_var.get().strip()
        if text:
            self._add_tag(text)
            self._suppressing = True
            self._input_var.set("")
            self._suppressing = False
            self._hide()
        return "break"

    def _on_backspace(self, _event):
        if not self._input_var.get() and self._tags:
            self._remove_tag(self._tags[-1])
            return "break"

    def _show(self, suggestions: list[str]) -> None:
        self._hide()
        self._suggestions = suggestions
        self._sel_idx     = -1
        self._btns        = []

        dialog = self.winfo_toplevel()
        self._entry.update_idletasks()

        ex = self._entry.winfo_rootx() - dialog.winfo_rootx()
        ey = self._entry.winfo_rooty() - dialog.winfo_rooty() + self._entry.winfo_height() + 2
        ew = self._entry.winfo_width()

        self._dropdown = ctk.CTkFrame(
            dialog,
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=6,
        )

        for tag in suggestions:
            btn = ctk.CTkButton(
                self._dropdown,
                text=tag,
                font=FONTS["small"],
                anchor="w",
                fg_color="transparent",
                text_color=COLORS["text_primary"],
                hover_color=COLORS["bg_secondary"],
                height=28,
                corner_radius=4,
                command=lambda t=tag: self._select(t),
            )
            btn.pack(fill="x", padx=4, pady=2)
            self._btns.append(btn)

        self._dropdown.place(x=ex, y=ey, width=ew)
        self._dropdown.lift()

    def _hide(self) -> None:
        if self._dropdown is not None:
            try:
                self._dropdown.destroy()
            except Exception:
                pass
            self._dropdown = None
        self._suggestions = []
        self._btns        = []
        self._sel_idx     = -1

    def _select(self, tag: str) -> None:
        self._add_tag(tag)
        self._suppressing = True
        self._input_var.set("")
        self._suppressing = False
        self._hide()
        self._entry.focus_set()

    def _nav_down(self, _event):
        if not self._suggestions:
            return
        self._sel_idx = min(self._sel_idx + 1, len(self._suggestions) - 1)
        self._highlight()
        return "break"

    def _nav_up(self, _event):
        if not self._suggestions:
            return
        self._sel_idx = max(self._sel_idx - 1, -1)
        self._highlight()
        return "break"

    def _highlight(self) -> None:
        for i, btn in enumerate(self._btns):
            if i == self._sel_idx:
                btn.configure(fg_color=COLORS["accent"], text_color="#000000")
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_primary"])
