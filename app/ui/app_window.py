"""Ventana principal de Rift Vault con sidebar, vistas y gestor de sesión."""

import logging
import sys
import time
import _tkinter

import customtkinter as ctk

logger = logging.getLogger(__name__)

from app.config import (
    APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    DEFAULT_COLOR_THEME,
    COLORS, FONTS, SIDEBAR_WIDTH, NAV_ITEMS, LOGO_PATH,
)
from app.core.event_bus             import EventBus
from app.ui.views.unlock_view       import UnlockView
from app.ui.views.home_view         import HomeView
from app.ui.views.accounts_view     import AccountsView
from app.ui.views.settings_view     import SettingsView
from app.ui.components.lock_overlay import LockOverlay


class AppWindow(ctk.CTk):
    """Ventana raiz de la aplicacion."""

    def __init__(self, registry):
        ctk.set_appearance_mode(registry.settings.theme)
        ctk.set_default_color_theme(DEFAULT_COLOR_THEME)
        super().__init__()

        self._registry        = registry
        self._bus             = EventBus.instance()
        self._clipboard_armed = False
        self._inactivity_job  = None
        self._last_activity   = None
        self._active_view_id  = ""
        self._transitioning   = False

        self._bus.subscribe("settings.changed", self._on_setting_changed)

        self.title(APP_NAME)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        try:
            from PIL import Image, ImageTk
            _icon = ImageTk.PhotoImage(Image.open(LOGO_PATH).resize((32, 32)))
            self._logo_icon = _icon
            self.after(200, lambda: self.wm_iconphoto(True, self._logo_icon))
        except Exception:
            pass
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.configure(fg_color=COLORS["bg_primary"])

        try:
            self.attributes("-alpha", 0.0)
        except Exception:
            pass
        self.after(120, self._fade_window_in)
        self._show_unlock_screen()

    def report_callback_exception(self, exc, val, tb):
        if exc is _tkinter.TclError and "bad window path name" in str(val):
            return
        sys.__excepthook__(exc, val, tb)

    def _show_unlock_screen(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._unlock_view = UnlockView(
            parent=self,
            crypto=self._registry.crypto,
            on_unlocked=self._on_unlocked,
            last_unlock_at=self._registry.settings.last_unlock_at,
        )
        self._unlock_view.grid(row=0, column=0, sticky="nsew")

    def _on_unlocked(self):
        from datetime import datetime
        self._registry.settings.previous_unlock_at = self._registry.settings.last_unlock_at
        self._registry.settings.last_unlock_at = datetime.now().isoformat(timespec="seconds")
        logger.info("Interfaz principal cargada tras desbloqueo.")
        self._bus.emit("app.unlocked")

        from app.hooks.hooks_registry import HooksRegistry
        HooksRegistry.instance().fire("after_unlock")

        self._bus.subscribe("clipboard.armed",   lambda **_: self._on_clipboard_armed())
        self._bus.subscribe("clipboard.cleared", lambda **_: self._on_clipboard_cleared())

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Move focus to AppWindow before creating the curtain CTkToplevel.
        # On Windows, CTkToplevel.__init__ calls focus_get() and schedules
        # after(10, saved_widget.focus). If the entry still has focus here,
        # that callback fires on a destroyed widget after unlock_view.destroy().
        self.focus_set()
        self.update_idletasks()
        wx, wy = self.winfo_x(), self.winfo_y()
        ww, wh = self.winfo_width(), self.winfo_height()

        curtain = ctk.CTkToplevel(self)
        curtain.overrideredirect(True)
        try:
            curtain.attributes("-alpha", 0.0)
        except Exception:
            pass
        curtain.configure(fg_color=COLORS["bg_primary"])
        curtain.geometry(f"{ww}x{wh}+{wx}+{wy}")
        curtain.lift()
        curtain.update_idletasks()
        try:
            curtain.attributes("-alpha", 1.0)
        except Exception:
            pass

        try:
            self._unlock_view.cleanup()
        except Exception:
            pass
        self._unlock_view.destroy()

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content_area()
        self._build_views()
        self._nav_buttons = {}
        self._register_nav_buttons()
        self._navigate("home")

        self._setup_inactivity_timer()
        self._setup_shortcuts()
        self.after(60, lambda: self._slide_curtain_up(curtain, wx, wy, ww, wh))

    def _setup_shortcuts(self):
        self.bind_all("<Control-n>", self._shortcut_new_account, add=True)
        self.bind_all("<Control-f>", self._shortcut_focus_search, add=True)

    def _modal_open(self) -> bool:
        """True si hay un diálogo modal activo (distinto de la ventana principal)."""
        gc = self.grab_current()
        return gc is not None and gc is not self

    def _shortcut_new_account(self, event=None):
        if self._modal_open():
            return
        self._navigate("accounts")
        self.after(50, self._views["accounts"]._open_create_dialog)

    def _shortcut_focus_search(self, event=None):
        if self._modal_open():
            return
        self._navigate("accounts")
        self.after(50, self._views["accounts"].focus_search)

    def _on_setting_changed(self, key=None, value=None, **_):
        if key == "inactivity_timeout_min":
            self._reset_inactivity_timer()
        elif key == "theme":
            ctk.set_appearance_mode(value)
            if value == "System":
                try:
                    resolved = ctk.get_appearance_mode()
                    self._bus.emit("app.theme_resolved", resolved=resolved)
                except Exception:
                    pass

    def _setup_inactivity_timer(self):
        self._last_activity = time.monotonic()
        for event in ("<Motion>", "<KeyPress>", "<ButtonPress>", "<MouseWheel>"):
            self.bind_all(event, self._on_activity, add=True)
        self._schedule_inactivity_check()

    def _on_activity(self, _event=None):
        self._last_activity = time.monotonic()

    def _schedule_inactivity_check(self):
        timeout_ms = self._registry.settings.inactivity_timeout_ms
        if timeout_ms <= 0:
            self._inactivity_job = None
            return
        elapsed_ms = (time.monotonic() - self._last_activity) * 1000
        if elapsed_ms >= timeout_ms:
            self._lock_session()
        else:
            remaining = int(timeout_ms - elapsed_ms)
            self._inactivity_job = self.after(
                min(remaining, 10_000), self._schedule_inactivity_check
            )

    def _reset_inactivity_timer(self):
        if self._last_activity is None:
            return
        if self._inactivity_job:
            try:
                self.after_cancel(self._inactivity_job)
            except Exception:
                pass
            self._inactivity_job = None
        self._last_activity = time.monotonic()
        self._schedule_inactivity_check()

    def _lock_session(self):
        self._inactivity_job = None
        logger.info("Sesión bloqueada por inactividad.")

        from app.hooks.hooks_registry import HooksRegistry
        HooksRegistry.instance().fire("before_lock")

        if self._clipboard_armed:
            try:
                self.clipboard_clear()
                self.update()
            except Exception:
                pass
            self._clipboard_armed = False
            self._bus.emit("clipboard.cleared")

        self._registry.crypto.lock()
        self._apply_capture_protection(False)

        LockOverlay(
            parent=self,
            crypto=self._registry.crypto,
            on_unlocked=self._on_session_reactivated,
        )

    def _on_session_reactivated(self):
        logger.info("Sesión reactivada tras desbloqueo de pantalla.")
        for view in getattr(self, "_views", {}).values():
            if hasattr(view, "refresh"):
                try:
                    view.refresh()
                except Exception:
                    pass
        self._reset_inactivity_timer()

    def _on_clipboard_armed(self):
        self._clipboard_armed = True
        self._apply_capture_protection(True)

    def _on_clipboard_cleared(self):
        self._clipboard_armed = False
        self._apply_capture_protection(False)

    def _apply_capture_protection(self, enabled: bool):
        from app.core.win32_utils import set_capture_protection
        set_capture_protection(self.winfo_id(), enabled)
        if hasattr(self, "_shield_label"):
            if enabled:
                self._shield_label.configure(
                    text="Proteccion activa", text_color=COLORS["success"])
            else:
                self._shield_label.configure(
                    text="", text_color=COLORS["bg_secondary"])

    def _on_close(self):
        if not self._clipboard_armed:
            logger.info("Aplicación cerrada.")
            self.destroy()
            return
        logger.warning("Cierre solicitado con contraseña en portapapeles.")

        dialog = ctk.CTkToplevel(self)
        dialog.title("Contrasena en portapapeles")
        dialog.geometry("380x170")
        dialog.resizable(False, False)
        dialog.configure(fg_color=COLORS["bg_primary"])
        dialog.grab_set()
        dialog.focus_set()
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - dialog.winfo_width())  // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            dialog,
            text="Tienes una contrasena en el portapapeles.",
            font=FONTS["body"], text_color=COLORS["accent"],
        ).pack(pady=(24, 4), padx=24)

        ctk.CTkLabel(
            dialog,
            text="Si cierras ahora quedara expuesta. Quieres limpiarla antes de salir?",
            font=FONTS["small"], text_color=COLORS["text_secondary"], wraplength=340,
        ).pack(padx=24)

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=16, padx=24, fill="x")

        def close_and_clear():
            try:
                self.clipboard_clear()
                self.update()
            except Exception:
                pass
            dialog.destroy()
            self.destroy()

        def close_without_clear():
            dialog.destroy()
            self.destroy()

        ctk.CTkButton(
            btn_row, text="Limpiar y salir",
            fg_color=COLORS["accent"], text_color="#000000",
            hover_color=COLORS["accent_hover"],
            font=FONTS["body"], height=36, command=close_and_clear,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="Salir sin limpiar",
            fg_color=COLORS["bg_card"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"],
            font=FONTS["body"], height=36, command=close_without_clear,
        ).pack(side="left", expand=True, fill="x", padx=(6, 0))

        from app.ui.anim import dialog_fade_in
        dialog_fade_in(dialog)

    def _build_sidebar(self):
        self._sidebar = ctk.CTkFrame(
            self, width=SIDEBAR_WIDTH,
            fg_color=COLORS["bg_secondary"], corner_radius=0,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsw")
        self._sidebar.grid_propagate(False)
        self._sidebar.grid_rowconfigure(10, weight=1)

        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=16, pady=(20, 8), sticky="w")

        try:
            from PIL import Image
            _img = Image.open(LOGO_PATH)
            _w, _h = _img.size
            _s = min(32 / _w, 32 / _h)
            _sbar_img = ctk.CTkImage(light_image=_img, dark_image=_img,
                                     size=(int(_w * _s), int(_h * _s)))
            ctk.CTkLabel(logo_frame, image=_sbar_img, text="").grid(
                row=0, column=0, padx=(0, 8))
            logo_frame.grid_columnconfigure(1, weight=1)
            _name_col = 1
        except Exception:
            _name_col = 0

        ctk.CTkLabel(
            logo_frame, text="Rift Vault",
            font=("Segoe UI", 16, "bold"), text_color=COLORS["accent"],
        ).grid(row=0, column=_name_col)

        ctk.CTkFrame(self._sidebar, height=1, fg_color=COLORS["border"]).grid(
            row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        self._sidebar._nav_btns = {}
        for idx, item in enumerate(NAV_ITEMS):
            btn = ctk.CTkButton(
                self._sidebar, text=item["label"], anchor="w",
                font=FONTS["body"], fg_color="transparent",
                text_color=COLORS["text_secondary"],
                hover_color=COLORS["bg_card"],
                corner_radius=8, height=40,
                command=lambda v=item["view"]: self._navigate(v),
            )
            btn.grid(row=idx + 2, column=0, padx=10, pady=3, sticky="ew")
            self._sidebar._nav_btns[item["view"]] = btn

        footer = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        footer.grid(row=11, column=0, padx=16, pady=16, sticky="sw")

        self._shield_label = ctk.CTkLabel(
            footer, text="",
            font=FONTS["small"], text_color=COLORS["bg_secondary"],
        )
        self._shield_label.pack()

        ctk.CTkLabel(
            footer, text=f"Rift Vault v{APP_VERSION}",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
        ).pack()

    def _build_content_area(self):
        self._content = ctk.CTkFrame(
            self, fg_color=COLORS["bg_primary"], corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

    def _build_views(self):
        service       = self._registry.service
        home_view     = HomeView(self._content, service=service,
                                 settings=self._registry.settings,
                                 on_navigate=self._navigate)
        accounts_view = AccountsView(self._content, service=service)

        self._bus.subscribe("accounts.changed", lambda **_: home_view.refresh())

        self._views = {
            "home":     home_view,
            "accounts": accounts_view,
            "settings": SettingsView(self._content, registry=self._registry),
        }

        for view in self._views.values():
            view.place(relx=0, rely=0, relwidth=1, relheight=1)
            view.place_forget()

    def _register_nav_buttons(self):
        self._nav_buttons = getattr(self._sidebar, "_nav_btns", {})

    def _navigate(self, view_id: str):
        if view_id == self._active_view_id or self._transitioning:
            return
        logger.debug("Navegando a vista: %s", view_id)

        view_order = list(self._views.keys())
        old_idx    = view_order.index(self._active_view_id) if self._active_view_id in view_order else -1
        new_idx    = view_order.index(view_id) if view_id in view_order else 0
        going_right = new_idx > old_idx

        old_view = self._views.get(self._active_view_id)
        new_view = self._views.get(view_id)

        if new_view and hasattr(new_view, "refresh"):
            new_view.refresh()

        if self._active_view_id in self._nav_buttons:
            self._nav_buttons[self._active_view_id].configure(
                fg_color="transparent", text_color=COLORS["text_secondary"])
        if view_id in self._nav_buttons:
            self._nav_buttons[view_id].configure(
                fg_color=COLORS["bg_card"], text_color=COLORS["accent"])

        self._active_view_id = view_id
        self._bus.emit("app.navigated", view=view_id)

        if old_view is None:
            if new_view:
                new_view.place(relx=0, rely=0, relwidth=1, relheight=1)
            return

        if new_view:
            start_relx = 1.0 if going_right else -1.0
            new_view.place(relx=start_relx, rely=0, relwidth=1, relheight=1)

        self._transitioning = True
        self._slide_views(old_view, new_view, going_right, 0)

    def _slide_views(self, old_view, new_view, going_right: bool, step: int):
        _STEPS    = 10
        _INTERVAL = 14

        t     = (step + 1) / _STEPS
        ease  = 1.0 - (1.0 - t) ** 3       # cubic ease-out
        d     = 1.0 if going_right else -1.0

        if old_view and old_view.winfo_exists():
            old_view.place(relx=-d * ease, rely=0, relwidth=1, relheight=1)
        if new_view and new_view.winfo_exists():
            new_view.place(relx=d * (1.0 - ease), rely=0, relwidth=1, relheight=1)

        if step + 1 < _STEPS:
            self.after(_INTERVAL, lambda: self._slide_views(old_view, new_view, going_right, step + 1))
        else:
            if old_view and old_view.winfo_exists():
                old_view.place_forget()
            if new_view and new_view.winfo_exists():
                new_view.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._transitioning = False

    def _fade_window_in(self, step: int = 0, steps: int = 10, interval: int = 16):
        try:
            self.attributes("-alpha", step / steps)
        except Exception:
            return
        if step < steps:
            self.after(interval, lambda: self._fade_window_in(step + 1, steps, interval))

    def _slide_curtain_up(self, curtain, x0: int, y0: int, w: int, h: int,
                          step: int = 0, steps: int = 9, interval: int = 16):
        t    = (step + 1) / steps
        ease = t * t                           # quadratic ease-in: accelerates upward
        try:
            if curtain.winfo_exists():
                curtain.geometry(f"{w}x{h}+{x0}+{y0 - round(h * ease)}")
        except Exception:
            pass
        if step + 1 < steps:
            self.after(interval, lambda: self._slide_curtain_up(
                curtain, x0, y0, w, h, step + 1, steps, interval))
        else:
            try:
                curtain.destroy()
            except Exception:
                pass
