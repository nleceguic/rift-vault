"""Vista de configuración: seguridad, apariencia y datos."""

import customtkinter as ctk

from app.config import COLORS, FONTS, DATA_DIR, APP_NAME
from app.core.event_bus import EventBus

_RESOLVED_LABEL = {"Dark": "Oscuro", "Light": "Claro"}


_TIMEOUT_OPTIONS = ["Desactivado", "5 min", "10 min", "15 min", "30 min", "60 min"]
_TIMEOUT_MAP     = {"Desactivado": 0, "5 min": 5, "10 min": 10,
                    "15 min": 15, "30 min": 30, "60 min": 60}
_THEME_LABELS    = {"Dark": "Oscuro", "System": "Sistema", "Light": "Claro"}
_THEME_VALUES    = {"Oscuro": "Dark", "Sistema": "System", "Claro": "Light"}


class SettingsView(ctk.CTkFrame):
    """Vista completa de ajustes de la aplicación."""

    def __init__(self, parent, registry):
        super().__init__(parent, fg_color=COLORS["bg_primary"], corner_radius=0)
        self._registry = registry
        self._settings = registry.settings
        self._bus      = EventBus.instance()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg_primary"], corner_radius=0,
        )
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            scroll, text="Ajustes",
            font=FONTS["title"], text_color=COLORS["text_primary"], anchor="w",
        ).grid(row=0, column=0, padx=32, pady=(28, 4), sticky="w")

        ctk.CTkLabel(
            scroll, text=f"Personaliza {APP_NAME} según tus preferencias.",
            font=FONTS["body"], text_color=COLORS["text_secondary"], anchor="w",
        ).grid(row=1, column=0, padx=32, pady=(0, 24), sticky="w")

        r = 2
        r = self._section(scroll, r, "Seguridad",  self._build_security)
        r = self._section(scroll, r, "Apariencia", self._build_appearance)
        r = self._section(scroll, r, "Riot API",   self._build_riot)
        r = self._section(scroll, r, "Lanzador",   self._build_launcher)
        r = self._section(scroll, r, "Datos",      self._build_data)

        ctk.CTkFrame(scroll, height=32, fg_color="transparent").grid(row=r, column=0)

    def _section(self, parent, row: int, title: str, builder) -> int:
        """Pinta encabezado de sección + tarjeta y llama a builder(card)."""
        ctk.CTkLabel(
            parent,
            text=title.upper(),
            font=("Segoe UI", 10, "bold"),
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=row, column=0, padx=32, pady=(20, 6), sticky="w")

        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=row + 1, column=0, padx=24, pady=(0, 4), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        builder(card)
        return row + 2

    def _build_security(self, card):
        self._row(
            card, 0,
            label="Contraseña maestra",
            desc="Cambia la clave que cifra todas tus cuentas.",
            right_cb=self._right_change_password,
        )
        self._separator(card, 1)
        self._row(
            card, 2,
            label="Bloqueo por inactividad",
            desc="La sesión se bloquea automáticamente tras este tiempo sin actividad.",
            right_cb=self._right_timeout,
        )

    def _right_change_password(self, parent):
        ctk.CTkButton(
            parent, text="Cambiar contraseña",
            font=FONTS["body"],
            fg_color=COLORS["accent"], text_color="#000000",
            hover_color=COLORS["accent_hover"],
            height=34, width=168, corner_radius=8,
            command=self._open_change_password,
        ).pack()

    def _right_timeout(self, parent):
        current = self._settings.inactivity_timeout_min
        label   = "Desactivado" if current == 0 else f"{current} min"
        if label not in _TIMEOUT_OPTIONS:
            label = "10 min"

        ctk.CTkOptionMenu(
            parent,
            values=_TIMEOUT_OPTIONS,
            font=FONTS["body"],
            fg_color=COLORS["bg_secondary"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            width=148,
            command=self._on_timeout_changed,
            variable=ctk.StringVar(value=label),
        ).pack()

    def _build_appearance(self, card):
        self._row(
            card, 0,
            label="Tema de la interfaz",
            desc="Afecta a toda la aplicación de forma inmediata.",
            right_cb=self._right_theme,
        )

    def _right_theme(self, parent):
        current_theme = _THEME_LABELS.get(self._settings.theme, "Oscuro")
        self._theme_seg = ctk.CTkSegmentedButton(
            parent,
            values=["Oscuro", "Sistema", "Claro"],
            font=FONTS["body"],
            fg_color=COLORS["bg_secondary"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["bg_secondary"],
            unselected_hover_color=COLORS["bg_primary"],
            text_color="#000000",
            text_color_disabled=COLORS["text_secondary"],
            command=self._on_theme_changed,
        )
        self._theme_seg.set(current_theme)
        self._theme_seg.pack()

        self._system_info_var = ctk.StringVar(value="")
        self._system_info_label = ctk.CTkLabel(
            parent, textvariable=self._system_info_var,
            font=FONTS["small"], text_color=COLORS["text_secondary"],
        )
        self._system_info_label.pack(pady=(4, 0))
        self._update_system_info(current_theme)

        # Actualizar el label si el OS cambia de tema mientras la app está abierta
        self._bus.subscribe("app.theme_resolved", self._on_theme_resolved)

    def _build_riot(self, card):
        self._riot_key_visible = False
        card.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=20, pady=(14, 2), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="API Key de Riot Games",
            font=FONTS["body"], text_color=COLORS["text_primary"], anchor="w",
        ).grid(row=0, column=0, sticky="w")

        configured      = bool(self._settings.riot_api_key)
        self._riot_status_lbl = ctk.CTkLabel(
            hdr,
            text="Configurada" if configured else "No configurada",
            font=FONTS["small"],
            text_color=COLORS["success"] if configured else COLORS["text_secondary"],
        )
        self._riot_status_lbl.grid(row=0, column=1, padx=(8, 0), sticky="e")

        ctk.CTkLabel(
            card,
            text="Permite mostrar nivel, rango y estado del invocador en cada tarjeta.",
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
            wraplength=350,
        ).grid(row=1, column=0, padx=20, pady=(0, 6), sticky="w")

        key_row = ctk.CTkFrame(card, fg_color="transparent")
        key_row.grid(row=2, column=0, padx=20, pady=(0, 4), sticky="ew")
        key_row.grid_columnconfigure(0, weight=1)

        self._riot_key_var = ctk.StringVar(value=self._settings.riot_api_key)
        self._riot_key_entry = ctk.CTkEntry(
            key_row, textvariable=self._riot_key_var,
            font=FONTS["mono"],
            fg_color=COLORS["bg_card"], border_color=COLORS["border"],
            show="*",
            placeholder_text="RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            height=36,
        )
        self._riot_key_entry.grid(row=0, column=0, sticky="ew")

        self._riot_show_btn = ctk.CTkButton(
            key_row, text="Mostrar",
            font=FONTS["small"],
            fg_color=COLORS["bg_secondary"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["border"],
            width=72, height=36, corner_radius=6,
            command=self._toggle_riot_key,
        )
        self._riot_show_btn.grid(row=0, column=1, padx=(6, 0))

        ctk.CTkButton(
            key_row, text="Guardar",
            font=FONTS["small"],
            fg_color=COLORS["accent"], text_color="#000000",
            hover_color=COLORS["accent_hover"],
            width=72, height=36, corner_radius=6,
            command=self._save_riot_key,
        ).grid(row=0, column=2, padx=(4, 0))

        ctk.CTkLabel(
            card,
            text="Obtén tu clave en developer.riotgames.com  ·  Las claves de desarrollo se renuevan cada 24 h.",
            font=("Segoe UI", 9), text_color=COLORS["text_secondary"], anchor="w",
            wraplength=380,
        ).grid(row=3, column=0, padx=20, pady=(0, 14), sticky="w")

    def _toggle_riot_key(self):
        self._riot_key_visible = not self._riot_key_visible
        self._riot_key_entry.configure(show="" if self._riot_key_visible else "*")
        self._riot_show_btn.configure(
            text="Ocultar" if self._riot_key_visible else "Mostrar"
        )

    def _save_riot_key(self):
        key = self._riot_key_var.get().strip()
        self._settings.riot_api_key = key
        try:
            self._registry.riot_service.set_api_key(key)
        except AttributeError:
            pass
        configured = bool(key)
        self._riot_status_lbl.configure(
            text="Configurada" if configured else "No configurada",
            text_color=COLORS["success"] if configured else COLORS["text_secondary"],
        )

    def _build_launcher(self, card):
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text="Ruta al ejecutable del cliente",
            font=FONTS["body"], text_color=COLORS["text_primary"], anchor="w",
        ).grid(row=0, column=0, padx=20, pady=(14, 2), sticky="w")

        ctk.CTkLabel(
            card,
            text="RiotClientServices.exe o LeagueClient.exe. Deja vacío para autodetectar.",
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
            wraplength=370,
        ).grid(row=1, column=0, padx=20, pady=(0, 6), sticky="w")

        path_row = ctk.CTkFrame(card, fg_color="transparent")
        path_row.grid(row=2, column=0, padx=20, pady=(0, 4), sticky="ew")
        path_row.grid_columnconfigure(0, weight=1)

        self._launcher_path_var = ctk.StringVar(value=self._settings.launcher_path)
        self._launcher_path_entry = ctk.CTkEntry(
            path_row, textvariable=self._launcher_path_var,
            font=FONTS["mono"],
            fg_color=COLORS["bg_card"], border_color=COLORS["border"],
            placeholder_text=r"C:\Riot Games\Riot Client\RiotClientServices.exe",
            height=36,
        )
        self._launcher_path_entry.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            path_row, text="…",
            font=FONTS["body"],
            fg_color=COLORS["bg_secondary"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["border"],
            width=36, height=36, corner_radius=6,
            command=self._browse_launcher,
        ).grid(row=0, column=1, padx=(4, 0))

        ctk.CTkButton(
            path_row, text="Guardar",
            font=FONTS["small"],
            fg_color=COLORS["accent"], text_color="#000000",
            hover_color=COLORS["accent_hover"],
            width=72, height=36, corner_radius=6,
            command=self._save_launcher_path,
        ).grid(row=0, column=2, padx=(4, 0))

        detect_row = ctk.CTkFrame(card, fg_color="transparent")
        detect_row.grid(row=3, column=0, padx=20, pady=(0, 14), sticky="ew")
        detect_row.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            detect_row, text="Autodetectar",
            font=FONTS["small"],
            fg_color=COLORS["bg_secondary"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["border"],
            height=30, corner_radius=6,
            command=self._autodetect_launcher,
        ).grid(row=0, column=0, sticky="w")

        self._launcher_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            detect_row, textvariable=self._launcher_status_var,
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        ).grid(row=0, column=1, padx=(10, 0), sticky="w")

    def _browse_launcher(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Seleccionar ejecutable del cliente",
            filetypes=[
                ("Ejecutables", "*.exe"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if path:
            self._launcher_path_var.set(path)

    def _autodetect_launcher(self):
        try:
            svc = self._registry.launcher_service
        except AttributeError:
            from app.core.launcher_service import LauncherService
            svc = LauncherService(settings=self._settings)
        found = svc.find_client()
        if found:
            self._launcher_path_var.set(found)
            self._settings.launcher_path = found
            self._launcher_status_var.configure(text_color=COLORS["success"]) \
                if hasattr(self._launcher_status_var, "configure") else None
            self._launcher_status_var.set(f"Encontrado: {found}")
        else:
            self._launcher_status_var.set("No encontrado. Introduce la ruta manualmente.")

    def _save_launcher_path(self):
        path = self._launcher_path_var.get().strip()
        self._settings.launcher_path = path
        if path:
            from pathlib import Path
            if Path(path).is_file():
                self._launcher_status_var.set("Guardado.")
            else:
                self._launcher_status_var.set("⚠ El archivo no existe en esa ruta.")
        else:
            self._launcher_status_var.set("Ruta eliminada. Se usará autodetección.")

    def _build_data(self, card):
        self._row(
            card, 0,
            label="Carpeta de datos",
            desc="Ubicación donde se almacenan las cuentas y la clave maestra.",
            right_cb=self._right_data_folder,
        )
        self._separator(card, 1)
        self._row(
            card, 2,
            label="Exportar / Importar",
            desc="Exportar cuentas a JSON o importar desde copia de seguridad.",
            right_cb=self._right_export_import,
        )

    def _right_data_folder(self, parent):
        ctk.CTkLabel(
            parent, text=DATA_DIR,
            font=FONTS["mono"], text_color=COLORS["text_secondary"],
            wraplength=260, justify="right",
        ).pack(anchor="e")
        ctk.CTkButton(
            parent, text="Abrir carpeta",
            font=FONTS["small"],
            fg_color=COLORS["bg_secondary"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_primary"],
            height=28, width=120, corner_radius=6,
            command=self._open_data_folder,
        ).pack(anchor="e", pady=(6, 0))

    def _right_export_import(self, parent):
        ctk.CTkButton(
            parent, text="Exportar",
            font=FONTS["small"],
            fg_color=COLORS["accent"], text_color="#000000",
            hover_color=COLORS["accent_hover"],
            height=32, width=96, corner_radius=6,
            command=self._export_accounts,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            parent, text="Importar",
            font=FONTS["small"],
            fg_color=COLORS["bg_secondary"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_primary"],
            height=32, width=96, corner_radius=6,
            command=self._import_accounts,
        ).pack(side="left")

    def _row(self, card, grid_row: int, label: str, desc: str, right_cb):
        """Fila: etiqueta+descripción a la izquierda, widget a la derecha."""
        row_frame = ctk.CTkFrame(card, fg_color="transparent")
        row_frame.grid(row=grid_row, column=0, padx=0, pady=0, sticky="ew")
        row_frame.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(row_frame, fg_color="transparent")
        left.grid(row=0, column=0, padx=(20, 8), pady=14, sticky="w")

        ctk.CTkLabel(
            left, text=label, font=FONTS["body"],
            text_color=COLORS["text_primary"], anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            left, text=desc, font=FONTS["small"],
            text_color=COLORS["text_secondary"], anchor="w",
            wraplength=280,
        ).pack(anchor="w")

        right = ctk.CTkFrame(row_frame, fg_color="transparent")
        right.grid(row=0, column=1, padx=(8, 20), pady=14, sticky="e")
        right_cb(right)

    def _separator(self, card, grid_row: int):
        ctk.CTkFrame(card, height=1, fg_color=COLORS["border"]).grid(
            row=grid_row, column=0, sticky="ew", padx=16,
        )

    def _open_change_password(self):
        from app.ui.components.change_password_dialog import ChangePasswordDialog
        ChangePasswordDialog(parent=self.winfo_toplevel(), registry=self._registry)

    def _on_timeout_changed(self, label: str):
        minutes = _TIMEOUT_MAP.get(label, 10)
        self._settings.inactivity_timeout_min = minutes

    def _on_theme_changed(self, label: str):
        theme = _THEME_VALUES.get(label, "Dark")
        self._settings.theme = theme   # EventBus notifica a AppWindow; él hace el rebuild
        self._update_system_info(label)

    def _update_system_info(self, seg_label: str):
        if seg_label == "Sistema":
            try:
                import customtkinter as ctk
                resolved = _RESOLVED_LABEL.get(ctk.get_appearance_mode(), "")
                self._system_info_var.set(f"(el SO usa modo {resolved.lower()})")
            except Exception:
                self._system_info_var.set("")
        else:
            self._system_info_var.set("")

    def _on_theme_resolved(self, resolved=None, **_):
        """Actualiza el info label cuando el OS cambia de tema en modo Sistema."""
        if hasattr(self, "_theme_seg") and self._theme_seg.get() == "Sistema":
            label = _RESOLVED_LABEL.get(resolved, "")
            self._system_info_var.set(f"(el SO usa modo {label.lower()})")

    def _open_data_folder(self):
        import os
        import sys
        import subprocess
        try:
            if sys.platform == "win32":
                os.startfile(DATA_DIR)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", DATA_DIR])
            else:
                subprocess.Popen(["xdg-open", DATA_DIR])
        except Exception as e:
            self._show_dialog_error(f"No se pudo abrir la carpeta:\n{e}")

    def _export_accounts(self):
        """Muestra diálogo de selección de formato antes de exportar."""
        dlg = ctk.CTkToplevel(self.winfo_toplevel())
        dlg.title("Exportar cuentas")
        dlg.geometry("420x420")
        dlg.resizable(False, False)
        dlg.configure(fg_color=COLORS["bg_primary"])
        dlg.grab_set()
        dlg.after(50, lambda: self._center_dialog(dlg))

        ctk.CTkLabel(
            dlg, text="Formato de exportación",
            font=FONTS["heading"], text_color=COLORS["text_primary"],
        ).pack(padx=24, pady=(20, 4), anchor="w")

        ctk.CTkLabel(
            dlg,
            text="Elige cómo quieres proteger el archivo exportado.",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
        ).pack(padx=24, pady=(0, 16), anchor="w")

        fmt_var = ctk.StringVar(value="json_v1")

        for value, label, desc in [
            ("json_v1",
             "JSON — contraseña maestra",
             "Solo restaurable en esta misma instalación."),
            ("json_v2",
             "JSON — contraseña personalizada",
             "Portable entre instalaciones. Requiere una contraseña de exportación."),
            ("csv",
             "CSV — sin cifrar",
             "⚠ Las contraseñas quedarán en texto plano. Solo para migrar a otro gestor."),
        ]:
            card = ctk.CTkFrame(dlg, fg_color=COLORS["bg_card"],
                                corner_radius=8, border_width=1,
                                border_color=COLORS["border"])
            card.pack(fill="x", padx=24, pady=3)
            card.grid_columnconfigure(1, weight=1)

            ctk.CTkRadioButton(
                card, text="", variable=fmt_var, value=value,
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                command=lambda: _toggle_password_section(),
            ).grid(row=0, column=0, padx=(12, 6), pady=10)

            ctk.CTkLabel(
                card, text=label, font=FONTS["body"],
                text_color=COLORS["text_primary"], anchor="w",
            ).grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(
                card, text=desc, font=FONTS["small"],
                text_color=COLORS["text_secondary"], anchor="w", wraplength=300,
            ).grid(row=1, column=1, sticky="w", pady=(0, 8))

        pw_frame = ctk.CTkFrame(dlg, fg_color="transparent")

        ctk.CTkLabel(
            pw_frame, text="Contraseña de exportación",
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        ).pack(anchor="w", padx=24, pady=(0, 2))
        exp_pw_var  = ctk.StringVar()
        exp_pw_entry = ctk.CTkEntry(
            pw_frame, textvariable=exp_pw_var, show="*",
            font=FONTS["body"], fg_color=COLORS["bg_card"],
            border_color=COLORS["border"], height=36,
        )
        exp_pw_entry.pack(fill="x", padx=24)

        ctk.CTkLabel(
            pw_frame, text="Confirmar contraseña",
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        ).pack(anchor="w", padx=24, pady=(8, 2))
        exp_pw2_var   = ctk.StringVar()
        exp_pw2_entry = ctk.CTkEntry(
            pw_frame, textvariable=exp_pw2_var, show="*",
            font=FONTS["body"], fg_color=COLORS["bg_card"],
            border_color=COLORS["border"], height=36,
        )
        exp_pw2_entry.pack(fill="x", padx=24)

        def _toggle_password_section():
            if fmt_var.get() == "json_v2":
                pw_frame.pack(fill="x", pady=(8, 0))
            else:
                pw_frame.pack_forget()

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(16, 20))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        def _do_export():
            fmt = fmt_var.get()
            if fmt == "json_v2":
                pw  = exp_pw_var.get()
                pw2 = exp_pw2_var.get()
                if not pw:
                    self._show_dialog_error("Introduce una contraseña de exportación.")
                    return
                if pw != pw2:
                    self._show_dialog_error("Las contraseñas no coinciden.")
                    return

            from tkinter import filedialog
            from app.core.export_service import ExportService, ExportError

            ext   = ".json" if fmt != "csv" else ".csv"
            ftype = [("JSON de Rift Vault", "*.json")] if fmt != "csv" else [("CSV", "*.csv")]
            name  = f"rift_vault_backup{ext}"

            filepath = filedialog.asksaveasfilename(
                parent=dlg,
                title="Guardar archivo de exportación",
                defaultextension=ext,
                filetypes=ftype + [("Todos los archivos", "*.*")],
                initialfile=name,
            )
            if not filepath:
                return

            try:
                svc = ExportService(self._registry.service, self._registry.crypto)
                if fmt == "json_v1":
                    count = svc.export_json(filepath)
                elif fmt == "json_v2":
                    count = svc.export_json_with_password(filepath, exp_pw_var.get())
                else:
                    count = svc.export_csv(filepath)

                dlg.destroy()
                self._show_dialog_info(
                    "Exportación completada",
                    f"{count} cuenta{'s' if count != 1 else ''} "
                    f"exportada{'s' if count != 1 else ''} correctamente.",
                )
            except ExportError as e:
                self._show_dialog_error(str(e))

        ctk.CTkButton(
            btn_row, text="Cancelar",
            font=FONTS["body"], fg_color=COLORS["bg_card"],
            text_color=COLORS["text_secondary"], hover_color=COLORS["bg_secondary"],
            height=36, command=dlg.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="Exportar",
            font=FONTS["body"], fg_color=COLORS["accent"],
            text_color="#000000", hover_color=COLORS["accent_hover"],
            height=36, command=_do_export,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _import_accounts(self):
        """Abre filedialog, detecta formato y muestra el paso siguiente."""
        from tkinter import filedialog
        from app.core.export_service import ExportService, ExportError

        filepath = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Importar cuentas",
            filetypes=[
                ("Todos los formatos compatibles", "*.json *.csv"),
                ("JSON de Rift Vault", "*.json"),
                ("CSV", "*.csv"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not filepath:
            return

        try:
            svc  = ExportService(self._registry.service, self._registry.crypto)
            info = svc.probe_file(filepath)
        except ExportError as e:
            self._show_dialog_error(str(e))
            return

        fmt = info["format"]

        if fmt == "json_v1":
            self._run_import(lambda: svc.import_json(filepath))

        elif fmt == "json_v2":
            self._import_with_password_dialog(svc, filepath, info["account_count"])

        elif fmt == "csv":
            self._import_csv_confirm_dialog(svc, filepath, info)

    def _run_import(self, import_fn):
        from app.core.export_service import ExportError
        try:
            imported, skipped = import_fn()
            msg = f"{imported} cuenta{'s' if imported != 1 else ''} importada{'s' if imported != 1 else ''}."
            if skipped:
                msg += f"\n{skipped} omitida{'s' if skipped != 1 else ''} (duplicadas o datos inválidos)."
            self._show_dialog_info("Importación completada", msg)
            self._bus.emit("accounts.changed")
        except ExportError as e:
            self._show_dialog_error(str(e))

    def _import_with_password_dialog(self, svc, filepath: str, count: int):
        """Pide la contraseña de exportación para un JSON v2."""
        dlg = ctk.CTkToplevel(self.winfo_toplevel())
        dlg.title("Contraseña de importación")
        dlg.geometry("380x240")
        dlg.resizable(False, False)
        dlg.configure(fg_color=COLORS["bg_primary"])
        dlg.grab_set()
        dlg.after(50, lambda: self._center_dialog(dlg))

        ctk.CTkLabel(
            dlg, text="Archivo protegido con contraseña",
            font=FONTS["heading"], text_color=COLORS["text_primary"],
        ).pack(padx=24, pady=(20, 4), anchor="w")
        ctk.CTkLabel(
            dlg,
            text=f"El archivo contiene {count} cuenta{'s' if count != 1 else ''}. "
                 "Introduce la contraseña usada al exportar.",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
            wraplength=340,
        ).pack(padx=24, pady=(0, 12), anchor="w")

        pw_var = ctk.StringVar()
        pw_entry = ctk.CTkEntry(
            dlg, textvariable=pw_var, show="*",
            font=FONTS["body"], fg_color=COLORS["bg_card"],
            border_color=COLORS["border"], height=38,
        )
        pw_entry.pack(fill="x", padx=24)
        pw_entry.focus_set()

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(16, 20))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        def _do():
            pw = pw_var.get()
            if not pw:
                return
            dlg.destroy()
            self._run_import(lambda: svc.import_json_with_password(filepath, pw))

        pw_entry.bind("<Return>", lambda _: _do())

        ctk.CTkButton(
            btn_row, text="Cancelar", font=FONTS["body"],
            fg_color=COLORS["bg_card"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"], height=36,
            command=dlg.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="Importar", font=FONTS["body"],
            fg_color=COLORS["accent"], text_color="#000000",
            hover_color=COLORS["accent_hover"], height=36,
            command=_do,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _import_csv_confirm_dialog(self, svc, filepath: str, info: dict):
        """Muestra un resumen del CSV detectado antes de importar."""
        dlg = ctk.CTkToplevel(self.winfo_toplevel())
        dlg.title("Importar desde CSV")
        dlg.geometry("400x280")
        dlg.resizable(False, False)
        dlg.configure(fg_color=COLORS["bg_primary"])
        dlg.grab_set()
        dlg.after(50, lambda: self._center_dialog(dlg))

        count   = info["account_count"]
        mapping = info.get("csv_mapping") or {}
        headers = info.get("csv_headers") or []

        ctk.CTkLabel(
            dlg, text="Importar desde CSV",
            font=FONTS["heading"], text_color=COLORS["text_primary"],
        ).pack(padx=24, pady=(20, 4), anchor="w")

        detected = ", ".join(
            f"{k}→col.{v+1}" for k, v in sorted(mapping.items())
        ) or "ninguna reconocida"
        ctk.CTkLabel(
            dlg,
            text=f"Filas de datos: {count}\n"
                 f"Cabeceras: {', '.join(headers[:6]) or '—'}\n"
                 f"Columnas detectadas: {detected}",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
            justify="left", wraplength=360,
        ).pack(padx=24, pady=(0, 8), anchor="w")

        if "alias" not in mapping or "username" not in mapping:
            ctk.CTkLabel(
                dlg,
                text="⚠ No se detectaron columnas de alias y/o username. "
                     "La importación puede fallar.",
                font=FONTS["small"], text_color=COLORS["danger"],
                wraplength=360,
            ).pack(padx=24, pady=(0, 4), anchor="w")

        ctk.CTkLabel(
            dlg,
            text="⚠ Las contraseñas del CSV están en texto plano.",
            font=FONTS["small"], text_color=COLORS["accent_dim"],
        ).pack(padx=24, pady=(4, 0), anchor="w")

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(16, 20), side="bottom")
        btn_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row, text="Cancelar", font=FONTS["body"],
            fg_color=COLORS["bg_card"], text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_secondary"], height=36,
            command=dlg.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        def _do():
            dlg.destroy()
            self._run_import(lambda: svc.import_csv(filepath))

        ctk.CTkButton(
            btn_row, text="Importar", font=FONTS["body"],
            fg_color=COLORS["accent"], text_color="#000000",
            hover_color=COLORS["accent_hover"], height=36,
            command=_do,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _show_dialog_info(self, title: str, message: str):
        self._dialog(title, message, COLORS["text_primary"])

    def _show_dialog_error(self, message: str):
        self._dialog("Error", message, COLORS["danger"])

    def _dialog(self, title: str, message: str, text_color):
        dlg = ctk.CTkToplevel(self.winfo_toplevel())
        dlg.title(title)
        dlg.geometry("380x160")
        dlg.resizable(False, False)
        dlg.configure(fg_color=COLORS["bg_primary"])
        dlg.grab_set()
        dlg.after(50, lambda: self._center_dialog(dlg))
        ctk.CTkLabel(
            dlg, text=message,
            font=FONTS["body"], text_color=text_color, wraplength=340,
        ).pack(pady=(28, 16), padx=24)
        ctk.CTkButton(
            dlg, text="OK",
            fg_color=COLORS["accent"], text_color="#000000",
            font=FONTS["body"], height=34, command=dlg.destroy,
        ).pack()

    def _center_dialog(self, dlg):
        dlg.update_idletasks()
        root = self.winfo_toplevel()
        x = root.winfo_x() + (root.winfo_width()  - dlg.winfo_width())  // 2
        y = root.winfo_y() + (root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")

    def refresh(self):
        pass
