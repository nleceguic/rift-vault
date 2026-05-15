"""Vista principal de gestión de cuentas con grid responsivo y paginación."""

import customtkinter as ctk
from app.core.account import Account
from app.core.account_service import AccountService
from app.ui.components.account_card import AccountCard
from app.ui.components.account_form_dialog import AccountFormDialog
from app.ui.components.filter_bar import FilterBar
from app.config import COLORS, FONTS
from app.core.event_bus import EventBus
from app.ui.anim import dialog_fade_in


class AccountsView(ctk.CTkFrame):

    PAGE_SIZE      = 24   # tarjetas por página; oculto si hay ≤ PAGE_SIZE cuentas
    _CARD_MIN_WIDTH = 220  # ancho mínimo de cada card en px — determina el nº de columnas
    _GRID_COLS_MIN  = 1
    _GRID_COLS_MAX  = 5

    def __init__(self, parent, service: AccountService, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._service    = service
        self._bus        = EventBus.instance()
        self._cards: list[AccountCard] = []
        self._anim_jobs: list[int] = []
        self._page       = 0
        self._grid_cols  = 3
        self._resize_job = None
        self._filter_debounce_job = None
        self._build()
        self.refresh()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Mis Cuentas",
            font=FONTS["title"], text_color=COLORS["text_primary"], anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header, text="  Anadir cuenta",
            font=FONTS["body"], fg_color=COLORS["accent"],
            text_color="#000000", hover_color=COLORS["accent_hover"],
            height=36, corner_radius=8,
            command=self._open_create_dialog,
        ).grid(row=0, column=1)

        self._filter_bar = FilterBar(self, on_change=self._on_filter_change)
        self._filter_bar.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent_dim"],
        )
        self._scroll.grid(row=2, column=0, sticky="nsew", padx=(20, 8), pady=(0, 0))
        self._scroll._scrollbar.grid_configure(padx=(0, 0))
        for col in range(self._GRID_COLS_MAX):
            self._scroll.grid_columnconfigure(
                col, weight=1 if col < self._grid_cols else 0)
        self._scroll.bind("<Configure>", self._on_scroll_resize)

        self._pag_frame = ctk.CTkFrame(
            self, fg_color=COLORS["bg_primary"], corner_radius=0, height=44,
        )
        self._pag_frame.grid(row=3, column=0, sticky="ew", padx=0, pady=0)
        self._pag_frame.grid_propagate(False)
        self._pag_frame.grid_columnconfigure(1, weight=1)
        self._pag_frame.grid_remove()

        self._prev_btn = ctk.CTkButton(
            self._pag_frame, text="← Anterior",
            font=FONTS["small"], width=110, height=30, corner_radius=6,
            fg_color=COLORS["bg_card"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"],
            command=self._prev_page,
        )
        self._prev_btn.grid(row=0, column=0, padx=(20, 0), pady=7)

        self._pag_label = ctk.CTkLabel(
            self._pag_frame, text="",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
        )
        self._pag_label.grid(row=0, column=1, pady=7)

        self._next_btn = ctk.CTkButton(
            self._pag_frame, text="Siguiente →",
            font=FONTS["small"], width=110, height=30, corner_radius=6,
            fg_color=COLORS["bg_card"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"],
            command=self._next_page,
        )
        self._next_btn.grid(row=0, column=2, padx=(0, 20), pady=7)

    def focus_search(self):
        """Enfoca el campo de búsqueda de la barra de filtros."""
        if hasattr(self, "_filter_bar"):
            self._filter_bar.focus_search()

    def _on_scroll_resize(self, event):
        if self._resize_job:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(120, lambda: self._apply_cols(event.width))

    def _apply_cols(self, width: int):
        self._resize_job = None
        cols = max(self._GRID_COLS_MIN,
                   min(self._GRID_COLS_MAX, width // self._CARD_MIN_WIDTH))
        if cols == self._grid_cols:
            return
        self._grid_cols = cols
        for c in range(self._GRID_COLS_MAX):
            self._scroll.grid_columnconfigure(
                c, weight=1 if c < cols else 0)
        self._re_render()

    def refresh(self):
        state = self._filter_bar.get_state() if hasattr(self, "_filter_bar") else {}
        try:
            self._render(**state) if state else self._render()
        except RuntimeError as e:
            self._show_integrity_error(str(e))
        if hasattr(self, "_filter_bar"):
            try:
                self._filter_bar.update_available_tags(self._service.get_all_tags())
            except RuntimeError:
                pass

    def _render(self, query="", region="Todas", tags=None, sort="alias_asc"):
        for job in self._anim_jobs:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._anim_jobs.clear()

        for card in self._cards:
            card.destroy()
        self._cards.clear()
        for widget in self._scroll.winfo_children():
            widget.destroy()

        accounts = self._service.search_filtered(
            query=query, region=region, tags=tags or [], sort=sort)

        total       = len(accounts)
        total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._page  = min(self._page, total_pages - 1)

        if not accounts:
            self._render_empty(bool(query or region != "Todas" or tags))
            self._pag_frame.grid_remove()
            return

        page_start   = self._page * self.PAGE_SIZE
        page_accounts = accounts[page_start : page_start + self.PAGE_SIZE]

        for idx, account in enumerate(page_accounts):
            row = idx // self._grid_cols
            col = idx  % self._grid_cols
            card = AccountCard(
                self._scroll, account=account,
                on_edit=self._open_edit_dialog,
                on_delete=self._confirm_delete,
            )
            delay = min(idx * 20, 280)
            card.grid_remove()
            job = self.after(delay, lambda c=card, r=row, cl=col: self._show_card(c, r, cl))
            self._anim_jobs.append(job)
            self._cards.append(card)

        self._update_pagination(self._page, total_pages, total)

    def _show_card(self, card: AccountCard, row: int, col: int):
        if card.winfo_exists():
            card.grid(row=row, column=col, padx=(0, 6), pady=6, sticky="new")
            card.animate_in()

    def _render_empty(self, has_filters: bool):
        frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        frame.grid(row=0, column=0, columnspan=self._grid_cols,
                   pady=40, padx=40, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)

        if has_filters:
            icon, title = "", "Sin resultados"
            msg      = "No hay cuentas que coincidan con los filtros activos.\nPrueba a cambiar o limpiar los filtros."
            btn_text = "Limpiar filtros"
            btn_cmd  = self._filter_bar.clear_all
        else:
            icon, title = "", "No hay cuentas todavia"
            msg      = "Anade tu primera cuenta de League of Legends\npara empezar a gestionarlas de forma segura."
            btn_text = "  Anadir primera cuenta"
            btn_cmd  = self._open_create_dialog

        ctk.CTkLabel(frame, text=icon, font=("Segoe UI Emoji", 52)).grid(
            row=0, column=0, pady=(0, 12))
        ctk.CTkLabel(
            frame, text=title,
            font=FONTS["heading"], text_color=COLORS["text_primary"],
        ).grid(row=1, column=0)
        ctk.CTkLabel(
            frame, text=msg,
            font=FONTS["body"], text_color=COLORS["text_secondary"], wraplength=380,
        ).grid(row=2, column=0, pady=(6, 20))
        ctk.CTkButton(
            frame, text=btn_text,
            font=FONTS["body"], fg_color=COLORS["accent"],
            text_color="#000000", hover_color=COLORS["accent_hover"],
            height=36, corner_radius=8, command=btn_cmd,
        ).grid(row=3, column=0)

    def _update_pagination(self, page: int, total_pages: int, total: int):
        if total_pages <= 1:
            self._pag_frame.grid_remove()
            return

        self._pag_frame.grid()

        start = page * self.PAGE_SIZE + 1
        end   = min((page + 1) * self.PAGE_SIZE, total)
        self._pag_label.configure(
            text=f"{start}–{end} de {total} cuentas  ·  Página {page + 1} / {total_pages}"
        )

        if page > 0:
            self._prev_btn.configure(
                state="normal", text_color=COLORS["text_secondary"],
                fg_color=COLORS["bg_card"],
            )
        else:
            self._prev_btn.configure(
                state="disabled", text_color=COLORS["border"],
                fg_color="transparent",
            )

        if page < total_pages - 1:
            self._next_btn.configure(
                state="normal", text_color=COLORS["text_secondary"],
                fg_color=COLORS["bg_card"],
            )
        else:
            self._next_btn.configure(
                state="disabled", text_color=COLORS["border"],
                fg_color="transparent",
            )

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._re_render()

    def _next_page(self):
        self._page += 1
        self._re_render()

    def _re_render(self):
        """Re-renderiza la página actual manteniendo los filtros activos."""
        state = self._filter_bar.get_state() if hasattr(self, "_filter_bar") else {}
        try:
            self._render(**state) if state else self._render()
        except RuntimeError as e:
            self._show_integrity_error(str(e))

    def _on_filter_change(self, query="", region="Todas", tags=None, sort="alias_asc"):
        self._page = 0
        if self._filter_debounce_job:
            try:
                self.after_cancel(self._filter_debounce_job)
            except Exception:
                pass
        self._filter_debounce_job = self.after(
            150, lambda: self._render(query=query, region=region, tags=tags or [], sort=sort)
        )

    def _open_create_dialog(self):
        AccountFormDialog(
            parent=self.winfo_toplevel(),
            on_submit=self._handle_create,
            available_tags=self._service.get_all_tags(),
        )

    def _open_edit_dialog(self, account: Account):
        AccountFormDialog(
            parent=self.winfo_toplevel(),
            on_submit=lambda data: self._handle_edit(account, data),
            account=account,
            available_tags=self._service.get_all_tags(),
        )

    def _handle_create(self, data: dict):
        try:
            self._service.create(**data)
            self.refresh()
            self._bus.emit("accounts.changed", count=len(self._service.get_all()))
        except ValueError as e:
            self._show_error(str(e))

    def _handle_edit(self, account: Account, data: dict):
        try:
            if not data.get("password"):
                data.pop("password", None)
            self._service.update(account, **data)
            self.refresh()
            self._bus.emit("accounts.changed", count=len(self._service.get_all()))
        except ValueError as e:
            self._show_error(str(e))

    def _confirm_delete(self, account: Account):
        dialog = ctk.CTkToplevel(self.winfo_toplevel())
        dialog.title("Confirmar eliminacion")
        dialog.geometry("360x160")
        dialog.resizable(False, False)
        dialog.configure(fg_color=COLORS["bg_primary"])
        dialog.grab_set()
        dialog.focus_set()
        dialog.after(50, lambda: self._center_dialog(dialog))

        ctk.CTkLabel(
            dialog, text=f"Eliminar la cuenta '{account.alias}'?",
            font=FONTS["body"], text_color=COLORS["text_primary"], wraplength=320,
        ).pack(pady=(28, 8), padx=24)
        ctk.CTkLabel(
            dialog, text="Esta accion no se puede deshacer.",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
        ).pack()

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=16, padx=24, fill="x")

        ctk.CTkButton(
            btn_row, text="Cancelar",
            fg_color=COLORS["bg_card"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"], font=FONTS["body"], height=36,
            command=dialog.destroy,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="Eliminar",
            fg_color=COLORS["danger"], text_color="#ffffff",
            hover_color=COLORS["danger_hover"], font=FONTS["body"], height=36,
            command=lambda: self._handle_delete(account, dialog),
        ).pack(side="left", expand=True, fill="x", padx=(6, 0))
        dialog_fade_in(dialog)

    def _handle_delete(self, account: Account, dialog):
        dialog.destroy()
        self._service.delete(account.id)
        self.refresh()
        self._bus.emit("accounts.changed", count=len(self._service.get_all()))

    def _show_error(self, message: str):
        dialog = ctk.CTkToplevel(self.winfo_toplevel())
        dialog.title("Error")
        dialog.geometry("340x140")
        dialog.resizable(False, False)
        dialog.configure(fg_color=COLORS["bg_primary"])
        dialog.grab_set()
        dialog.after(50, lambda: self._center_dialog(dialog))

        ctk.CTkLabel(
            dialog, text=message,
            font=FONTS["body"], text_color=COLORS["danger"], wraplength=300,
        ).pack(pady=(28, 16), padx=24)
        ctk.CTkButton(
            dialog, text="OK",
            fg_color=COLORS["accent"], text_color="#000000",
            font=FONTS["body"], height=34, command=dialog.destroy,
        ).pack()
        dialog_fade_in(dialog)

    def _show_integrity_error(self, message: str):
        dialog = ctk.CTkToplevel(self.winfo_toplevel())
        dialog.title("Advertencia de seguridad")
        dialog.geometry("420x220")
        dialog.resizable(False, False)
        dialog.configure(fg_color=COLORS["bg_primary"])
        dialog.grab_set()
        dialog.after(50, lambda: self._center_dialog(dialog))

        ctk.CTkLabel(
            dialog, text="Posible manipulacion del archivo de datos",
            font=FONTS["heading"], text_color=COLORS["danger"],
        ).pack(pady=(24, 8), padx=24)
        ctk.CTkLabel(
            dialog, text=message,
            font=FONTS["small"], text_color=COLORS["text_secondary"], wraplength=380,
        ).pack(padx=24)
        ctk.CTkButton(
            dialog, text="Entendido",
            fg_color=COLORS["danger"], text_color="#ffffff",
            font=FONTS["body"], height=36, command=dialog.destroy,
        ).pack(pady=20)
        dialog_fade_in(dialog)

    def _center_dialog(self, dialog):
        dialog.update_idletasks()
        root = self.winfo_toplevel()
        x = root.winfo_x() + (root.winfo_width()  - dialog.winfo_width())  // 2
        y = root.winfo_y() + (root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
