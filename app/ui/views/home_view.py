"""Vista de inicio con onboarding y dashboard de estadísticas."""

import customtkinter as ctk
from datetime import datetime, timezone
from typing import Callable, Optional

from app.config import COLORS, FONTS, APP_VERSION, LOGO_PATH
from app.core.password_generator import evaluate as eval_strength

_MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun",
              "jul", "ago", "sep", "oct", "nov", "dic"]

_REGION_COLORS = [
    COLORS["accent"],
    COLORS["success"],
    ("#5B8CFF", "#5B8CFF"),
    ("#9B59B6", "#9B59B6"),
    COLORS["accent_dim"],
]


def _fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return f"{dt.day} {_MONTHS_ES[dt.month - 1]} {dt.year}  {dt.strftime('%H:%M')}"
    except Exception:
        return "—"


class HomeView(ctk.CTkFrame):
    """Vista de inicio con onboarding dinámico y dashboard de estadísticas."""

    def __init__(self, parent, service=None, settings=None,
                 on_navigate: Optional[Callable[[str], None]] = None,
                 **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._service     = service
        self._settings    = settings
        self._on_navigate = on_navigate

        self._total_var   = ctk.StringVar(value="—")
        self._month_var   = ctk.StringVar(value="—")
        self._session_var = ctk.StringVar(value="—")

        self._build()

    def refresh(self, **kwargs):
        if not self._service:
            return
        count = len(self._service.get_all())
        self._show_panel(count)
        if count > 0:
            self._update_stats()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=0, column=0)
        self._center = center

        try:
            from PIL import Image
            _img = Image.open(LOGO_PATH)
            _w, _h = _img.size
            _s = min(96 / _w, 96 / _h)
            _logo_img = ctk.CTkImage(light_image=_img, dark_image=_img,
                                     size=(int(_w * _s), int(_h * _s)))
            ctk.CTkLabel(center, image=_logo_img, text="").pack(pady=(0, 6))
        except Exception:
            ctk.CTkLabel(center, text="", font=("Segoe UI Emoji", 48)).pack(pady=(0, 6))
        ctk.CTkLabel(
            center, text="Rift Vault",
            font=FONTS["title"], text_color=COLORS["accent"],
        ).pack()
        ctk.CTkLabel(
            center, text="Tus contrasenas, seguras detras del nexo.",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
        ).pack(pady=(0, 20))

        self._onboarding_panel = self._build_onboarding(center)
        self._stats_panel      = self._build_stats_shell(center)

        ctk.CTkLabel(
            self, text=f"v{APP_VERSION}",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, pady=(0, 8))

        self._stats_panel.pack_forget()
        self.refresh()

    def _build_onboarding(self, parent) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(
            parent, fg_color=COLORS["bg_card"],
            corner_radius=12, border_width=1, border_color=COLORS["border"],
        )

        ctk.CTkLabel(
            panel, text="Empecemos",
            font=FONTS["heading"], text_color=COLORS["text_primary"],
        ).pack(pady=(20, 4), padx=32)
        ctk.CTkLabel(
            panel, text="Sigue estos pasos para gestionar tus cuentas de LoL:",
            font=FONTS["small"], text_color=COLORS["text_secondary"],
        ).pack(pady=(0, 16), padx=32)

        self._build_step(panel, "1", done=True,
                         title="Contrasena maestra creada",
                         detail="Tus datos estan cifrados con AES-128 + PBKDF2.")
        self._build_divider(panel)
        self._build_step(panel, "2", done=False,
                         title="Anade tu primera cuenta",
                         detail="Guarda usuario y contrasena de una cuenta de League of Legends.",
                         cta_text="  Anadir primera cuenta",
                         cta_cmd=lambda: self._on_navigate("accounts") if self._on_navigate else None)
        self._build_divider(panel)
        self._build_step(panel, "3", done=False,
                         title="Copia credenciales con un clic",
                         detail="Accede a tus contrasenas sin escribirlas.",
                         pending=True)

        ctk.CTkFrame(panel, height=20, fg_color="transparent").pack()
        return panel

    def _build_stats_shell(self, parent) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(parent, fg_color="transparent")

        cards_row = ctk.CTkFrame(panel, fg_color="transparent")
        cards_row.pack(pady=(0, 10))

        self._build_stat_card(cards_row, "Cuentas",       self._total_var,   col=0)
        self._build_stat_card(cards_row, "Este mes",      self._month_var,   col=1)
        self._build_stat_card(cards_row, "Última sesión", self._session_var, col=2, mono=True)

        self._regions_card = ctk.CTkFrame(
            panel,
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"], border_width=1,
            corner_radius=10,
        )
        self._regions_card.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            self._regions_card,
            text="Distribución por región",
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        ).pack(anchor="w", padx=14, pady=(10, 6))

        self._regions_body = ctk.CTkFrame(self._regions_card, fg_color="transparent")
        self._regions_body.pack(fill="x", padx=14, pady=(0, 10))

        self._alerts_frame = ctk.CTkFrame(
            panel,
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"], border_width=1,
            corner_radius=10,
        )
        self._alerts_frame.pack(fill="x")
        self._alerts_frame.grid_columnconfigure(0, weight=1)

        return panel

    def _build_stat_card(self, parent, label: str, var: ctk.StringVar,
                         col: int, mono: bool = False):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=10, border_width=1, border_color=COLORS["border"],
        )
        card.grid(row=0, column=col, padx=5, ipadx=14, ipady=10, sticky="nsew")

        font = ("Consolas", 11) if mono else FONTS["heading"]
        ctk.CTkLabel(
            card, textvariable=var,
            font=font, text_color=COLORS["accent"], anchor="center",
        ).pack(padx=16, pady=(8, 2))
        ctk.CTkLabel(
            card, text=label,
            font=FONTS["small"], text_color=COLORS["text_secondary"],
        ).pack(padx=16, pady=(0, 8))

    def _update_stats(self):
        stats = self._compute_stats()

        self._total_var.set(str(stats["total"]))
        self._month_var.set(str(stats["this_month"]))

        prev = self._settings.previous_unlock_at if self._settings else None
        self._session_var.set(_fmt_date(prev) if prev else "Primera sesión")

        self._rebuild_regions(stats["regions"])
        self._rebuild_alerts(stats["weak"], stats["old_password"])

    def _rebuild_regions(self, regions: list[tuple[str, int]]):
        for w in self._regions_body.winfo_children():
            w.destroy()

        if not regions:
            ctk.CTkLabel(
                self._regions_body, text="Sin datos",
                font=FONTS["small"], text_color=COLORS["text_secondary"],
            ).pack(side="left")
            return

        total = sum(c for _, c in regions)
        for i, (region, count) in enumerate(regions):
            color = _REGION_COLORS[i % len(_REGION_COLORS)]
            pct   = int(count / total * 100)

            pill = ctk.CTkFrame(
                self._regions_body,
                fg_color=COLORS["bg_secondary"],
                corner_radius=6, border_width=1, border_color=COLORS["border"],
            )
            pill.pack(side="left", padx=(0, 6), pady=2)

            ctk.CTkLabel(
                pill, text=region,
                font=("Consolas", 10, "bold"), text_color=color,
            ).pack(side="left", padx=(8, 4), pady=4)

            ctk.CTkLabel(
                pill, text=f"{count}  ({pct}%)",
                font=("Consolas", 10), text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(0, 8), pady=4)

    def _rebuild_alerts(self, weak: int, old: int):
        for w in self._alerts_frame.winfo_children():
            w.destroy()

        items: list[tuple[str, str, tuple]] = []

        if weak > 0:
            s = "cuenta" if weak == 1 else "cuentas"
            items.append(("⚠", f"{weak} {s} con contraseña débil", COLORS["danger"]))
        if old > 0:
            s = "cuenta" if old == 1 else "cuentas"
            items.append(("⚠", f"{old} {s} sin cambio de contraseña en más de 180 días",
                          ("#E67E22", "#E67E22")))
        if not items:
            items.append(("✓", "Sin alertas de seguridad", COLORS["success"]))

        for row_idx, (icon, text, color) in enumerate(items):
            row = ctk.CTkFrame(self._alerts_frame, fg_color="transparent")
            row.grid(row=row_idx, column=0, sticky="ew",
                     padx=14,
                     pady=(8 if row_idx == 0 else 2,
                            8 if row_idx == len(items) - 1 else 2))

            ctk.CTkLabel(
                row, text=icon,
                font=("Segoe UI Emoji", 12), text_color=color,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(
                row, text=text,
                font=FONTS["small"], text_color=color, anchor="w",
            ).pack(side="left")

    def _compute_stats(self) -> dict:
        accounts   = self._service.get_all()
        now        = datetime.now(timezone.utc)
        this_month = 0
        weak_count = 0
        old_count  = 0
        regions: dict[str, int] = {}

        for a in accounts:
            try:
                created = datetime.fromisoformat(a.created_at)
                if created.year == now.year and created.month == now.month:
                    this_month += 1
            except Exception:
                pass

            regions[a.region] = regions.get(a.region, 0) + 1

            try:
                updated = datetime.fromisoformat(a.updated_at)
                if (now - updated).days > 180:
                    old_count += 1
            except Exception:
                pass

            try:
                plain = self._service.get_decrypted_password(a.id)
                if eval_strength(plain)["level"] <= 2:
                    weak_count += 1
            except Exception:
                pass

        return {
            "total":        len(accounts),
            "this_month":   this_month,
            "weak":         weak_count,
            "old_password": old_count,
            "regions":      sorted(regions.items(), key=lambda x: -x[1]),
        }

    def _build_step(self, parent, number: str, done: bool, title: str,
                    detail: str, cta_text: str = "", cta_cmd=None,
                    pending: bool = False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=28, pady=4)
        row.grid_columnconfigure(1, weight=1)

        if done:
            icon_text, icon_color = "✓", COLORS["success"]
        elif pending:
            icon_text, icon_color = str(number), COLORS["text_secondary"]
        else:
            icon_text, icon_color = str(number), COLORS["accent"]

        icon_frame = ctk.CTkFrame(
            row, width=32, height=32,
            fg_color=COLORS["bg_secondary"], corner_radius=16,
        )
        icon_frame.grid(row=0, column=0, rowspan=3, sticky="n", padx=(0, 14), pady=(4, 0))
        icon_frame.grid_propagate(False)
        ctk.CTkLabel(
            icon_frame, text=icon_text,
            font=("Segoe UI", 13, "bold"), text_color=icon_color,
        ).place(relx=0.5, rely=0.5, anchor="center")

        title_color = COLORS["text_primary"] if (done or not pending) else COLORS["text_secondary"]
        ctk.CTkLabel(
            row, text=title,
            font=FONTS["body"], text_color=title_color, anchor="w",
        ).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            row, text=detail,
            font=FONTS["small"], text_color=COLORS["text_secondary"],
            anchor="w", wraplength=300,
        ).grid(row=1, column=1, sticky="w")

        if cta_text and cta_cmd:
            ctk.CTkButton(
                row, text=cta_text,
                font=FONTS["body"], height=34, corner_radius=8,
                fg_color=COLORS["accent"], text_color="#000000",
                hover_color=COLORS["accent_hover"],
                command=cta_cmd,
            ).grid(row=2, column=1, sticky="w", pady=(8, 4))

    def _build_divider(self, parent):
        ctk.CTkFrame(parent, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=28, pady=6)

    def _show_panel(self, count: int):
        if count == 0:
            self._stats_panel.pack_forget()
            self._onboarding_panel.pack()
        else:
            self._onboarding_panel.pack_forget()
            self._stats_panel.pack()
