"""Gestión global de excepciones no capturadas y configuración de logging."""

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler

from app.config import DATA_DIR, LOG_FILE

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configura logging con handler de archivo rotativo y handler de consola."""
    import os
    os.makedirs(DATA_DIR, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    if root.handlers:
        return

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(
        "%(levelname)s [%(name)s] %(message)s"
    ))
    root.addHandler(console_handler)

    logger.info("Logging configurado. Archivo: %s", LOG_FILE)


class ErrorHandler:
    """
    Gestor global de excepciones no capturadas.
    Llama a install(root) una vez después de crear la ventana principal.
    """

    def __init__(self):
        self._root = None

    def install(self, root) -> None:
        self._root = root
        root.report_callback_exception = self._on_tk_error
        sys.excepthook = self._on_sys_exception
        logger.info("ErrorHandler instalado.")

    def _on_tk_error(self, exc_type, exc_value, exc_tb):
        """Captura errores en callbacks de tkinter (after, bind, command…)."""
        self._handle(exc_type, exc_value, exc_tb)

    def _on_sys_exception(self, exc_type, exc_value, exc_tb):
        """Captura errores fuera del bucle de eventos tkinter."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        self._handle(exc_type, exc_value, exc_tb)

    def _handle(self, exc_type, exc_value, exc_tb):
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        tb_str   = "".join(tb_lines)
        summary  = f"{exc_type.__name__}: {exc_value}"

        logger.error("Excepción no capturada:\n%s", tb_str)

        if self._root and self._root.winfo_exists():
            try:
                self._root.after(0, lambda: self._show_dialog(summary, tb_str))
            except Exception:
                pass

    def _show_dialog(self, summary: str, detail: str) -> None:
        import customtkinter as ctk
        from app.config import COLORS, FONTS

        dialog = ctk.CTkToplevel(self._root)
        dialog.title("Error inesperado")
        dialog.resizable(False, False)
        dialog.configure(fg_color=COLORS["bg_primary"])
        dialog.grab_set()
        dialog.lift()
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog, text="Ha ocurrido un error inesperado",
            font=FONTS["heading"], text_color=COLORS["danger"], anchor="w",
        ).grid(row=0, column=0, padx=24, pady=(22, 4), sticky="w")

        ctk.CTkLabel(
            dialog,
            text="La aplicación intentará continuar con normalidad.\n"
                 f"El error ha sido registrado en: {LOG_FILE}",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
            anchor="w", justify="left", wraplength=420,
        ).grid(row=1, column=0, padx=24, pady=(0, 14), sticky="w")

        err_card = ctk.CTkFrame(
            dialog, fg_color=COLORS["bg_card"],
            corner_radius=8, border_width=1, border_color=COLORS["border"],
        )
        err_card.grid(row=2, column=0, padx=24, pady=(0, 0), sticky="ew")

        ctk.CTkLabel(
            err_card, text=summary,
            font=FONTS["mono"], text_color=COLORS["danger"],
            anchor="w", justify="left", wraplength=408,
        ).pack(padx=12, pady=10, anchor="w")

        detail_box = ctk.CTkTextbox(
            dialog, height=150,
            font=("Consolas", 9),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_secondary"],
            border_color=COLORS["border"], border_width=1,
            wrap="none",
        )
        detail_box.insert("1.0", detail)
        detail_box.configure(state="disabled")

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.grid(row=4, column=0, padx=24, pady=(12, 18), sticky="ew")
        btn_row.grid_columnconfigure(1, weight=1)

        _expanded = [False]

        def toggle_detail():
            if _expanded[0]:
                detail_box.grid_remove()
                dialog.geometry(f"460x{_H_COLLAPSED}")
                detail_btn.configure(text="Ver detalles")
                _expanded[0] = False
            else:
                detail_box.grid(row=3, column=0, padx=24, pady=(10, 0), sticky="ew")
                dialog.geometry(f"460x{_H_EXPANDED}")
                detail_btn.configure(text="Ocultar detalles")
                _expanded[0] = True

        detail_btn = ctk.CTkButton(
            btn_row, text="Ver detalles",
            font=FONTS["small"], height=30, width=124, corner_radius=6,
            fg_color=COLORS["bg_card"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"],
            command=toggle_detail,
        )
        detail_btn.grid(row=0, column=0)

        ctk.CTkButton(
            btn_row, text="Cerrar",
            font=FONTS["body"], height=30, width=90, corner_radius=6,
            fg_color=COLORS["accent"], text_color="#000000",
            hover_color=COLORS["accent_hover"],
            command=dialog.destroy,
        ).grid(row=0, column=2)

        _H_COLLAPSED = 230
        _H_EXPANDED  = 400

        dialog.update_idletasks()
        if self._root.winfo_exists():
            rx = self._root.winfo_x()
            ry = self._root.winfo_y()
            rw = self._root.winfo_width()
            rh = self._root.winfo_height()
            x  = rx + (rw - 460) // 2
            y  = ry + (rh - _H_COLLAPSED) // 2
            dialog.geometry(f"460x{_H_COLLAPSED}+{x}+{y}")
        else:
            dialog.geometry(f"460x{_H_COLLAPSED}")
