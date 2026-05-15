"""
filter_bar.py - Barra de busqueda + filtros + chips de filtros activos.

Emite on_change(query, region, tags, sort) cada vez que cualquier
parametro cambia. AccountsView se suscribe y refresca la lista.

Parametros emitidos:
  query  : str        - texto de busqueda libre / operadores avanzados
  region : str        - "Todas" o codigo de region ("EUW", "NA"...)
  tags   : list[str]  - lista de tags a filtrar (AND logico)
  sort   : str        - "alias_asc" | "alias_desc" | "reciente" | "antiguo"

Búsqueda avanzada (P2-07):
  Operadores: alias:X  region:EUW  tag:ranked  before:2025-01-01
  Historial:  se muestra al enfocar el campo vacío (≤10 búsquedas)
  Fuzzy:      el texto libre tolera errores tipográficos menores
"""

import customtkinter as ctk
from typing import Callable

from app.core.account import VALID_REGIONS
from app.config import COLORS, FONTS

SORT_OPTIONS = {
    "Alias AZ":   "alias_asc",
    "Alias ZA":   "alias_desc",
    "Mas reciente": "reciente",
    "Mas antiguo":  "antiguo",
}

ALL_REGIONS         = ["Todas"] + VALID_REGIONS
_MAX_HISTORY_SHOWN  = 6
_OPERATOR_HINT      = "alias:X  region:EUW  tag:Y  before:YYYY-MM-DD"


def _get_settings():
    try:
        from app.core.service_registry import ServiceRegistry
        from app.core.settings_service import SettingsService
        return ServiceRegistry.instance().get(SettingsService)
    except Exception:
        return None


class FilterBar(ctk.CTkFrame):
    """
    Barra de filtros completa con búsqueda avanzada e historial.
    """

    def __init__(self, parent, on_change: Callable, available_tags: list[str] = None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._on_change      = on_change
        self._available_tags = available_tags or []
        self._active_tags:   list[str] = []
        self._chips:         list[ctk.CTkButton] = []
        self._history_frame: ctk.CTkFrame | None = None
        self._history_btns:  list[ctk.CTkButton] = []

        self.grid_columnconfigure(0, weight=1)
        self._build_search_row()
        self._build_chips_row()

    def _build_search_row(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew")
        row.grid_columnconfigure(0, weight=1)

        self._query_var = ctk.StringVar()
        self._query_var.trace_add("write", self._on_query_write)

        self._search_entry = ctk.CTkEntry(
            row,
            textvariable=self._query_var,
            placeholder_text="  Buscar...  ·  alias:X  region:EUW  tag:Y  before:YYYY",
            font=FONTS["body"],
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            height=38,
            corner_radius=8,
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._search_entry.bind("<FocusIn>",  self._on_entry_focus)
        self._search_entry.bind("<FocusOut>", lambda e: self.after(150, self._hide_history))
        self._search_entry.bind("<Return>",   self._on_enter)
        self._search_entry.bind("<Escape>",   lambda e: self._hide_history())
        self._search_entry.bind("<Down>",     self._history_nav_down)
        self._search_entry.bind("<Up>",       self._history_nav_up)

        self._region_var = ctk.StringVar(value="Todas")
        self._region_var.trace_add("write", lambda *_: self._emit())

        ctk.CTkOptionMenu(
            row,
            values=ALL_REGIONS,
            variable=self._region_var,
            font=FONTS["small"],
            fg_color=COLORS["bg_card"],
            button_color=COLORS["accent_dim"],
            button_hover_color=COLORS["accent"],
            dropdown_fg_color=COLORS["bg_card"],
            width=100,
            height=38,
        ).grid(row=0, column=1, padx=(0, 8))

        self._sort_var = ctk.StringVar(value="Alias AZ")
        self._sort_var.trace_add("write", lambda *_: self._emit())

        ctk.CTkOptionMenu(
            row,
            values=list(SORT_OPTIONS.keys()),
            variable=self._sort_var,
            font=FONTS["small"],
            fg_color=COLORS["bg_card"],
            button_color=COLORS["accent_dim"],
            button_hover_color=COLORS["accent"],
            dropdown_fg_color=COLORS["bg_card"],
            width=130,
            height=38,
        ).grid(row=0, column=2)

    def _build_chips_row(self):
        self._chips_frame = ctk.CTkFrame(self, fg_color="transparent")

    def focus_search(self):
        self._search_entry.focus_set()
        self._search_entry.select_range(0, "end")

    def update_available_tags(self, tags: list[str]):
        self._available_tags = sorted(set(tags))

    def get_state(self) -> dict:
        return {
            "query":  self._query_var.get().strip(),
            "region": self._region_var.get(),
            "tags":   list(self._active_tags),
            "sort":   SORT_OPTIONS.get(self._sort_var.get(), "alias_asc"),
        }

    def clear_all(self):
        self._query_var.set("")
        self._region_var.set("Todas")
        self._sort_var.set("Alias AZ")
        self._active_tags.clear()
        self._refresh_chips()
        self._emit()

    def add_tag_filter(self, tag: str):
        if tag and tag not in self._active_tags:
            self._active_tags.append(tag)
            self._refresh_chips()
            self._emit()

    def remove_tag_filter(self, tag: str):
        if tag in self._active_tags:
            self._active_tags.remove(tag)
            self._refresh_chips()
            self._emit()

    def _on_entry_focus(self, _event=None):
        """Muestra el historial si el campo está vacío."""
        if not self._query_var.get().strip():
            self._show_history()

    def _on_query_write(self, *_):
        """Callback de trace: emite y gestiona el historial."""
        text = self._query_var.get()
        if not text.strip():
            self._show_history()
        else:
            self._hide_history()
        self._emit()

    def _on_enter(self, _event=None):
        """Guarda la búsqueda actual en el historial."""
        query = self._query_var.get().strip()
        if query:
            s = _get_settings()
            if s:
                s.add_recent_search(query)
        self._hide_history()
        return "break"

    def _show_history(self):
        self._hide_history()
        s = _get_settings()
        if not s:
            return
        searches = s.recent_searches
        if not searches:
            return

        dialog = self._search_entry.winfo_toplevel()
        self._search_entry.update_idletasks()

        ex = self._search_entry.winfo_rootx() - dialog.winfo_rootx()
        ey = self._search_entry.winfo_rooty() - dialog.winfo_rooty() + self._search_entry.winfo_height() + 2
        ew = self._search_entry.winfo_width()

        frame = ctk.CTkFrame(
            dialog,
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=6,
        )

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=6, pady=(6, 2))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Búsquedas recientes",
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header, text="Borrar",
            font=("Segoe UI", 9),
            fg_color="transparent",
            text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"],
            width=40, height=18, corner_radius=4,
            command=self._clear_history,
        ).grid(row=0, column=1, sticky="e")

        self._history_btns = []
        self._history_sel  = -1

        for q in searches[:_MAX_HISTORY_SHOWN]:
            btn = ctk.CTkButton(
                frame,
                text=q,
                font=FONTS["small"],
                anchor="w",
                fg_color="transparent",
                text_color=COLORS["text_primary"],
                hover_color=COLORS["bg_secondary"],
                height=28,
                corner_radius=4,
                command=lambda v=q: self._select_history(v),
            )
            btn.pack(fill="x", padx=4, pady=1)
            self._history_btns.append(btn)

        frame.place(x=ex, y=ey, width=ew)
        frame.lift()
        self._history_frame = frame

    def _hide_history(self):
        if self._history_frame is not None:
            try:
                self._history_frame.destroy()
            except Exception:
                pass
            self._history_frame = None
        self._history_btns = []
        self._history_sel  = -1

    def _select_history(self, query: str):
        self._query_var.set(query)
        self._hide_history()
        self._search_entry.focus_set()
        self._emit()

    def _clear_history(self):
        s = _get_settings()
        if s:
            s.clear_recent_searches()
        self._hide_history()

    def _history_nav_down(self, _event):
        if not self._history_btns:
            return
        self._history_sel = min(self._history_sel + 1, len(self._history_btns) - 1)
        self._highlight_history()
        return "break"

    def _history_nav_up(self, _event):
        if not self._history_btns:
            return
        self._history_sel = max(self._history_sel - 1, -1)
        self._highlight_history()
        return "break"

    def _highlight_history(self):
        for i, btn in enumerate(self._history_btns):
            if i == self._history_sel:
                btn.configure(fg_color=COLORS["accent"], text_color="#000000")
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_primary"])

    def _refresh_chips(self):
        for chip in self._chips:
            chip.destroy()
        self._chips.clear()

        region = self._region_var.get()
        active = []
        if region != "Todas":
            active.append(("region", region, f" {region}"))
        for tag in self._active_tags:
            active.append(("tag", tag, f"#{tag}"))

        if not active:
            self._chips_frame.grid_remove()
            return

        self._chips_frame.grid(row=1, column=0, sticky="w", pady=(6, 0))

        ctk.CTkLabel(
            self._chips_frame,
            text="Filtros activos:",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        ).pack(side="left", padx=(0, 6))

        for kind, value, label in active:
            chip = ctk.CTkButton(
                self._chips_frame,
                text=f"{label}  ",
                font=FONTS["small"],
                fg_color=COLORS["bg_secondary"],
                text_color=COLORS["accent"],
                hover_color=COLORS["bg_card"],
                border_width=1,
                border_color=COLORS["accent_dim"],
                height=24,
                corner_radius=12,
                command=lambda k=kind, v=value: self._remove_filter(k, v),
            )
            chip.pack(side="left", padx=(0, 4))
            self._chips.append(chip)

        clear_btn = ctk.CTkButton(
            self._chips_frame,
            text="Limpiar todo",
            font=FONTS["small"],
            fg_color="transparent",
            text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_card"],
            height=24,
            corner_radius=12,
            command=self.clear_all,
        )
        clear_btn.pack(side="left", padx=(4, 0))
        self._chips.append(clear_btn)

    def _remove_filter(self, kind: str, value: str):
        if kind == "region":
            self._region_var.set("Todas")
        elif kind == "tag":
            self.remove_tag_filter(value)

    def _emit(self):
        self._refresh_chips()
        self._on_change(**self.get_state())
