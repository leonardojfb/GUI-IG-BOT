"""
⚡ Instagram Automation Pro — GUI Premium V7
Dashboard ultra-premium con CustomTkinter.
Mantiene toda la lógica de negocio de gui_unificada.py.


TAREA 1: Esqueleto base — sidebar, content area, status bar, reloj.
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import math
import random
import time
import threading
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import json
import shutil
import requests
import render_performance

from calendar_manifest import (
    append_scheduled_entries,
    build_entry,
    load_entries,
    manifest_path,
    replace_entries,
)
from publication_schedule import expand_lane_slots, merge_scheduled_entries
from por_cuentas_lanes import LaneRequest, build_lane_entries, resolve_legacy_reel_schedule
from database import DatabaseManager
from airtable_sync import (
    AirtableConfig,
    AirtableSyncError,
    apply_airtable_mirror_plan,
    build_account_sync_plan,
    build_airtable_mirror_plan,
    fetch_airtable_accounts,
    fetch_airtable_records,
    load_airtable_config,
    prepare_airtable_account_table,
    save_airtable_config,
)
from trial_content import (
    group_trial_sources, missing_trial_caption_sources,
    trial_calendar_root, build_trial_account_plan,
    reused_trial_tanda_warnings, trial_preview_path,
    source_key_from_filename, forge_output_id_from_filename,
)
from updater import APP_DIR as UPDATE_APP_DIR, check_and_apply, load_config, read_local_version
from console_encoding import ensure_stdout_utf8

ensure_stdout_utf8()

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ACCT_HIST_FILE = os.path.join(_BASE_DIR, "dist_accounts_history.json")


def _windows_long_path(path):
    path = os.path.abspath(os.fspath(path))
    if os.name != "nt" or path.startswith("\\\\?\\"):
        return path
    if path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path


def _path_exists(path):
    return os.path.exists(_windows_long_path(path))


def _path_isdir(path):
    return os.path.isdir(_windows_long_path(path))


def _safe_file_status(path):
    try:
        exists = os.path.exists(_windows_long_path(path))
        size = os.path.getsize(_windows_long_path(path)) if exists else 0
        return exists, size, ""
    except OSError as exc:
        return False, 0, str(exc)


def _acct_inventory_items(folders):
    """Use the same Forge publication gate for Por Cuentas and Por Tandas."""
    items, _notices = _acct_inventory_summary(folders)
    return items


def _acct_inventory_summary(folders):
    """Return distributable Forge outputs and notices for validated partial batches."""
    from Organizador import _tanda_video_inventory

    items = []
    notices = []
    for source_tanda, source_folder in folders.items():
        if not os.path.isdir(source_folder):
            raise FileNotFoundError(f"Carpeta no encontrada: {source_folder}")
        videos, notice = _tanda_video_inventory(
            source_folder, extensions=(".mp4", ".mov", ".avi"))
        if notice and not notice.startswith("Tanda Forge parcial:"):
            raise ValueError(f"{source_tanda}: {notice}")
        if notice:
            notices.append(f"{source_tanda}: {notice}")
        items.extend({"tanda": source_tanda, "name": name} for name in sorted(videos))
    return items, notices


def _telegram_runtime_diagnostics(db_manager, app_dir=None, version_reader=read_local_version):
    app_path = os.path.abspath(os.fspath(app_dir or _BASE_DIR))
    try:
        version = version_reader(UPDATE_APP_DIR)
    except Exception as exc:
        version = f"desconocida ({exc})"
    db_path = os.path.abspath(os.fspath(getattr(db_manager, "db_path", os.path.join(app_path, "organizador.db"))))
    db_exists, db_size, db_error = _safe_file_status(db_path)
    manifest_path_local = os.path.join(app_path, "calendar_manifest.json")
    manifest_exists, manifest_size, manifest_error = _safe_file_status(manifest_path_local)
    lines = [
        f"Diagnostico Telegram: version={version}",
        f"Diagnostico Telegram: app_dir={app_path}",
        f"Diagnostico Telegram: db_path={db_path} db_exists={db_exists} db_size={db_size}",
        f"Diagnostico Telegram: manifest={manifest_path_local} manifest_exists={manifest_exists} manifest_size={manifest_size}",
    ]
    if db_error:
        lines.append(f"Diagnostico Telegram: db_error={db_error}")
    if manifest_error:
        lines.append(f"Diagnostico Telegram: manifest_error={manifest_error}")
    return lines


def _telegram_done_logs(success, detail):
    if success:
        return [("Proceso completado exitosamente.", "SUCCESS")]
    logs = []
    detail = str(detail or "").strip()
    if detail:
        logs.append((f"Error interno Telegram: {detail}", "ERROR"))
    logs.append(("El bot se detuvo por un error o cancelacion.", "ERROR"))
    return logs


def _copy_calendar_file(src, dst):
    dst_dir = os.path.dirname(os.path.abspath(os.fspath(dst)))
    os.makedirs(_windows_long_path(dst_dir), exist_ok=True)
    shutil.copy2(_windows_long_path(src), _windows_long_path(dst))


def _save_forge_transform_log(
    db,
    process_kind,
    source_path,
    output_path,
    tanda_name,
    source_identity,
    params,
    meta,
):
    details = dict(params or {})
    details["iphone_metadata"] = meta or {}
    return db.save_video_transform_log(
        process_kind,
        os.path.abspath(source_path),
        os.path.abspath(output_path),
        details,
        tanda_name=tanda_name,
        source_identity=source_identity,
    )


def _format_transform_summary(details):
    details = details or {}
    trim_start = details.get("trim_start_ms") or 0
    trim_end = details.get("trim_end_ms") or 0
    return {
        "rotation": f"{float(details.get('rotate_deg') or 0):.2f} deg",
        "crop": f"{int(details.get('crop_px') or 0)} px",
        "speed": f"x{float(details.get('speed') or 1):.4f}",
        "trim": f"{int(trim_start)} ms / {int(trim_end)} ms",
    }
from styles.colors import (
    BG_APP, BG_SIDEBAR, BG_CARD, BG_CARD2, BG_INPUT, BORDER,
    NEON_CYAN, NEON_PURPLE, IG_PINK, SUCCESS, WARNING, DANGER, INFO, TELEGRAM,
    ACCENT_WEAK, ACCENT, ACCENT_TEXT, ACCENT_HOVER, SURFACE2, resolve, darken,
    TEXT_H1, TEXT_BODY, TEXT_MUTED, TEXT_ON_DANGER,
    FONT_TITLE, FONT_H2, FONT_H3, FONT_BODY, FONT_SMALL, FONT_MONO,
    SIDEBAR_W, STATUS_H, CARD_RADIUS, BTN_RADIUS, BTN_H, BTN_H_LG,
)
from styles.components import (
    NavItem, GhostButton, PrimaryButton, DangerButton, Card, PageHeader,
    SegmentedControl, Stepper, ToggleRow, KeyValueRow, Dropzone, PhonePreview,
)


def _install_customtkinter_dropdown_destroy_safety(
    *,
    dropdown_menu_cls=None,
    scaling_base_cls=None,
    combo_box_cls=None,
    option_menu_cls=None,
    tcl_error_cls=None,
):
    """Remove stale CustomTkinter dropdown scaling callbacks on widget teardown."""
    if (
        dropdown_menu_cls is None
        or scaling_base_cls is None
        or combo_box_cls is None
        or option_menu_cls is None
    ):
        try:
            from customtkinter.windows.widgets.core_widget_classes.dropdown_menu import DropdownMenu
            from customtkinter.windows.widgets.scaling.scaling_base_class import CTkScalingBaseClass
            from customtkinter.windows.widgets.ctk_combobox import CTkComboBox
            from customtkinter.windows.widgets.ctk_optionmenu import CTkOptionMenu
        except Exception:
            return
        dropdown_menu_cls = dropdown_menu_cls or DropdownMenu
        scaling_base_cls = scaling_base_cls or CTkScalingBaseClass
        combo_box_cls = combo_box_cls or CTkComboBox
        option_menu_cls = option_menu_cls or CTkOptionMenu

    tcl_error_cls = tcl_error_cls or tk.TclError

    def _is_destroyed_tk_command_error(exc):
        return "invalid command name" in str(exc)

    if not getattr(dropdown_menu_cls, "_metodo_destroy_safety_installed", False):
        original_dropdown_destroy = dropdown_menu_cls.destroy

        def safe_dropdown_destroy(self, *args, **kwargs):
            if not getattr(self, "_metodo_scaling_destroy_called", False):
                try:
                    scaling_base_cls.destroy(self)
                except Exception:
                    pass
                try:
                    self._metodo_scaling_destroy_called = True
                except Exception:
                    pass
            try:
                return original_dropdown_destroy(self, *args, **kwargs)
            except tcl_error_cls as exc:
                if _is_destroyed_tk_command_error(exc):
                    return None
                raise

        dropdown_menu_cls.destroy = safe_dropdown_destroy
        dropdown_menu_cls._metodo_original_destroy = original_dropdown_destroy
        dropdown_menu_cls._metodo_destroy_safety_installed = True

    def _patch_owner_destroy(owner_cls, patch_attr):
        if getattr(owner_cls, patch_attr, False):
            return

        original_owner_destroy = owner_cls.destroy

        def safe_owner_destroy(self, *args, **kwargs):
            dropdown = getattr(self, "_dropdown_menu", None)
            if dropdown is not None:
                try:
                    dropdown.destroy()
                except tcl_error_cls as exc:
                    if not _is_destroyed_tk_command_error(exc):
                        raise
            return original_owner_destroy(self, *args, **kwargs)

        owner_cls.destroy = safe_owner_destroy
        setattr(owner_cls, f"{patch_attr}_original", original_owner_destroy)
        setattr(owner_cls, patch_attr, True)

    _patch_owner_destroy(combo_box_cls, "_metodo_dropdown_destroy_safety_installed")
    _patch_owner_destroy(option_menu_cls, "_metodo_dropdown_destroy_safety_installed")


_install_customtkinter_dropdown_destroy_safety()

# ── Configuración global de CustomTkinter ──────────────────────────────────
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("dark-blue")

DESIGN_WINDOW_W = 1400
DESIGN_WINDOW_H = 860
MIN_WINDOW_W = 860
MIN_WINDOW_H = 520
SCREEN_MARGIN_W = 80
SCREEN_MARGIN_H = 120

# ══════════════════════════════════════════════════════════════════════════════
# PANEL DE ESTADO DE CUENTAS — Constantes y helpers
# ══════════════════════════════════════════════════════════════════════════════
PANEL_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel_config.json")

LABEL_OPTIONS = ["nuevo", "viral", "normal", "SB", "ban", "limitada", "muerta"]
LABEL_COLORS  = {
    "nuevo":    "#64748b",
    "viral":    "#f59e0b",
    "normal":   "#10b981",
    "SB":       "#f97316",
    "ban":      "#ef4444",
    "limitada": "#eab308",
    "muerta":   "#6b7280",
}

ACCOUNT_STATUS_OPTIONS = ["unknown", "alive", "limited", "dead"]
LIMITATION_OPTIONS = [
    "Restricción de acciones",
    "Shadowban",
    "No distribuir",
    "Requiere calentamiento",
    "Revisión manual",
]

MAX_PER_SESSION = 10
DELAY_MIN = 300    # 5 min
DELAY_MAX = 600    # 10 min

TIMEZONE_MAP = {
    "Buenos Aires": "America/Argentina/Buenos_Aires",
    "Caracas":      "America/Caracas",
    "New York":     "America/New_York",
    "Chicago":      "America/Chicago",
    "Los Angeles":  "America/Los_Angeles",
    "Madrid":       "Europe/Madrid",
    "London":       "Europe/London",
}
TZ_TO_LABEL = {v: k for k, v in TIMEZONE_MAP.items()}

DAY_NAMES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
DEFAULT_CATEGORIES = ["promo", "suicide", "general"]

_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/121.0.6167.171 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.143 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36 SamsungBrowser/23.0",
    "Mozilla/5.0 (Linux; Android 13; OnePlus 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.184 Safari/537.36",
]
_ACCEPT_LANGS = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "en-US,en;q=0.9,es;q=0.8",
    "es-US,es;q=0.9,en;q=0.8",
    "en-US,en;q=0.8",
]


def _load_panel_config() -> dict:
    if os.path.exists(PANEL_CONFIG_FILE):
        try:
            import json
            with open(PANEL_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"cookie": "", "proxy": ""}


def _save_panel_config(data: dict):
    import json
    with open(PANEL_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _random_headers(cookie: str) -> dict:
    return {
        "User-Agent":                random.choice(_USER_AGENTS),
        "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language":           random.choice(_ACCEPT_LANGS),
        "Accept-Encoding":           "gzip, deflate, br",
        "Connection":                "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest":            "document",
        "Sec-Fetch-Mode":            "navigate",
        "Sec-Fetch-Site":            "none",
        "Sec-Fetch-User":            "?1",
        "Cache-Control":             "max-age=0",
        "Cookie":                    cookie,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PANEL DE ESTADO DE CUENTAS
# ══════════════════════════════════════════════════════════════════════════════
class AccountStatusPanel(ctk.CTkFrame):
    """Panel de control de cuentas IG con verificación HTTP sigilosa."""

    def __init__(self, master, db, **kwargs):
        super().__init__(master, fg_color=BG_APP, corner_radius=0, **kwargs)
        self.db = db
        self._stop_flag = False
        self._checking  = False
        self._rows: dict = {}   # username → {circle, combo, lbl_label}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self._build_header()
        self._build_config_card()
        self._build_controls()
        self._build_table_header()
        self._build_scroll_area()
        self.load_accounts()

    # ── Construcción UI ───────────────────────────────────────────────────────

    def _build_header(self):
        PageHeader(
            self, "LEGACY", "Verify Legacy",
            f"Verificación HTTP con cookies y proxy · máx {MAX_PER_SESSION} cuentas por sesión."
        ).grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))

    def _build_config_card(self):
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        card.grid(row=1, column=0, sticky="ew", padx=24, pady=(14, 0))
        card.grid_columnconfigure(1, weight=1)

        cfg = _load_panel_config()

        ctk.CTkLabel(card, text="Cookie Instagram:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(20, 10), pady=(16, 6), sticky="e")
        self.e_cookie = ctk.CTkEntry(
            card, fg_color=BG_INPUT, border_color=BORDER,
            placeholder_text="sessionid=xxxxx; ds_user_id=xxxxx; csrftoken=xxxxx; ..."
        )
        self.e_cookie.grid(row=0, column=1, padx=(0, 10), pady=(16, 6), sticky="ew")
        if cfg.get("cookie"):
            self.e_cookie.insert(0, cfg["cookie"])

        ctk.CTkLabel(card, text="Proxy (opcional):", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=1, column=0, padx=(20, 10), pady=(0, 16), sticky="e")
        self.e_proxy = ctk.CTkEntry(
            card, fg_color=BG_INPUT, border_color=BORDER,
            placeholder_text="http://usuario:contraseña@host:puerto  (vacío = sin proxy)"
        )
        self.e_proxy.grid(row=1, column=1, padx=(0, 10), pady=(0, 16), sticky="ew")
        if cfg.get("proxy"):
            self.e_proxy.insert(0, cfg["proxy"])

        PrimaryButton(
            card, text="Guardar", width=110, command=self._save_cfg
        ).grid(row=0, column=2, rowspan=2, padx=20, pady=16)

    def _build_controls(self):
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.grid(row=2, column=0, sticky="ew", padx=24, pady=10)
        ctrl.grid_columnconfigure(7, weight=1)

        self.btn_check = PrimaryButton(
            ctrl, text=f"Verificar (máx {MAX_PER_SESSION})",
            command=self.start_check
        )
        self.btn_check.grid(row=0, column=0, padx=(0, 8))

        self.btn_stop = DangerButton(
            ctrl, text="Detener",
            state="disabled", command=self.stop_check
        )
        self.btn_stop.grid(row=0, column=1, padx=(0, 8))

        GhostButton(
            ctrl, text="Reiniciar", command=self._reset_all_status
        ).grid(row=0, column=2, padx=(0, 8))

        GhostButton(
            ctrl, text="Recargar lista", command=self.load_accounts
        ).grid(row=0, column=3, padx=(0, 8))

        self.btn_delete_sel = DangerButton(
            ctrl, text="Eliminar sel.",
            command=self._delete_selected
        )
        self.btn_delete_sel.grid(row=0, column=4, padx=(0, 6))

        self.lbl_sel_count = ctk.CTkLabel(ctrl, text="", text_color=WARNING,
                                           font=ctk.CTkFont(size=11, weight="bold"), width=52)
        self.lbl_sel_count.grid(row=0, column=5, padx=(0, 12))

        self.lbl_progress = ctk.CTkLabel(ctrl, text="", text_color=TEXT_MUTED,
                                          font=ctk.CTkFont(size=11))
        self.lbl_progress.grid(row=0, column=6, padx=(0, 12))

        self.pb = ctk.CTkProgressBar(ctrl, fg_color=BG_INPUT, progress_color=NEON_CYAN, height=8)
        self.pb.grid(row=0, column=7, sticky="ew")
        self.pb.set(0)

    def _build_table_header(self):
        hdr = ctk.CTkFrame(self, fg_color=BG_CARD2, corner_radius=0, height=32)
        hdr.grid(row=3, column=0, sticky="ew", padx=24, pady=(4, 0))
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(2, weight=1)

        self._select_all_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            hdr, text="", variable=self._select_all_var,
            checkbox_width=16, checkbox_height=16,
            fg_color=NEON_PURPLE, hover_color=NEON_CYAN,
            command=self._toggle_all, width=36
        ).grid(row=0, column=0, padx=(14, 4), pady=4)

        cols = [
            ("Estado HTTP", 90,  "center"),
            ("Usuario",     0,   "w"),
            ("Etiqueta",    160, "center"),
            ("VA Asignado", 180, "w"),
            ("Tipo",        110, "center"),
        ]
        for i, (text, w, anchor) in enumerate(cols):
            col = i + 1
            if w == 0:
                hdr.grid_columnconfigure(col, weight=1)
            lbl = ctk.CTkLabel(
                hdr, text=text, text_color=NEON_CYAN,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor=anchor, width=w if w else 0
            )
            padx = (4, 8) if i == 0 else (8, 8)
            lbl.grid(row=0, column=col, padx=padx, pady=4, sticky="ew" if w == 0 else "")

    def _build_scroll_area(self):
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color=BG_CARD, corner_radius=CARD_RADIUS
        )
        self.scroll_frame.grid(row=4, column=0, sticky="nsew", padx=24, pady=(0, 20))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

    # ── Carga de filas ────────────────────────────────────────────────────────

    def load_accounts(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self._rows = {}
        for i, acc in enumerate(self.db.get_all_accounts()):
            self._add_row(i, acc)
        total = len(self._rows)
        unknown = sum(
            1 for u, d in self._rows.items()
            if d["circle"].cget("text_color") == "#64748b"
        )
        self.lbl_progress.configure(
            text=f"{total} cuentas · {unknown} sin verificar"
        )

    def _add_row(self, index: int, acc: dict):
        username  = acc["username"]
        va        = acc.get("assigned_va") or "Sin Asignar"
        acc_type  = acc.get("account_type", "—")
        status    = acc.get("ig_status", "unknown")
        label_val = acc.get("ig_label", "nuevo")
        if label_val not in LABEL_OPTIONS:
            label_val = "nuevo"

        row_bg = BG_CARD if index % 2 == 0 else BG_CARD2
        row = ctk.CTkFrame(self.scroll_frame, fg_color=row_bg, corner_radius=4)
        row.grid(row=index, column=0, sticky="ew", pady=1, padx=2)
        row.grid_columnconfigure(2, weight=1)

        select_var = tk.BooleanVar(value=False)
        chk = ctk.CTkCheckBox(
            row, text="", variable=select_var,
            checkbox_width=16, checkbox_height=16,
            fg_color=NEON_PURPLE, hover_color=NEON_CYAN,
            command=self._update_selected_count, width=36
        )
        chk.grid(row=0, column=0, padx=(14, 4), pady=8)

        circle_color = (
            SUCCESS   if status == "alive"
            else DANGER   if status == "dead"
            else "#64748b"
        )
        circle = ctk.CTkLabel(
            row, text="⬤", text_color=circle_color,
            font=ctk.CTkFont(size=18), width=90, anchor="center"
        )
        circle.grid(row=0, column=1, padx=(4, 8), pady=8)

        ctk.CTkLabel(
            row, text=f"@{username}", text_color=TEXT_BODY,
            font=ctk.CTkFont(size=12), anchor="w"
        ).grid(row=0, column=2, padx=8, pady=8, sticky="ew")

        combo = ctk.CTkComboBox(
            row, values=LABEL_OPTIONS,
            fg_color=BG_INPUT, border_color=BORDER,
            button_color=NEON_PURPLE, dropdown_fg_color=BG_CARD2,
            width=150, state="readonly",
            command=lambda val, u=username: self._on_label_change(u, val)
        )
        combo.set(label_val)
        combo.grid(row=0, column=3, padx=8, pady=6)

        # Indicador de color según etiqueta
        label_dot = ctk.CTkLabel(
            row, text="⬤",
            text_color=LABEL_COLORS.get(label_val, "#64748b"),
            font=ctk.CTkFont(size=10), width=16
        )
        label_dot.grid(row=0, column=3, padx=(8, 0), pady=8, sticky="e")

        ctk.CTkLabel(
            row, text=va, text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11), width=180, anchor="w"
        ).grid(row=0, column=4, padx=(8, 8), pady=8, sticky="w")

        ctk.CTkLabel(
            row, text=acc_type, text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11), width=110, anchor="center"
        ).grid(row=0, column=5, padx=(8, 20), pady=8)

        self._rows[username] = {"circle": circle, "combo": combo, "dot": label_dot, "select_var": select_var}

    # ── Acciones de usuario ───────────────────────────────────────────────────

    def _save_cfg(self):
        _save_panel_config({
            "cookie": self.e_cookie.get().strip(),
            "proxy":  self.e_proxy.get().strip(),
        })
        messagebox.showinfo("✅ Guardado", "Configuración guardada correctamente.")

    def _on_label_change(self, username: str, value: str):
        self.db.update_account(username, ig_label=value)
        if username in self._rows:
            self._rows[username]["dot"].configure(
                text_color=LABEL_COLORS.get(value, "#64748b")
            )

    def _reset_all_status(self):
        if not messagebox.askyesno(
            "Reiniciar estado",
            "¿Marcar todas las cuentas como 'sin verificar'?\n"
            "Esto permite lanzar una nueva sesión completa."
        ):
            return
        for username in self._rows:
            self.db.update_account(username, ig_status="unknown")
            self._rows[username]["circle"].configure(text_color="#64748b")
        self.pb.set(0)
        self.lbl_progress.configure(text="Estado reiniciado — listo para nueva sesión")

    def _toggle_all(self):
        val = self._select_all_var.get()
        for d in self._rows.values():
            d["select_var"].set(val)
        self._update_selected_count()

    def _update_selected_count(self):
        n = sum(1 for d in self._rows.values() if d["select_var"].get())
        self.lbl_sel_count.configure(text=f"{n} sel." if n else "")
        # Si alguno fue desmarcado manualmente, quitar el "seleccionar todo"
        if not n:
            self._select_all_var.set(False)

    def _delete_selected(self):
        selected = [u for u, d in self._rows.items() if d["select_var"].get()]
        if not selected:
            messagebox.showinfo("Sin selección", "Seleccioná al menos una cuenta para eliminar.")
            return
        preview = "\n".join(f"  • @{u}" for u in selected[:10])
        if len(selected) > 10:
            preview += f"\n  … y {len(selected) - 10} más"
        if not messagebox.askyesno(
            "Eliminar cuentas",
            f"¿Eliminar {len(selected)} cuenta(s) permanentemente?\n\n{preview}"
        ):
            return
        for u in selected:
            self.db.delete_account(u)
        self._select_all_var.set(False)
        self.load_accounts()

    def start_check(self):
        if self._checking:
            return

        cookie = self.e_cookie.get().strip() or _load_panel_config().get("cookie", "")
        if not cookie:
            messagebox.showwarning("⚠️ Cookie requerida",
                                   "Ingresa una cookie de Instagram antes de verificar.")
            return

        pending = [
            u for u, data in self._rows.items()
            if data["circle"].cget("text_color") == "#64748b"
        ]
        if not pending:
            all_accs = self.db.get_all_accounts()
            pending = [a["username"] for a in all_accs if a.get("ig_status", "unknown") == "unknown"]

        if not pending:
            messagebox.showinfo(
                "✅ Todo verificado",
                "Todas las cuentas ya tienen estado.\n"
                "Usa '🔄 Reiniciar' para empezar una nueva sesión."
            )
            return

        batch = pending[:MAX_PER_SESSION]
        remaining_after = len(pending) - len(batch)

        proxy_raw = self.e_proxy.get().strip() or _load_panel_config().get("proxy", "")
        proxies = {"http": proxy_raw, "https": proxy_raw} if proxy_raw else None

        self._stop_flag = False
        self._checking  = True
        self.btn_check.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.pb.set(0)
        self.lbl_progress.configure(
            text=f"Sesión iniciada — {len(batch)} cuentas · {remaining_after} pendientes después"
        )

        def worker():
            total = len(batch)
            for idx, username in enumerate(batch):
                if self._stop_flag:
                    break
                self.after(0, lambda u=username, i=idx, t=total:
                    self.lbl_progress.configure(text=f"🔍 Verificando @{u}  ({i + 1}/{t})"))

                status = self._check_account(username, cookie, proxies)
                self.db.update_account(username, ig_status=status)
                self.after(0, lambda u=username, s=status: self._update_circle(u, s))
                self.after(0, lambda i=idx + 1, t=total: self.pb.set(i / t))

                if idx < total - 1 and not self._stop_flag:
                    wait = random.randint(DELAY_MIN, DELAY_MAX)
                    self._countdown(wait, idx + 1, total)

            self.after(0, self._on_check_done)

        threading.Thread(target=worker, daemon=True).start()

    def stop_check(self):
        self._stop_flag = True
        self.lbl_progress.configure(text="⏹ Deteniendo tras la cuenta actual...")

    # ── Verificación HTTP ─────────────────────────────────────────────────────

    def _check_account(self, username: str, cookie: str, proxies) -> str:
        time.sleep(random.uniform(0.5, 3.0))
        url     = f"https://www.instagram.com/{username}/"
        headers = _random_headers(cookie)
        try:
            resp = requests.get(url, headers=headers, proxies=proxies,
                                timeout=15, allow_redirects=True)
            if "accounts/login" in resp.url or "challenge" in resp.url:
                return "dead"
            if resp.status_code == 404:
                return "dead"
            if resp.status_code == 200:
                low = resp.text.lower()
                dead_phrases = [
                    "sorry, this page", "esta página no está disponible",
                    "user not found", "we suspended", "page not found",
                ]
                if any(p in low for p in dead_phrases):
                    return "dead"
                return "alive"
            return "dead"
        except Exception:
            return "dead"

    # ── Countdown ─────────────────────────────────────────────────────────────

    def _countdown(self, seconds: int, done: int, total: int):
        for remaining in range(seconds, 0, -1):
            if self._stop_flag:
                return
            m, s = divmod(remaining, 60)
            text = f"⏳ Próxima en {m}m {s:02d}s  —  {done}/{total} verificadas"
            self.after(0, lambda t=text: self.lbl_progress.configure(text=t))
            time.sleep(1)

    # ── Actualización de UI ───────────────────────────────────────────────────

    def _update_circle(self, username: str, status: str):
        if username not in self._rows:
            return
        color = SUCCESS if status == "alive" else DANGER
        self._rows[username]["circle"].configure(text_color=color)

    def _on_check_done(self):
        self._checking  = False
        self._stop_flag = False
        self.btn_check.configure(state="normal")
        self.btn_stop.configure(state="disabled")

        all_accs      = self.db.get_all_accounts()
        still_pending = sum(1 for a in all_accs if a.get("ig_status", "unknown") == "unknown")
        if still_pending:
            self.lbl_progress.configure(
                text=f"✅ Sesión completa  —  {still_pending} cuentas pendientes para la próxima"
            )
        else:
            self.lbl_progress.configure(text="✅ Todas las cuentas verificadas")
        self.pb.set(1)

    def refresh(self):
        """Recarga la lista al cambiar a esta pestaña."""
        self.load_accounts()


# ══════════════════════════════════════════════════════════════════════════════
# WORKER THREAD  (idéntico a gui_unificada.py — no modificar)
# ══════════════════════════════════════════════════════════════════════════════
class WorkerThread(threading.Thread):
    def __init__(self, root, callback, task, *args, **kwargs):
        super().__init__()
        self.root = root
        self.callback = callback
        self.task = task
        self.args = args
        self.kwargs = kwargs
        self.daemon = True

    def run(self):
        try:
            res = self.task(*self.args, **self.kwargs)
            if self.callback:
                self.root.after(0, lambda r=res: self.callback(True, r))
        except Exception as e:
            error_msg = str(e)
            if self.callback:
                self.root.after(0, lambda m=error_msg: self.callback(False, m))


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGOS PREMIUM (portados de gui_unificada.py a CTkToplevel)
# ══════════════════════════════════════════════════════════════════════════════
class SelectionDialog(ctk.CTkToplevel):
    """Diálogo para seleccionar o crear una categoría / VA."""
    def __init__(self, parent, title, prompt, items):
        super().__init__(parent)
        self.title(title)
        self.geometry("380x260")
        self.configure(fg_color=BG_CARD)
        self.result = None
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        ctk.CTkLabel(self, text=prompt, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT_H1).pack(pady=(20, 5), padx=20, anchor="w")

        ctk.CTkLabel(self, text="Selecciona existente:", font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED).pack(padx=20, anchor="w")
        self.combo = ctk.CTkComboBox(self, values=items, state="readonly",
                                     fg_color=BG_INPUT, border_color=BORDER,
                                     button_color=NEON_CYAN, dropdown_fg_color=BG_CARD2)
        self.combo.pack(padx=20, pady=(4, 10), fill="x")

        ctk.CTkLabel(self, text="O escribe uno nuevo:", font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED).pack(padx=20, anchor="w")
        self.entry = ctk.CTkEntry(self, fg_color=BG_INPUT, border_color=BORDER,
                                  placeholder_text="Nombre nuevo...")
        self.entry.pack(padx=20, pady=(4, 16), fill="x")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(padx=20, fill="x")
        ctk.CTkButton(btn_row, text="✅ Aplicar", fg_color=NEON_CYAN,
                      text_color=BG_APP, hover_color="#00c9b0",
                      corner_radius=BTN_RADIUS, command=self._confirm).pack(side="left", padx=(0,8))
        ctk.CTkButton(btn_row, text="Cancelar", fg_color=BG_CARD2,
                      text_color=TEXT_MUTED, hover_color=BORDER,
                      corner_radius=BTN_RADIUS, command=self.destroy).pack(side="left")

    def _confirm(self):
        new_val = self.entry.get().strip()
        sel = self.combo.get()
        self.result = new_val if new_val else sel
        if self.result:
            self.destroy()
        else:
            messagebox.showwarning("⚠️", "Selecciona o escribe algo.")


def build_bulk_account_updates(category: str, assigned_va: str) -> dict:
    """Construye el dict de campos a actualizar, ignorando 'Sin cambios'."""
    updates = {}
    if category and category != "Sin cambios":
        updates["account_type"] = category
    if assigned_va and assigned_va != "Sin cambios":
        updates["assigned_va"] = assigned_va
    return updates


def airtable_sync_review_text(plan) -> str:
    """Resumen seguro: incluye cuentas afectadas, nunca credenciales ni secretos."""
    lines = [
        "Cambios detectados desde Airtable:",
        f"• {len(plan.create)} creadas",
        f"• {len(plan.update)} actualizadas",
        f"• {len(plan.delete_usernames)} eliminadas",
    ]
    for title, usernames in (
        ("Crear", [row["username"] for row in plan.create]),
        ("Actualizar", [row["username"] for row in plan.update]),
        ("Eliminar", plan.delete_usernames),
    ):
        if usernames:
            preview = ", ".join(f"@{name}" for name in usernames[:10])
            extra = f" y {len(usernames) - 10} más" if len(usernames) > 10 else ""
            lines.append(f"{title}: {preview}{extra}")
    if plan.delete_usernames:
        lines.append(
            "Las eliminadas salen solo de la tabla local; no se borran videos, calendarios ni historial."
        )
    return "\n".join(lines)


def airtable_mirror_review_text(plan) -> str:
    """Resume el espejo GUI -> Airtable antes de aplicar cambios destructivos."""
    lines = [
        "Cambios detectados: GUI → Airtable",
        f"• {len(plan.create)} creadas",
        f"• {len(plan.update)} actualizadas",
        f"• {len(plan.delete)} eliminadas",
        "La GUI será la fuente de verdad para las 9 columnas administradas.",
    ]
    for title, usernames in (
        ("Crear", [row["Username"] for row in plan.create]),
        ("Actualizar", [row["username"] for row in plan.update]),
        ("Eliminar", [row["username"] for row in plan.delete]),
    ):
        if usernames:
            preview = ", ".join(f"@{name}" for name in usernames[:10])
            extra = f" y {len(usernames) - 10} más" if len(usernames) > 10 else ""
            lines.append(f"{title}: {preview}{extra}")
    if plan.delete:
        lines.append("Las eliminaciones en Airtable no se pueden deshacer desde la GUI.")
    return "\n".join(lines)


def airtable_schema_preparation_text(result) -> str:
    """Resume cambios de esquema sin incluir el token local."""
    if result.source_renames:
        lines = [
            "Se renombraron las primeras 9 columnas por posición, sin buscar nombres.",
            "Orden: Username, 2FA, VA, Categoria, Trials desbloqueados, Dia, Red social, VPN / Proxy, Link.",
        ]
        if result.backup_renames:
            lines.append(
                "Las columnas duplicadas se renombraron como respaldo y no se borraron."
            )
    elif result.added_fields:
        lines = [f"Columnas agregadas: {', '.join(result.added_fields)}."]
    else:
        lines = ["La tabla ya tenía todas las columnas requeridas."]
    if result.incompatible_fields:
        details = ", ".join(
            f"{name} ({actual}; se esperaba {expected})"
            for name, actual, expected in result.incompatible_fields
        )
        lines.append(f"Estas columnas ya existían y no se modificó su tipo: {details}.")
    lines.append("Conexión guardada en esta GUI.")
    return "\n".join(lines)


def resolve_selected_account_ids(accounts: list[dict], usernames: list[str]) -> list[int]:
    """Resuelve los IDs de cuenta a partir de los usernames seleccionados en la tabla."""
    selected = set(usernames)
    return [account["id"] for account in accounts if account["username"] in selected]


class BulkEditAccountsDialog(ctk.CTkToplevel):
    """Diálogo para editar categoría y/o VA de varias cuentas seleccionadas a la vez."""
    def __init__(self, parent, count, categories, vas):
        super().__init__(parent)
        self.title("Editar cuentas seleccionadas")
        self.geometry("380x300")
        self.configure(fg_color=BG_CARD)
        self.result = None
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        plural = "s" if count != 1 else ""
        ctk.CTkLabel(self, text=f"{count} cuenta{plural} seleccionada{plural}",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT_H1).pack(pady=(20, 10), padx=20, anchor="w")

        ctk.CTkLabel(self, text="Categoría:", font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED).pack(padx=20, anchor="w")
        self.cat_menu = ctk.CTkOptionMenu(self, values=["Sin cambios"] + list(categories),
                                          fg_color=BG_INPUT, button_color=NEON_CYAN)
        self.cat_menu.set("Sin cambios")
        self.cat_menu.pack(padx=20, pady=(4, 10), fill="x")

        ctk.CTkLabel(self, text="VA:", font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED).pack(padx=20, anchor="w")
        self.va_menu = ctk.CTkOptionMenu(self, values=["Sin cambios", "Sin Asignar"] + list(vas),
                                         fg_color=BG_INPUT, button_color=NEON_CYAN)
        self.va_menu.set("Sin cambios")
        self.va_menu.pack(padx=20, pady=(4, 16), fill="x")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(padx=20, fill="x")
        ctk.CTkButton(btn_row, text="✅ Aplicar", fg_color=NEON_CYAN,
                      text_color=BG_APP, hover_color="#00c9b0",
                      corner_radius=BTN_RADIUS, command=self._confirm).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Cancelar", fg_color=BG_CARD2,
                      text_color=TEXT_MUTED, hover_color=BORDER,
                      corner_radius=BTN_RADIUS, command=self.destroy).pack(side="left")

    def _confirm(self):
        category = self.cat_menu.get()
        assigned_va = self.va_menu.get()
        if not build_bulk_account_updates(category, assigned_va):
            messagebox.showwarning("⚠️", "Elige al menos un cambio.")
            return
        self.result = (category, assigned_va)
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# APLICACIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
class InstagramAutoPro(ctk.CTk):

    # ── Init ──────────────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()
        self.title("⚡ Instagram Automation Pro  —  V7")
        self._apply_responsive_window()
        self.configure(fg_color=BG_APP)

        self.db = DatabaseManager()
        self._active_nav = None
        self._render_worker_controls = []
        self._render_worker_syncing = False
        self._editor_render_active = False

        # Estado de rutas (Tandas)
        self.p1_dir = ""
        self.p2_dir = ""
        self.tg_controller = None
        self._tg_accounts = []
        self._tg_only_with_videos = None  # se inicializa en _build_tg_frame

        # Configurar Treeview con estilo premium
        self._setup_treeview_style()

        # Layout: sidebar (col 0) | contenido (col 1) / status bar (row 1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_content_area()
        self._build_status_bar()

        self.show_frame("Dashboard")
        self._update_clock()
        self.after(250, self._show_startup_greeting)
        self.after(1600, self._show_update_notice)

    def _apply_responsive_window(self):
        screen_w = max(1, self.winfo_screenwidth())
        screen_h = max(1, self.winfo_screenheight())
        width = max(MIN_WINDOW_W, min(DESIGN_WINDOW_W, screen_w - SCREEN_MARGIN_W))
        height = max(MIN_WINDOW_H, min(DESIGN_WINDOW_H, screen_h - SCREEN_MARGIN_H))

        self.minsize(MIN_WINDOW_W, MIN_WINDOW_H)
        self.geometry(f"{width}x{height}")

    def _fit_toplevel(self, window, width, height):
        screen_w = max(1, window.winfo_screenwidth())
        screen_h = max(1, window.winfo_screenheight())
        fitted_w = max(360, min(width, screen_w - SCREEN_MARGIN_W))
        fitted_h = max(320, min(height, screen_h - SCREEN_MARGIN_H))
        window.geometry(f"{fitted_w}x{fitted_h}")
        return fitted_w, fitted_h

    def _show_startup_greeting(self):
        """Small startup toast used to verify an installed update visually."""
        toast = ctk.CTkToplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(fg_color=BG_CARD)

        width, height = 250, 96
        self.update_idletasks()
        x = self.winfo_rootx() + max((self.winfo_width() - width) // 2, 0)
        y = self.winfo_rooty() + max((self.winfo_height() - height) // 2, 0)
        toast.geometry(f"{width}x{height}+{x}+{y}")

        card = ctk.CTkFrame(
            toast, fg_color=BG_CARD2, corner_radius=8,
            border_width=1, border_color=NEON_CYAN
        )
        card.pack(fill="both", expand=True, padx=1, pady=1)
        ctk.CTkLabel(
            card, text="Hola!!", text_color=NEON_CYAN,
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(expand=True)

        def fade(alpha=1.0):
            if alpha <= 0:
                toast.destroy()
                return
            try:
                toast.attributes("-alpha", alpha)
            except tk.TclError:
                toast.after(1200, toast.destroy)
                return
            toast.after(70, lambda: fade(alpha - 0.1))

        toast.after(600, fade)

    def _show_update_notice(self):
        """Show one gentle notice when the silent update check could not run."""
        status_file = os.path.join(_BASE_DIR, ".update_status.json")
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status = json.load(f)
            error = status.get("error", "") if isinstance(status, dict) else ""
            try:
                os.remove(status_file)
            except OSError:
                pass
        except (OSError, ValueError, TypeError):
            return

        if not isinstance(error, str) or not error.strip():
            return

        toast = ctk.CTkToplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(fg_color=BG_CARD)

        width, height = 410, 118
        self.update_idletasks()
        x = self.winfo_rootx() + max((self.winfo_width() - width) // 2, 0)
        y = self.winfo_rooty() + max((self.winfo_height() - height) // 2, 0)
        toast.geometry(f"{width}x{height}+{x}+{y}")

        card = ctk.CTkFrame(
            toast, fg_color=BG_CARD2, corner_radius=8,
            border_width=1, border_color=INFO
        )
        card.pack(fill="both", expand=True, padx=1, pady=1)
        ctk.CTkLabel(
            card, text="Actualizaciones", text_color=INFO,
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(pady=(16, 4), padx=20)
        ctk.CTkLabel(
            card,
            text=("No se pudieron comprobar actualizaciones. Configura tu token\n"
                  "en Actualizaciones para no perderte las novedades."),
            text_color=TEXT_BODY, justify="center",
            font=ctk.CTkFont(size=12)
        ).pack(padx=20)

        def fade(alpha=1.0):
            if alpha <= 0:
                toast.destroy()
                return
            try:
                toast.attributes("-alpha", alpha)
            except tk.TclError:
                toast.after(1200, toast.destroy)
                return
            toast.after(70, lambda: fade(alpha - 0.1))

        toast.after(2800, fade)

    def themed(self, value):
        """Resolve a (light, dark) color token to a single color for the
        current appearance mode. Use for raw Tk/ttk widgets that cannot
        consume CustomTkinter tuples."""
        return resolve(value, ctk.get_appearance_mode())

    def _apply_theme(self, mode: str):
        """Switch appearance mode and re-color the raw Tk/ttk widgets that
        do not auto-update. `mode` is 'Light', 'Dark', or 'System'."""
        # Hide the window during the recolor so the user never sees CTk's
        # torn intermediate repaint, then show it fully re-themed. Preserve the
        # maximized state, which deiconify() would otherwise drop on Windows.
        prev_state = self.state()
        try:
            self.withdraw()
            ctk.set_appearance_mode(mode)
            self._restyle_raw_tk()
            self.update_idletasks()
        finally:
            self.deiconify()
            if prev_state == "zoomed":
                self.state("zoomed")

    def _on_theme_change(self, choice: str):
        self._apply_theme({"Claro": "Light", "Oscuro": "Dark", "Sistema": "System"}[choice])

    def _restyle_raw_tk(self):
        """Re-apply mode-correct colors to the ttk Treeview style and the
        raw Tk Listboxes (CustomTkinter widgets recolor themselves)."""
        self._setup_treeview_style()
        for lb in (
            getattr(self, "list_tg", None),
            getattr(self, "forge_lst", None),
            getattr(self, "photo_forge_sources", None),
            getattr(self, "photo_forge_accounts", None),
        ):
            if lb is not None:
                lb.configure(
                    bg=self.themed(BG_INPUT), fg=self.themed(TEXT_BODY),
                    selectbackground=self.themed(ACCENT),
                    selectforeground=self.themed(ACCENT_TEXT),
                    highlightbackground=self.themed(BORDER),
                )
        if getattr(self, "tree", None) is not None:
            self.tree.tag_configure("odd",  background=self.themed(BG_CARD2))
            self.tree.tag_configure("even", background=self.themed(BG_CARD))
        if getattr(self, "tg_log", None) is not None:
            self.tg_log.tag_config("INFO", foreground=self.themed(INFO))
            self.tg_log.tag_config("SUCCESS", foreground=self.themed(SUCCESS))
            self.tg_log.tag_config("WARNING", foreground=self.themed(WARNING))
            self.tg_log.tag_config("ERROR", foreground=self.themed(DANGER))

    def _setup_treeview_style(self):
        """Aplica tema oscuro premium al ttk.Treeview estándar."""
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Premium.Treeview",
                        background=self.themed(BG_CARD), foreground=self.themed(TEXT_BODY),
                        fieldbackground=self.themed(BG_CARD), bordercolor=self.themed(BORDER),
                        rowheight=30, font=FONT_BODY, borderwidth=0)
        style.configure("Premium.Treeview.Heading",
                        background=self.themed(BG_CARD2), foreground=self.themed(TEXT_MUTED),
                        font=FONT_H3, borderwidth=0, relief="flat")
        style.map("Premium.Treeview",
                  background=[("selected", self.themed(ACCENT))],
                  foreground=[("selected", self.themed(ACCENT_TEXT))])

    # ── Sidebar ───────────────────────────────────────────────────────────
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self, width=SIDEBAR_W, corner_radius=0,
            fg_color=BG_SIDEBAR, border_width=1, border_color=BORDER
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(2, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_propagate(False)

        # — Logo —
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=16, pady=(20, 10), sticky="ew")
        tile = ctk.CTkLabel(brand, text="IA", width=40, height=40,
                            corner_radius=12, fg_color=ACCENT, text_color=ACCENT_TEXT,
                            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"))
        tile.grid(row=0, column=0, rowspan=2, padx=(0, 10))
        ctk.CTkLabel(brand, text="IG AUTO PRO", anchor="w",
                     font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                     text_color=TEXT_H1).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(brand, text="AUTOMATION SUITE", anchor="w",
                     font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=1, column=1, sticky="nw")

        # — Separador —
        ctk.CTkFrame(self.sidebar, height=1, fg_color=BORDER).grid(
            row=1, column=0, sticky="ew", padx=16, pady=(4, 8))

        self.sidebar_nav = ctk.CTkScrollableFrame(
            self.sidebar, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=ACCENT,
        )
        self.sidebar_nav.grid(row=2, column=0, sticky="nsew", padx=0, pady=(0, 8))
        self.sidebar_nav.grid_columnconfigure(0, weight=1)

        # — Navegación agrupada por flujo de trabajo —
        nav_groups = [
            ("Edición",       [("🖼️   Edición de video", "VideoEditor")]),
            ("Contenido",    [("🔮   Forge", "Forge"), ("🖼️   Photo Forge", "PhotoForge"),
                              ("🎬   Tandas", "Tandas")]),
            ("Distribución", [("🚀   Logística", "Logistica"), ("🗓️   Calendario", "Calendario"),
                              ("📡   Cuentas", "Cuentas"), ("📲   Telegram", "Telegram")]),
            ("Control",      [("📊   Dashboard", "Dashboard")]),
            ("Sistema",      [("⚙️   Admin", "Equipo"), ("🔍   Verify Legacy", "VerifyLegacy"),
                              ("⬇   Actualizaciones", "Actualizaciones")]),
        ]
        self._nav_btns = {}
        row = 0
        for group_name, items in nav_groups:
            ctk.CTkLabel(self.sidebar_nav, text=group_name.upper(), anchor="w",
                         font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                         text_color=TEXT_MUTED).grid(row=row, column=0, padx=18,
                                                     pady=(10, 2), sticky="w")
            row += 1
            for label, key in items:
                btn = NavItem(self.sidebar_nav, text=label, command=lambda k=key: self.show_frame(k))
                btn.grid(row=row, column=0, padx=10, pady=2, sticky="ew")
                self._nav_btns[key] = btn
                row += 1

        # — Selector de tema —
        self.theme_seg = ctk.CTkSegmentedButton(
            self.sidebar_nav, values=["Claro", "Oscuro", "Sistema"],
            command=self._on_theme_change,
            fg_color=SURFACE2, selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
            unselected_color=SURFACE2, text_color=TEXT_BODY,
            font=ctk.CTkFont(family="Segoe UI", size=11), height=30, corner_radius=BTN_RADIUS,
        )
        self.theme_seg.set("Sistema")
        self.theme_seg.grid(row=row, column=0, padx=14, pady=(14, 4), sticky="ew")
        row += 1

        # — Status del bot (parte inferior sidebar) —
        ctk.CTkFrame(self.sidebar_nav, height=1, fg_color=BORDER).grid(
            row=row, column=0, sticky="ew", padx=16, pady=(8, 4))
        row += 1
        self.lbl_bot_status = ctk.CTkLabel(
            self.sidebar_nav, text="⬤  Bot inactivo",
            font=ctk.CTkFont(size=11), text_color=TEXT_MUTED)
        self.lbl_bot_status.grid(row=row, column=0, padx=18, pady=(0, 18), sticky="sw")

    def set_bot_status(self, active: bool):
        """Actualiza indicador de bot en la sidebar."""
        if active:
            self.lbl_bot_status.configure(text="⬤  Bot activo", text_color=SUCCESS)
        else:
            self.lbl_bot_status.configure(text="⬤  Bot inactivo", text_color=TEXT_MUTED)

    # ── Área de Contenido ─────────────────────────────────────────────────
    def _build_content_area(self):
        self._frames = {}
        container = ctk.CTkFrame(self, fg_color=BG_APP, corner_radius=0)
        container.grid(row=0, column=1, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        self._container = container

        for name in ["Dashboard", "Equipo", "Tandas", "Logistica", "Calendario", "Telegram", "Cuentas", "VerifyLegacy", "AIAdvisor", "Forge", "PhotoForge", "VideoEditor", "Actualizaciones"]:
            f = ctk.CTkFrame(container, fg_color=BG_APP, corner_radius=0)
            f.grid(row=0, column=0, sticky="nsew")
            f.grid_columnconfigure(0, weight=1)
            self._frames[name] = f

        # Construir contenido de cada frame
        self._build_dashboard_frame()
        self._build_team_frame()
        self._build_mix_frame()
        self._build_dist_frame()
        self._build_calendar_frame()
        self._build_tg_frame()
        self._build_cuentas_frame()
        self._build_verify_legacy_frame()
        self._build_ai_frame()
        self._build_forge_frame()
        self._build_photo_forge_frame()
        self._build_video_editor_frame()
        self._build_updates_frame()

    # ── Status Bar ────────────────────────────────────────────────────────
    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, height=STATUS_H, corner_radius=0,
                           fg_color=BG_SIDEBAR, border_width=1, border_color=BORDER)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_propagate(False)

        ctk.CTkLabel(bar, text="⚡ Instagram Automation Pro  v7",
                     font=ctk.CTkFont(size=10), text_color=TEXT_MUTED
                     ).grid(row=0, column=0, padx=14, pady=4, sticky="w")

        self.lbl_clock = ctk.CTkLabel(bar, text="",
                                       font=ctk.CTkFont(size=10), text_color=TEXT_MUTED)
        self.lbl_clock.grid(row=0, column=2, padx=14, pady=4, sticky="e")

    # ── Navegación ────────────────────────────────────────────────────────
    def show_frame(self, name: str):
        if self._active_nav and self._active_nav in self._nav_btns:
            self._nav_btns[self._active_nav].set_active(False)
        if name in self._nav_btns:
            self._nav_btns[name].set_active(True)
        self._active_nav = name
        # Keep only the visible frame under geometry management; the other eight
        # (each with scrollable content) stay built but unmanaged, so a resize
        # or maximize repaints one frame instead of all nine — kills the lag.
        for fname, fr in self._frames.items():
            if fname == name:
                fr.grid()
            elif fr.winfo_manager():
                fr.grid_remove()
        self._frames[name].tkraise()
        if name == "Calendario":
            self._refresh_calendar_view()
        # Nota: NO recargar listas acá. Cada panel (Cuentas, VerifyLegacy,
        # Tandas) reconstruye todas sus filas (CTkOptionMenu/CTkEntry por
        # cuenta) destruyendo y recreando widgets — hacerlo en cada cambio de
        # pestaña, aunque nada haya cambiado, es lo que colgaba la UI al
        # navegar. Cada panel ya tiene su propio botón "Actualizar"/"Recargar
        # lista" y se refresca solo tras acciones que sí modifican datos.

    # ── Reloj ─────────────────────────────────────────────────────────────
    def _build_updates_frame(self):
        """Configuracion local del canal de actualizaciones privadas."""
        f = self._frames["Actualizaciones"]
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(f, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        PageHeader(
            scroll, "APP", "Actualizaciones", "Mantén la app al día."
        ).grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))

        try:
            config = load_config(UPDATE_APP_DIR)
        except Exception:
            config = {}

        try:
            version = read_local_version(UPDATE_APP_DIR)
        except Exception:
            version = "desconocida"

        status_card = Card(scroll, title="Estado")
        status_card.grid(row=1, column=0, sticky="ew", padx=24, pady=(16, 10))
        KeyValueRow(status_card.body, "Versión actual", version).grid(row=0, column=0, sticky="ew")
        KeyValueRow(status_card.body, "Canal", config.get("channel", "Privado")).grid(row=1, column=0, sticky="ew")
        self.update_last_check_row = KeyValueRow(
            status_card.body, "Última comprobación", "Aún no comprobada", divider=False
        )
        self.update_last_check_row.grid(row=2, column=0, sticky="ew")

        card = Card(scroll, title="Acceso privado")
        card.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 24))
        card = card.body
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card, text="Manifiesto remoto:", text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11)
        ).grid(row=0, column=0, padx=(0, 10), pady=(0, 8), sticky="e")
        self.e_update_manifest = ctk.CTkEntry(
            card, fg_color=BG_INPUT, border_color=BORDER,
            placeholder_text="https://raw.githubusercontent.com/.../release-manifest.json"
        )
        self.e_update_manifest.grid(row=0, column=1, columnspan=2, pady=(0, 8), sticky="ew")
        if config.get("manifest_url"):
            self.e_update_manifest.insert(0, str(config["manifest_url"]))

        ctk.CTkLabel(
            card, text="Token GitHub:", text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11)
        ).grid(row=1, column=0, padx=(0, 10), pady=8, sticky="e")
        self.e_update_token = ctk.CTkEntry(
            card, fg_color=BG_INPUT, border_color=BORDER, show="*",
            placeholder_text="github_pat_... (Contents: Read-only)"
        )
        self.e_update_token.grid(row=1, column=1, columnspan=2, pady=8, sticky="ew")
        if config.get("access_token"):
            self.e_update_token.insert(0, str(config["access_token"]))

        self.lbl_update_state = ctk.CTkLabel(
            card, text="", text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11), anchor="w"
        )
        self.lbl_update_state.grid(row=2, column=0, columnspan=3, pady=(8, 12), sticky="ew")

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=3, column=0, columnspan=3, pady=(0, 0), sticky="ew")
        buttons.grid_columnconfigure(3, weight=1)
        GhostButton(
            buttons, text="Guardar configuración", command=self._save_update_config
        ).grid(row=0, column=0, padx=(0, 8))
        DangerButton(
            buttons, text="Borrar token", command=self._clear_update_token
        ).grid(row=0, column=1, padx=(0, 8))
        self.btn_check_update = PrimaryButton(
            buttons, text="Buscar actualizaciones", command=self._check_updates_from_gui
        )
        self.btn_check_update.grid(row=0, column=2, padx=(0, 8))

        self._refresh_update_state()

    def _refresh_update_state(self, message=None, color=TEXT_MUTED):
        try:
            version = read_local_version(UPDATE_APP_DIR)
        except Exception:
            version = "desconocida"
        token_set = bool(self.e_update_token.get().strip())
        state = f"Version instalada: {version}  |  Token: {'configurado' if token_set else 'no configurado'}"
        if message:
            state += f"  |  {message}"
        self.lbl_update_state.configure(text=state, text_color=color)
        if hasattr(self, "update_last_check_row"):
            self.update_last_check_row.value_lbl.configure(
                text=message or "Comprobación pendiente"
            )

    def _write_update_config(self):
        config_path = os.path.join(UPDATE_APP_DIR, "update_config.json")
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    config = loaded
            except (OSError, json.JSONDecodeError):
                config = {}
        config["manifest_url"] = self.e_update_manifest.get().strip()
        config["timeout_seconds"] = int(config.get("timeout_seconds", 15))
        config["check_on_start"] = True
        config["access_token"] = self.e_update_token.get().strip()
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2, ensure_ascii=True)

    def _save_update_config(self):
        try:
            if not self.e_update_manifest.get().strip():
                return messagebox.showwarning("Configuracion incompleta", "Indica la URL del manifiesto.", parent=self)
            self._write_update_config()
            self._refresh_update_state("configuracion guardada", SUCCESS)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Error", f"No se pudo guardar la configuracion: {exc}", parent=self)

    def _clear_update_token(self):
        if not messagebox.askyesno("Borrar token", "Eliminar el token local de GitHub?", parent=self):
            return
        self.e_update_token.delete(0, "end")
        try:
            self._write_update_config()
            self._refresh_update_state("token eliminado", WARNING)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Error", f"No se pudo guardar la configuracion: {exc}", parent=self)

    def _check_updates_from_gui(self):
        try:
            self._write_update_config()
            before = read_local_version(UPDATE_APP_DIR)
        except (OSError, ValueError) as exc:
            return messagebox.showerror("Error", f"No se pudo preparar la actualizacion: {exc}", parent=self)

        self.btn_check_update.configure(state="disabled", text="Comprobando...")
        self._refresh_update_state("consultando GitHub", WARNING)

        def worker():
            messages = []
            updated = check_and_apply(UPDATE_APP_DIR, status_callback=messages.append)
            try:
                after = read_local_version(UPDATE_APP_DIR)
            except Exception:
                after = before
            detail = messages[-1] if messages else "No se recibio respuesta del actualizador."
            self.after(0, lambda: self._finish_gui_update(before, after, updated, detail))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_gui_update(self, before, after, updated, detail):
        self.btn_check_update.configure(state="normal", text="Buscar actualizaciones")
        if updated and after != before:
            self._refresh_update_state(f"actualizada de {before} a {after}; reinicia la GUI", SUCCESS)
            messagebox.showinfo(
                "Actualizacion aplicada",
                f"La version {after} ya esta instalada. Cierra y vuelve a abrir la GUI para usarla.",
                parent=self,
            )
        else:
            color = WARNING if "ya esta instalada" in detail else DANGER
            self._refresh_update_state(detail, color)
            if color == DANGER:
                messagebox.showerror("No se pudo actualizar", detail, parent=self)

    def _update_clock(self):
        self.lbl_clock.configure(
            text=datetime.now().strftime("🕐  %Y-%m-%d   %H:%M:%S"))
        self.after(1000, self._update_clock)

    # ══════════════════════════════════════════════════════════════════════
    # STUBS — se reemplazan en TAREAS 2-6
    # ══════════════════════════════════════════════════════════════════════
    def _build_dashboard_frame(self):
        """TAREA 2 — Dashboard: header, KPI cards, tabla de cuentas, botones."""
        f = self._frames["Dashboard"]
        f.grid_rowconfigure(2, weight=1)
        f.grid_columnconfigure(0, weight=1)

        # ── Header ──────────────────────────────────────────────────────
        PageHeader(
            f, "CONTROL", "Dashboard",
            "Estado del sistema y actividad reciente."
        ).grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))

        # ── KPI Cards ───────────────────────────────────────────────────
        kpi_row = ctk.CTkFrame(f, fg_color="transparent")
        kpi_row.grid(row=1, column=0, sticky="ew", padx=24, pady=(18, 0))

        self.kpi_cuentas = self._make_kpi_card(kpi_row, "📱", "Cuentas", "0", NEON_CYAN, 0)
        self.kpi_videos  = self._make_kpi_card(kpi_row, "🎬", "Videos Enviados", "0", NEON_PURPLE, 1)
        self.kpi_vas     = self._make_kpi_card(kpi_row, "👥", "VAs Activos", "0", SUCCESS, 2)

        # Orden de columna elegido por el usuario (persistido entre rebuilds)
        self._dash_sort_col = None
        self._dash_sort_reverse = False

        # ── Área Central (Tabla) ─────────────────────────────────────────
        center_row = ctk.CTkFrame(f, fg_color="transparent")
        center_row.grid(row=2, column=0, sticky="nsew", padx=24, pady=(14, 0))
        center_row.grid_rowconfigure(0, weight=1)
        center_row.grid_columnconfigure(0, weight=1)

        # ── Tabla ───────────────────────────────────────────────────────
        table_card = Card(center_row, title="Cuentas registradas")
        table_card.grid(row=0, column=0, sticky="nsew")
        table_frame = table_card.body
        table_frame.grid(row=0, column=0, sticky="nsew")
        table_frame.grid_rowconfigure(1, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Sub-header de tabla con buscador
        th = ctk.CTkFrame(table_frame, fg_color="transparent")
        th.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        th.grid_columnconfigure(1, weight=1)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_tree())
        srch = ctk.CTkEntry(th, textvariable=self.search_var, width=200,
                            placeholder_text="🔍 Buscar cuenta...",
                            fg_color=BG_INPUT, border_color=BORDER)
        srch.grid(row=0, column=2, sticky="e")

        # Treeview
        cols = ("VA", "Telegram ID", "Cuenta IG", "Categoría", "Videos", "Fecha")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                  style="Premium.Treeview", height=16,
                                  selectmode="extended")
        col_widths = {"VA": 120, "Telegram ID": 130, "Cuenta IG": 160,
                      "Categoría": 120, "Videos": 80, "Fecha": 110}
        for c in cols:
            self.tree.heading(c, text=c,
                              command=lambda _c=c: self._sort_tree(self.tree, _c, False))
            self.tree.column(c, width=col_widths.get(c, 120), anchor="center")

        # Scrollbar premium
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        sb.grid(row=1, column=1, sticky="ns", pady=(0, 8), padx=(0, 4))

        # Tags de color alternado
        self.tree.tag_configure("odd",  background=self.themed(BG_CARD2))
        self.tree.tag_configure("even", background=self.themed(BG_CARD))

        # ── Botones de acción ────────────────────────────────────────────
        btn_bar = ctk.CTkFrame(f, fg_color="transparent")
        btn_bar.grid(row=3, column=0, sticky="ew", padx=24, pady=(10, 16))

        GhostButton(btn_bar, text="Editar cuentas seleccionadas",
                    command=self.bulk_edit_accounts).pack(side="left", padx=(0, 8))
        DangerButton(btn_bar, text="Eliminar",
                     command=self.delete_account).pack(side="left", padx=(0, 8))
        PrimaryButton(btn_bar, text="Actualizar",
                      command=self.refresh_dashboard).pack(side="left")

        self.refresh_dashboard()

    # ── KPI Card helper ───────────────────────────────────────────────────────
    def _make_kpi_card(self, parent, icon, label, value, accent, col):
        card = Card(parent)
        card.grid(row=0, column=col, padx=(0, 12), sticky="ew")
        parent.grid_columnconfigure(col, weight=1)

        inner = card.body
        inner.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(inner, text=f"{icon}  {label}",
                     font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(anchor="w")
        lbl_val = ctk.CTkLabel(inner, text=value,
                               font=ctk.CTkFont(size=32, weight="bold"),
                               text_color=accent)
        lbl_val.pack(anchor="w", pady=(4, 0))

        # Barra de acento decorativa
        ctk.CTkFrame(inner, height=3, fg_color=accent,
                     corner_radius=2).pack(fill="x", pady=(8, 0))
        return lbl_val

    def _darken(self, color, factor=0.75):
        """Versión más oscura del color. Acepta hex o tupla (light, dark)."""
        return darken(color, factor)

    # ── Lógica Dashboard ─────────────────────────────────────────────────────
    def refresh_dashboard(self):
        """Recarga la tabla y actualiza KPIs. Solo se llama tras acciones que
        modifican datos (borrar, reasignar, etc.) o al presionar 'Actualizar'
        — no hay temporizador de fondo, así que la selección de filas y el
        orden de columna solo cambian cuando el usuario lo pide."""
        # delete()+insert() reconstruye filas con iids nuevos, perdiendo la
        # selección; la recuperamos por username después de reinsertar.
        selected_usernames = {
            self.tree.item(iid)["values"][2].lstrip("@")
            for iid in self.tree.selection()
        }
        for item in self.tree.get_children():
            self.tree.delete(item)

        accounts = self.db.get_all_accounts()
        vas_data = {va: self.get_va_tg_id(va) for va in self.db.get_vas()}
        total_videos = 0

        for i, acc in enumerate(accounts):
            va    = acc.get("assigned_va", "Sin Asignar")
            tg    = vas_data.get(va, "N/A")
            fecha = (acc.get("created_at") or "N/A")[:10]
            vids  = acc.get("videos_posted", 0)
            total_videos += vids
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end", tags=(tag,),
                             values=(va, tg, f"@{acc['username']}",
                                     acc["account_type"], vids, fecha))

        # Reaplicar el orden de columna elegido por el usuario (si lo hay);
        # de lo contrario cada rebuild vuelve al orden crudo de la DB.
        if self._dash_sort_col:
            self._sort_tree(self.tree, self._dash_sort_col, self._dash_sort_reverse)

        if selected_usernames:
            restored = [iid for iid in self.tree.get_children()
                        if self.tree.item(iid)["values"][2].lstrip("@") in selected_usernames]
            if restored:
                self.tree.selection_set(restored)

        # KPIs
        self.kpi_cuentas.configure(text=str(len(accounts)))
        self.kpi_videos.configure(text=str(total_videos))
        self.kpi_vas.configure(text=str(len(self.db.get_vas())))

        # Sincronizar combos en otras pestañas
        self._admin_refresh()
        if hasattr(self, "c_tandas"):
            self.reload_dist_lists()

    def _filter_tree(self):
        """Filtra filas de la tabla por texto del buscador."""
        query = self.search_var.get().lower()
        for item in self.tree.get_children():
            vals = [str(v).lower() for v in self.tree.item(item)["values"]]
            self.tree.item(item, tags=("hidden",) if query and not any(query in v for v in vals) else ())
        # Re-aplicar stripe tags
        visible = [i for i in self.tree.get_children()
                   if "hidden" not in self.tree.item(i)["tags"]]
        for idx, item in enumerate(visible):
            self.tree.item(item, tags=("even" if idx % 2 == 0 else "odd",))

    def get_va_tg_id(self, va_name: str) -> str:
        cur = self.db.conn.cursor()
        cur.execute("SELECT tg_group_id FROM virtual_assistants WHERE name = ?", (va_name,))
        row = cur.fetchone()
        return row["tg_group_id"] if row and row["tg_group_id"] else "N/A"

    def get_selected_accounts(self) -> list[str]:
        return [self.tree.item(iid)["values"][2].lstrip("@")
                for iid in self.tree.selection()]

    def bulk_edit_accounts(self):
        usernames = self.get_selected_accounts()
        if not usernames:
            messagebox.showwarning("⚠️", "Selecciona al menos una cuenta.")
            return
        dialog = BulkEditAccountsDialog(self, len(usernames),
                                        self.db.get_categories(), self.db.get_vas())
        self.wait_window(dialog)
        if not dialog.result:
            return
        category, assigned_va = dialog.result
        updates = build_bulk_account_updates(category, assigned_va)
        if not updates:
            return
        if category != "Sin cambios":
            self.db.add_category(category)
        account_ids = resolve_selected_account_ids(self.db.get_all_accounts(), usernames)
        try:
            self.db.bulk_update_accounts(account_ids, **updates)
        except Exception as exc:
            messagebox.showerror("❌", f"No se pudo actualizar: {exc}")
            return
        self.refresh_dashboard()
        messagebox.showinfo("✅", f"{len(account_ids)} cuenta(s) actualizada(s).")

    def delete_account(self):
        usernames = self.get_selected_accounts()
        if not usernames:
            messagebox.showwarning("⚠️", "Selecciona al menos una cuenta.")
            return
        if len(usernames) == 1:
            msg = f"¿Eliminar la cuenta @{usernames[0]}?"
        else:
            preview = "\n".join(f"  • @{u}" for u in usernames[:10])
            if len(usernames) > 10:
                preview += f"\n  … y {len(usernames) - 10} más"
            msg = f"¿Eliminar {len(usernames)} cuentas?\n\n{preview}"
        if messagebox.askyesno("Confirmar eliminación", msg):
            for u in usernames:
                self.db.delete_account(u)
            self.refresh_dashboard()

    def _sort_tree(self, tv, col, reverse):
        items = [(tv.set(k, col), k) for k in tv.get_children("")]
        items.sort(key=lambda x: (0, float(x[0])) if x[0].isdigit() else (1, x[0].lower()),
                   reverse=reverse)
        for idx, (_, k) in enumerate(items):
            tv.move(k, "", idx)
            tv.item(k, tags=("even" if idx % 2 == 0 else "odd",))
        tv.heading(col, command=lambda: self._sort_tree(tv, col, not reverse))
        if tv is getattr(self, "tree", None):
            self._dash_sort_col = col
            self._dash_sort_reverse = reverse

    def _build_team_frame(self):
        """Panel Admin para VAs y categorías; las tandas se gestionan en su pestaña."""
        f = self._frames["Equipo"]
        f.grid_rowconfigure(1, weight=1)   # fila superior
        f.grid_columnconfigure((0, 1), weight=1)

        # ── Header ──────────────────────────────────────────────────────
        PageHeader(
            f, "SISTEMA", "Admin",
            "Gestión de equipo y configuración."
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 10))

        # ══ FILA SUPERIOR ═══════════════════════════════════════════════

        # ── Columna 0: VAs ───────────────────────────────────────────────
        col0_card = Card(f)
        col0_card.grid(row=1, column=0, sticky="nsew", padx=(24, 8), pady=(0, 8))
        col0 = col0_card.body
        col0.grid_rowconfigure(1, weight=1)
        col0.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(col0, text="👥  VAs",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=NEON_CYAN).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        self._va_scroll = ctk.CTkScrollableFrame(col0, fg_color="transparent")
        self._va_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self._va_scroll.grid_columnconfigure(0, weight=1)

        va_form = ctk.CTkFrame(col0, fg_color="transparent")
        va_form.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 16))
        va_form.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(va_form, text="Nombre:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        self.e_va_name = ctk.CTkEntry(va_form, fg_color=BG_INPUT, border_color=BORDER)
        self.e_va_name.grid(row=1, column=0, sticky="ew", pady=(2, 4))
        ctk.CTkLabel(va_form, text="Telegram ID:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=2, column=0, sticky="w")
        self.e_va_tg = ctk.CTkEntry(va_form, fg_color=BG_INPUT, border_color=BORDER)
        self.e_va_tg.grid(row=3, column=0, sticky="ew", pady=(2, 8))
        PrimaryButton(va_form, text="Guardar VA",
                      command=self.add_va_ui).grid(row=4, column=0, sticky="ew")

        # ── Columna 1: Categorías ────────────────────────────────────────
        col1_card = Card(f)
        col1_card.grid(row=1, column=1, sticky="nsew", padx=(8, 24), pady=(0, 8))
        col1 = col1_card.body
        col1.grid_rowconfigure(1, weight=1)
        col1.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(col1, text="🏷️  Categorías",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=WARNING).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        self._cat_scroll = ctk.CTkScrollableFrame(col1, fg_color="transparent")
        self._cat_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self._cat_scroll.grid_columnconfigure(0, weight=1)

        cat_form = ctk.CTkFrame(col1, fg_color="transparent")
        cat_form.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 16))
        cat_form.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cat_form, text="Nombre:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        self.e_cat_new = ctk.CTkEntry(cat_form, fg_color=BG_INPUT, border_color=BORDER)
        self.e_cat_new.grid(row=1, column=0, sticky="ew", pady=(2, 8))
        PrimaryButton(cat_form, text="Agregar",
                      command=self.add_category_ui).grid(row=2, column=0, sticky="ew")

        self._admin_refresh()

    # ── Lógica Equipo ────────────────────────────────────────────────────────
    def refresh_team_ui(self):
        self._admin_refresh()

    def refresh_team_ui_combo(self):
        self._admin_refresh()

    def add_category_ui(self):
        raw = self.e_cat_new.get().strip() if hasattr(self, "e_cat_new") else ""
        if not raw:
            return messagebox.showwarning("⚠️", "Ingresa un nombre de categoría.")
        cat = raw.upper()
        self.db.add_category(cat)
        self.e_cat_new.delete(0, "end")
        self.refresh_dashboard()
        self._admin_refresh()
        messagebox.showinfo("Éxito", f"Categoría '{cat}' creada.")

    def add_va_ui(self):
        name = self.e_va_name.get().strip()
        tg_id = self.e_va_tg.get().strip()
        if name:
            self.db.add_va(name)
            if tg_id:
                self.db.update_va_telegram_group(name, tg_id)
            self.e_va_name.delete(0, "end")
            self.e_va_tg.delete(0, "end")
            self.refresh_dashboard()
            self._admin_refresh()
            messagebox.showinfo("✅", f"VA '{name}' guardado correctamente.")

    def add_bulk_accounts(self):
        txt = self.txt_accounts.get("1.0", "end").strip()
        if not txt or txt == "usuario1\nusuario2":
            return messagebox.showwarning("⚠️", "No has escrito cuentas válidas.")
            
        users = txt.split("\n")
        ctype = self.c_bulk_cat.get() or "GENERAL"
        vname = self.c_bulk_va.get()
        
        added = 0
        for u in users:
            clean = u.strip().replace("@", "")
            if clean:
                try:
                    self.db.add_virtual_account(clean, ctype)
                    if vname and vname != "Sin Asignar":
                        self.db.update_account(clean, assigned_va=vname)
                    added += 1
                except Exception:
                    pass
                    
        self.txt_accounts.delete("1.0", "end")
        self.refresh_dashboard()
        messagebox.showinfo("✅", f"Proceso terminado. {added} cuentas vinculadas exitosamente.")

    def apply_bulk_category(self):
        new_cat = self.c_bulk_cat_all.get()
        if not new_cat:
            return messagebox.showwarning("⚠️", "Selecciona una categoría.")
            
        if messagebox.askyesno("Confirmación Masiva", 
                               f"¿Mover TODAS las cuentas a '{new_cat}'?"):
            self.db.bulk_update_accounts([acc['id'] for acc in self.db.get_all_accounts()], account_type=new_cat)
            messagebox.showinfo("Éxito", f"Todas las cuentas movidas a {new_cat}")
            self._admin_refresh()
            self.refresh_dashboard()
            if hasattr(self, 'reload_dist_lists'):
                self.refresh_transform_log_table()
                self.reload_dist_lists()

    # ── Admin helpers ────────────────────────────────────────────────────────

    def _admin_load_vas(self):
        for w in self._va_scroll.winfo_children():
            w.destroy()
        cur = self.db.conn.cursor()
        cur.execute("SELECT name, tg_group_id, timezone FROM virtual_assistants ORDER BY name")
        for row in cur.fetchall():
            name = row["name"]
            tg   = row["tg_group_id"] or ""
            tz   = row["timezone"] or "America/Argentina/Buenos_Aires"
            r = ctk.CTkFrame(self._va_scroll, fg_color="transparent")
            r.pack(fill="x", pady=2, padx=4)
            r.grid_columnconfigure(0, weight=1)
            dot_color = NEON_CYAN if tg else TEXT_MUTED
            ctk.CTkLabel(r, text=name, text_color=TEXT_BODY,
                         font=ctk.CTkFont(size=12), anchor="w").grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(r, text="⬤", text_color=dot_color,
                         font=ctk.CTkFont(size=10)).grid(row=0, column=1, padx=(4, 2))

            # Dropdown de timezone (etiqueta corta para no aplastar el nombre del VA)
            tz_label = TZ_TO_LABEL.get(tz, tz)
            tz_var = tk.StringVar(value=tz_label)
            tz_menu = ctk.CTkOptionMenu(
                r, values=list(TIMEZONE_MAP.keys()), variable=tz_var, width=110,
                fg_color=BG_CARD2, button_color=BG_CARD2, text_color=TEXT_BODY,
                font=ctk.CTkFont(size=11),
                command=lambda label, n=name: self._admin_save_va_tz(n, label),
            )
            tz_menu.grid(row=0, column=2, padx=(4, 4))

            GhostButton(r, text="TG", width=36, height=26,
                          command=lambda n=name, t=tg: self._admin_edit_va_tg(n, t)
                          ).grid(row=0, column=3, padx=(2, 2))
            DangerButton(r, text="×", width=28, height=26,
                          command=lambda n=name: self._admin_delete_va(n)
                          ).grid(row=0, column=4, padx=(2, 0))

    def _admin_load_accounts(self):
        for w in self._acc_scroll.winfo_children():
            w.destroy()
        accounts  = self.db.get_all_accounts()
        vas_list  = ["Sin Asignar"] + self.db.get_vas()
        cats_list = self.db.get_categories() or ["GENERAL"]
        self._acc_header_lbl.configure(text=f"{len(accounts)} cuenta(s) destino")
        for acc in accounts:
            username = acc["username"]
            acc_type = acc.get("account_type", "GENERAL")
            assigned = acc.get("assigned_va") or "Sin Asignar"
            label = acc.get("ig_label", "nuevo")
            if label not in LABEL_OPTIONS:
                label = "nuevo"
            r = ctk.CTkFrame(self._acc_scroll, fg_color=BG_CARD2, corner_radius=BTN_RADIUS)
            r.pack(fill="x", pady=3, padx=2)
            r.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(r, text=f"@{username}", text_color=TEXT_BODY,
                         font=ctk.CTkFont(size=12), anchor="w").grid(
                             row=0, column=0, sticky="w", padx=(12, 8), pady=8)
            c_label = ctk.CTkOptionMenu(
                r, values=LABEL_OPTIONS, width=105, height=30,
                fg_color=LABEL_COLORS.get(label, TEXT_MUTED), button_color=LABEL_COLORS.get(label, TEXT_MUTED),
                text_color=TEXT_ON_DANGER, font=ctk.CTkFont(size=11),
                command=lambda v, u=username: self._set_account_label(u, v),
            )
            c_label.set(label)
            c_label.grid(row=0, column=1, padx=(4, 2), pady=6)
            followers_var = tk.StringVar(value=str(acc.get("followers") or 0))
            followers = ctk.CTkEntry(
                r, textvariable=followers_var, width=78, height=30, justify="center",
                fg_color=BG_INPUT, border_color=BORDER,
            )
            followers.bind("<FocusOut>", lambda _e, u=username, v=followers_var: self._set_account_followers(u, v.get()))
            followers.bind("<Return>", lambda _e, u=username, v=followers_var: self._set_account_followers(u, v.get()))
            followers.grid(row=0, column=2, padx=(2, 2), pady=6)
            status = acc.get("ig_status", "unknown")
            if status not in ACCOUNT_STATUS_OPTIONS:
                status = "unknown"
            c_status = ctk.CTkOptionMenu(
                r, values=ACCOUNT_STATUS_OPTIONS, width=98, height=30,
                fg_color=BG_INPUT, button_color=BG_CARD2, button_hover_color=BORDER,
                text_color=TEXT_BODY, font=ctk.CTkFont(size=11),
                command=lambda v, u=username: self._set_account_status(u, v),
            )
            c_status.set(status)
            c_status.grid(row=0, column=3, padx=(2, 2), pady=6)
            c_type = ctk.CTkOptionMenu(
                r, values=cats_list, width=120, height=30,
                fg_color=BG_INPUT, button_color=BG_CARD2, button_hover_color=BORDER,
                text_color=TEXT_BODY, font=ctk.CTkFont(size=11),
                command=lambda v, u=username: self._set_account_category(u, v)
            )
            c_type.set(acc_type if acc_type in cats_list else cats_list[0])
            c_type.grid(row=0, column=4, padx=(2, 2), pady=6)
            c_va = ctk.CTkOptionMenu(
                r, values=vas_list, width=150, height=30,
                fg_color=BG_INPUT, button_color=BG_CARD2, button_hover_color=BORDER,
                text_color=TEXT_BODY, font=ctk.CTkFont(size=11),
                command=lambda v, u=username: self._set_account_va(u, v)
            )
            c_va.set(assigned if assigned in vas_list else vas_list[0])
            c_va.grid(row=0, column=5, padx=(2, 4), pady=6)
            trials_var = tk.BooleanVar(value=bool(acc.get("trials_active")))
            ctk.CTkSwitch(
                r, text="TRIALS ACTIVOS", variable=trials_var, width=118,
                command=lambda u=username, v=trials_var: self._set_account_trials_active(u, v.get()),
            ).grid(row=0, column=6, padx=(2, 4), pady=6)
            notes_var = tk.StringVar(value=acc.get("notes") or "")
            notes = ctk.CTkEntry(
                r, textvariable=notes_var, width=150, height=30,
                fg_color=BG_INPUT, border_color=BORDER, placeholder_text="Notas",
            )
            notes.bind("<FocusOut>", lambda _e, u=username, v=notes_var: self._set_account_notes(u, v.get()))
            notes.bind("<Return>", lambda _e, u=username, v=notes_var: self._set_account_notes(u, v.get()))
            notes.grid(row=0, column=7, padx=(2, 4), pady=6)
            limitations = self._parse_account_limitations(acc.get("limitations"))
            GhostButton(
                r, text=f"Checks ({len(limitations)})", width=108, height=30,
                command=lambda u=username, values=limitations: self._edit_account_limitations(u, values),
            ).grid(row=0, column=8, padx=(2, 4), pady=6)
            DangerButton(r, text="×", width=28, height=30,
                          command=lambda u=username: self._admin_delete_account(u)
                          ).grid(row=0, column=9, padx=(2, 8), pady=6)

    def _set_account_label(self, username: str, value: str):
        self.db.update_account(username, ig_label=value)
        self._admin_load_accounts()

    def _set_account_category(self, username: str, value: str):
        self.db.update_account(username, account_type=value)
        self.refresh_dashboard()

    def _set_account_trials_active(self, username: str, active: bool):
        self.db.set_account_trials_active(username, active)
        if hasattr(self, "reload_dist_lists"):
            self.reload_dist_lists()

    def _set_account_va(self, username: str, value: str):
        self.db.update_account(username, assigned_va=value)
        self.refresh_dashboard()

    def _set_account_followers(self, username: str, value: str):
        try:
            followers = max(0, int(value.strip() or 0))
        except ValueError:
            return
        self.db.update_account(username, followers=followers)

    def _set_account_status(self, username: str, value: str):
        self.db.update_account(username, ig_status=value)

    def _set_account_notes(self, username: str, value: str):
        self.db.update_account(username, notes=value.strip())

    @staticmethod
    def _parse_account_limitations(raw) -> list[str]:
        if not raw:
            return []
        try:
            values = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return []
        return [value for value in values if value in LIMITATION_OPTIONS]

    def _edit_account_limitations(self, username: str, selected: list[str]):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Limitaciones — @{username}")
        dialog.geometry("380x330")
        dialog.configure(fg_color=BG_CARD)
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=f"Limitaciones de @{username}", text_color=TEXT_H1,
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=20, pady=(20, 8))
        ctk.CTkLabel(dialog, text="Marca todas las que correspondan.", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=20, pady=(0, 8))
        vars_by_option = {}
        for option in LIMITATION_OPTIONS:
            var = tk.BooleanVar(value=option in selected)
            vars_by_option[option] = var
            ctk.CTkCheckBox(dialog, text=option, variable=var, text_color=TEXT_BODY,
                             fg_color=ACCENT, hover_color=ACCENT_HOVER).pack(anchor="w", padx=20, pady=4)

        def save():
            values = [option for option, var in vars_by_option.items() if var.get()]
            self.db.update_account(username, limitations=json.dumps(values, ensure_ascii=False))
            dialog.destroy()
            self._admin_load_accounts()

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=(14, 20))
        GhostButton(buttons, text="Cancelar", command=dialog.destroy).pack(side="right")
        PrimaryButton(buttons, text="Guardar", command=save).pack(side="right", padx=(0, 8))

    def _admin_load_cats(self):
        for w in self._cat_scroll.winfo_children():
            w.destroy()
        for cat in self.db.get_categories():
            r = ctk.CTkFrame(self._cat_scroll, fg_color="transparent")
            r.pack(fill="x", pady=2, padx=4)
            r.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(r, text=cat, text_color=TEXT_BODY,
                         font=ctk.CTkFont(size=12), anchor="w").grid(row=0, column=0, sticky="w")
            DangerButton(r, text="×", width=28, height=26,
                          command=lambda c=cat: self._admin_delete_cat(c)
                          ).grid(row=0, column=1, padx=(4, 0))

    def _admin_refresh(self):
        if hasattr(self, "_va_scroll"):
            self._admin_load_vas()
        if hasattr(self, "_acc_scroll"):
            self._admin_load_accounts()
        if hasattr(self, "_cat_scroll"):
            self._admin_load_cats()
        if hasattr(self, "_tanda_scroll"):
            self._admin_load_tandas()
        cats = self.db.get_categories()
        vas  = ["Sin Asignar"] + self.db.get_vas()
        if hasattr(self, "c_bulk_cat"):
            self.c_bulk_cat.configure(values=cats)
            if cats and not self.c_bulk_cat.get():
                self.c_bulk_cat.set(cats[0])
        if hasattr(self, "c_bulk_va"):
            self.c_bulk_va.configure(values=vas)
            if not self.c_bulk_va.get():
                self.c_bulk_va.set(vas[0])
        if hasattr(self, "c_dest"):
            self.c_dest.configure(values=cats)
            if cats and not self.c_dest.get():
                self.c_dest.set(cats[0])

    def _admin_edit_va_tg(self, va_name: str, current_tg: str):
        new_tg = simpledialog.askstring("Telegram ID", f"TG ID para {va_name}:",
                                        initialvalue=current_tg, parent=self)
        if new_tg is not None:
            self.db.update_va_telegram_group(va_name, new_tg.strip())
            self._admin_load_vas()

    def _admin_save_va_tz(self, va_name: str, label: str):
        """Guarda el timezone seleccionado en el dropdown de una VA."""
        tz_id = TIMEZONE_MAP.get(label, label)
        self.db.set_va_timezone(va_name, tz_id)

    def _admin_delete_va(self, va_name: str):
        if messagebox.askyesno("Eliminar VA", f"¿Eliminar '{va_name}'?", parent=self):
            self.db.delete_va(va_name)
            self._admin_refresh()

    def _admin_delete_account(self, username: str):
        if messagebox.askyesno("Eliminar cuenta", f"¿Eliminar @{username}?", parent=self):
            self.db.delete_account(username)
            self._admin_load_accounts()
            self.refresh_dashboard()

    def _admin_delete_cat(self, cat_name: str):
        if messagebox.askyesno("Eliminar categoría", f"¿Eliminar '{cat_name}'?", parent=self):
            self.db.delete_category(cat_name)
            self._admin_refresh()

    # ── Admin Tandas ─────────────────────────────────────────────────────────

    def _admin_load_tandas(self):
        if not hasattr(self, "_tanda_scroll"):
            return
        for w in self._tanda_scroll.winfo_children():
            w.destroy()
        tandas = self.db.get_all_tandas()
        self._tanda_admin_header.configure(text=f"🎬  Tandas ({len(tandas)})")
        for tanda in tandas:
            name = tanda.get("tanda_name", "")
            p1   = os.path.basename(tanda.get("p1_folder", "")) or "—"
            p2   = os.path.basename(tanda.get("p2_folder", "")) or "—"
            cap  = os.path.basename(tanda.get("captions_file_path", "") or "") or "—"

            r = ctk.CTkFrame(self._tanda_scroll, fg_color=BG_CARD2, corner_radius=4)
            r.pack(fill="x", pady=3, padx=4)
            r.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(r, text=name, text_color=IG_PINK,
                         font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
                         ).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(6, 0))
            ctk.CTkLabel(r, text=f"P1: {p1[:20]}", text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=10), anchor="w"
                         ).grid(row=1, column=0, sticky="w", padx=8, pady=0)
            ctk.CTkLabel(r, text=f"P2: {p2[:20]}", text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=10), anchor="w"
                         ).grid(row=2, column=0, sticky="w", padx=8, pady=0)
            ctk.CTkLabel(r, text=f"Cap: {cap[:20]}", text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=10), anchor="w"
                         ).grid(row=3, column=0, sticky="w", padx=8, pady=(0, 4))

            GhostButton(r, text="✏️", width=30, height=26,
                          command=lambda t=tanda: self._admin_edit_tanda(t)
                          ).grid(row=0, column=1, padx=(4, 2), pady=(4, 0), sticky="ne")
            DangerButton(r, text="×", width=28, height=26,
                          command=lambda n=name: self._admin_delete_tanda(n)
                          ).grid(row=0, column=2, padx=(2, 6), pady=(4, 0), sticky="ne")

    def _admin_edit_tanda(self, tanda: dict):
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Editar Tanda — {tanda['tanda_name']}")
        dlg.geometry("440x340")
        dlg.configure(fg_color=BG_CARD)
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        state = {
            "p1": tanda.get("p1_folder", ""),
            "p2": tanda.get("p2_folder", ""),
            "cap": tanda.get("captions_file_path", "") or "",
        }

        ctk.CTkLabel(dlg, text="Nombre:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=20, pady=(20, 2))
        e_name = ctk.CTkEntry(dlg, fg_color=BG_INPUT, border_color=BORDER)
        e_name.insert(0, tanda.get("tanda_name", ""))
        e_name.pack(fill="x", padx=20, pady=(0, 8))

        lbl_p1 = ctk.CTkLabel(dlg, text=f"P1: {os.path.basename(state['p1']) or '—'}",
                               text_color=NEON_PURPLE, font=ctk.CTkFont(size=11), anchor="w")
        lbl_p1.pack(fill="x", padx=20)

        def pick_p1():
            path = filedialog.askdirectory(title="Carpeta P1", parent=dlg)
            if path:
                state["p1"] = path
                lbl_p1.configure(text=f"P1: {os.path.basename(path)}")
        ctk.CTkButton(dlg, text="📂 Cambiar P1", fg_color=NEON_PURPLE,
                      hover_color=self._darken(NEON_PURPLE), text_color=TEXT_H1,
                      corner_radius=BTN_RADIUS, height=BTN_H, command=pick_p1
                      ).pack(fill="x", padx=20, pady=(2, 8))

        lbl_p2 = ctk.CTkLabel(dlg, text=f"P2: {os.path.basename(state['p2']) or '—'}",
                               text_color=NEON_CYAN, font=ctk.CTkFont(size=11), anchor="w")
        lbl_p2.pack(fill="x", padx=20)

        def pick_p2():
            path = filedialog.askdirectory(title="Carpeta P2", parent=dlg)
            if path:
                state["p2"] = path
                lbl_p2.configure(text=f"P2: {os.path.basename(path)}")
        ctk.CTkButton(dlg, text="📂 Cambiar P2", fg_color=NEON_CYAN,
                      hover_color=self._darken(NEON_CYAN), text_color=BG_APP,
                      corner_radius=BTN_RADIUS, height=BTN_H, command=pick_p2
                      ).pack(fill="x", padx=20, pady=(2, 8))

        lbl_cap = ctk.CTkLabel(dlg, text=f"Cap: {os.path.basename(state['cap']) or '—'}",
                               text_color=WARNING, font=ctk.CTkFont(size=11), anchor="w")
        lbl_cap.pack(fill="x", padx=20)
        ctk.CTkLabel(dlg, text="Los captions se cambian solo desde Logística.",
                     text_color=TEXT_MUTED, font=ctk.CTkFont(size=10), anchor="w"
                     ).pack(fill="x", padx=20, pady=(2, 12))

        def save():
            new_name = e_name.get().strip().upper()
            if not new_name or not state["p1"] or not state["p2"]:
                messagebox.showwarning("⚠️", "Nombre, P1 y P2 son obligatorios.", parent=dlg)
                return
            old_name = tanda["tanda_name"]
            cur = self.db.conn.cursor()
            cur.execute(
                "UPDATE batch_tandas SET tanda_name=?, p1_folder=?, p2_folder=?, captions_file_path=? WHERE tanda_name=?",
                (new_name, state["p1"], state["p2"], state["cap"] or None, old_name)
            )
            self.db.conn.commit()
            dlg.destroy()
            self._admin_load_tandas()
            self.reload_dist_lists()
            messagebox.showinfo("✅", f"Tanda '{new_name}' actualizada.")

        ctk.CTkButton(dlg, text="💾 Guardar cambios", fg_color=SUCCESS,
                      hover_color=self._darken(SUCCESS), text_color=BG_APP,
                      corner_radius=BTN_RADIUS, height=BTN_H,
                      font=ctk.CTkFont(weight="bold"), command=save
                      ).pack(fill="x", padx=20, pady=(0, 20))

    def _admin_delete_tanda(self, tanda_name: str):
        if messagebox.askyesno("Eliminar tanda", f"¿Eliminar '{tanda_name}'?", parent=self):
            cur = self.db.conn.cursor()
            cur.execute("DELETE FROM batch_tandas WHERE tanda_name = ?", (tanda_name,))
            self.db.conn.commit()
            self._admin_load_tandas()
            self.reload_dist_lists()

    def _tanda_admin_pick_p1(self):
        path = filedialog.askdirectory(title="Carpeta P1 (Inicio)")
        if path:
            self._tanda_admin_p1 = path
            self.lbl_tanda_p1.configure(
                text=f"P1: {os.path.basename(path)}", text_color=NEON_PURPLE)

    def _tanda_admin_pick_p2(self):
        path = filedialog.askdirectory(title="Carpeta P2 (Cierre)")
        if path:
            self._tanda_admin_p2 = path
            self.lbl_tanda_p2.configure(
                text=f"P2: {os.path.basename(path)}", text_color=NEON_CYAN)

    def _tanda_admin_save(self):
        name = self.e_tanda_admin_name.get().strip().upper()
        if not name:
            return messagebox.showwarning("⚠️", "Ingresa un nombre para la tanda.")
        if not self._tanda_admin_p1 or not self._tanda_admin_p2:
            return messagebox.showwarning("⚠️", "Selecciona las carpetas P1 y P2.")
        existing = self.db.get_tanda_by_name(name) or {}
        self.db.add_tanda(name, self._tanda_admin_p1, self._tanda_admin_p2,
                          existing.get("captions_file_path"))
        self.e_tanda_admin_name.delete(0, "end")
        self._tanda_admin_p1 = ""
        self._tanda_admin_p2 = ""
        self.lbl_tanda_p1.configure(text="P1: —", text_color=TEXT_MUTED)
        self.lbl_tanda_p2.configure(text="P2: —", text_color=TEXT_MUTED)
        self._admin_load_tandas()
        self.reload_dist_lists()
        messagebox.showinfo("✅", f"Tanda '{name}' guardada correctamente.")

    def _build_render_performance_control(self, parent, context):
        """Build one compact view of the globally persisted render worker count."""
        snapshot = render_performance.get_render_performance()
        value_text = self._render_performance_value_text(snapshot)
        slider_max = max(2, snapshot.max_workers)
        slider_state = "disabled" if snapshot.max_workers == 1 else "normal"
        control = ctk.CTkFrame(parent, fg_color=BG_CARD2, corner_radius=8)
        control._render_performance_context = context
        ctk.CTkLabel(
            control, text="Videos en paralelo", text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left", padx=(10, 6), pady=6)
        slider = ctk.CTkSlider(
            control, from_=1, to=slider_max,
            number_of_steps=max(1, slider_max - 1), state=slider_state,
            command=self._on_render_workers_changed,
            fg_color=BG_INPUT, progress_color=ACCENT, button_color=NEON_CYAN,
            width=120,
        )
        slider.pack(side="left", padx=(0, 6), pady=6)
        value_label = ctk.CTkLabel(
            control, text=value_text,
            text_color=TEXT_BODY, font=ctk.CTkFont(size=11), width=142,
        )
        value_label.pack(side="left", padx=(0, 10), pady=6)

        self._render_worker_controls = getattr(self, "_render_worker_controls", [])
        self._render_worker_controls.append((slider, value_label))
        was_syncing = getattr(self, "_render_worker_syncing", False)
        self._render_worker_syncing = True
        try:
            slider.set(snapshot.workers)
        finally:
            self._render_worker_syncing = was_syncing
        return control

    def _render_performance_value_text(self, snapshot):
        value_text = f"{snapshot.workers} de {snapshot.max_workers} equipo"
        available_workers = snapshot.available_workers or snapshot.max_workers
        if available_workers < snapshot.max_workers:
            value_text += f" - RAM actual: {available_workers}"
        if snapshot.workers_were_reclamped:
            value_text += " - ajustado"
        return value_text

    def _on_render_workers_changed(self, value):
        if getattr(self, "_render_worker_syncing", False):
            return
        current = render_performance.get_render_performance()
        workers = max(1, min(round(float(value)), current.max_workers))
        available_workers = current.available_workers or current.max_workers
        if workers > available_workers:
            self._sync_render_worker_controls(current)
            warning_key = (workers, available_workers, current.max_workers)
            if getattr(self, "_render_memory_warning_key", None) != warning_key:
                self._render_memory_warning_key = warning_key
                messagebox.showwarning(
                    "Rendimiento",
                    (
                        f"Ahora hay memoria para {available_workers} videos en paralelo.\n\n"
                        f"Cerra mas programas para poder usar {workers}."
                    ),
                )
            return
        self._render_memory_warning_key = None
        snapshot = render_performance.save_render_workers(workers)
        self._sync_render_worker_controls(snapshot)

    def _sync_render_worker_controls(self, snapshot):
        self._render_worker_syncing = True
        try:
            value_text = self._render_performance_value_text(snapshot)
            for slider, value_label in self._render_worker_controls:
                slider_max = max(2, snapshot.max_workers)
                slider.configure(
                    from_=1,
                    to=slider_max,
                    number_of_steps=max(1, slider_max - 1),
                    state="disabled" if snapshot.max_workers == 1 else "normal",
                )
                slider.set(snapshot.workers)
                value_label.configure(text=value_text)
        finally:
            self._render_worker_syncing = False

    def _build_mix_frame(self):
        """TAREA 4 — Creador de Tandas."""
        f = self._frames["Tandas"]
        f.grid_rowconfigure(2, weight=1)
        f.grid_columnconfigure((0, 1), weight=1)

        # ── Header ──────────────────────────────────────────────────────
        PageHeader(
            f, "CONTENIDO", "Tandas",
            "Lotes de videos forjados listos para distribuir."
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 10))

        # ── Configuración Tanda ─────────────────────────────────────────
        top_card = Card(f, title="Configuración de tanda")
        top_card.grid(row=1, column=0, columnspan=2, sticky="ew", padx=24, pady=10)
        top_body = top_card.body
        
        ctk.CTkLabel(top_body, text="Nombre/ID de la Tanda:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.e_tanda_name = ctk.CTkEntry(top_body, fg_color=BG_INPUT, border_color=BORDER, width=300)
        self.e_tanda_name.pack(side="left", padx=10)

        # ── P1 y P2 (Paneles scrollables) ───────────────────────────────
        p1_card = Card(f, title="P1 · Inicio")
        p1_card.grid(row=2, column=0, sticky="nsew", padx=(24, 12), pady=10)
        self.f_p1 = ctk.CTkScrollableFrame(p1_card.body, fg_color="transparent")
        self.f_p1.grid(row=0, column=0, sticky="nsew")
        p1_card.body.grid_rowconfigure(0, weight=1)
        
        GhostButton(self.f_p1, text="Buscar Carpeta P1 (Inicio)",
                    command=lambda: self.pick_folder(1)).pack(pady=10, padx=10, fill="x")
        self.lbl_p1_count = ctk.CTkLabel(self.f_p1, text="0 videos", text_color=TEXT_MUTED)
        self.lbl_p1_count.pack()
        
        p2_card = Card(f, title="P2 · Cierre")
        p2_card.grid(row=2, column=1, sticky="nsew", padx=(12, 24), pady=10)
        self.f_p2 = ctk.CTkScrollableFrame(p2_card.body, fg_color="transparent")
        self.f_p2.grid(row=0, column=0, sticky="nsew")
        p2_card.body.grid_rowconfigure(0, weight=1)
        
        PrimaryButton(self.f_p2, text="Buscar Carpeta P2 (Cierre)",
                      command=lambda: self.pick_folder(2)).pack(pady=10, padx=10, fill="x")
        self.lbl_p2_count = ctk.CTkLabel(self.f_p2, text="0 videos", text_color=TEXT_MUTED)
        self.lbl_p2_count.pack()

        # ── Controles Inferiores ────────────────────────────────────────
        bot_card = Card(f, title="Renderizado")
        bot_card.grid(row=3, column=0, columnspan=2, sticky="ew", padx=24, pady=(10, 24))
        bot_body = bot_card.body
        
        ctk.CTkLabel(
            bot_body, text="Los captions se asignan por tanda desde Logística.", text_color=TEXT_MUTED
        ).pack(side="left")
        self.btn_render = PrimaryButton(bot_body, text="INICIAR RENDER", height=BTN_H_LG,
                                        command=self.process_tanda)
        self.btn_render.pack(side="right")
        self._build_render_performance_control(bot_body, "Tandas").pack(side="right", padx=(0, 12))

        # ── Lista de Tandas registradas ─────────────────────────────────
        tandas_card = Card(f, title="Tandas registradas")
        tandas_card.grid(row=4, column=0, columnspan=2, sticky="ew", padx=24, pady=(0, 24))
        tandas_body = tandas_card.body
        tandas_body.grid_columnconfigure(0, weight=1)

        self._tandas_list_scroll = ctk.CTkScrollableFrame(
            tandas_body, fg_color="transparent", height=140)
        self._tandas_list_scroll.grid(row=0, column=0, sticky="ew")
        self._tandas_list_scroll.grid_columnconfigure(0, weight=1)

        self._refresh_tandas_list()

    # ── Lógica Tandas ────────────────────────────────────────────────────────
    def pick_folder(self, pane_num):
        path = filedialog.askdirectory(title="Seleccionar carpeta de videos")
        if not path: return
        
        target_frame = self.f_p1 if pane_num == 1 else self.f_p2
        lbl_count = self.lbl_p1_count if pane_num == 1 else self.lbl_p2_count
        
        # Limpiar lista anterior (excepto botón y label)
        for widget in target_frame.winfo_children()[2:]:
            widget.destroy()
            
        if pane_num == 1: self.p1_dir = path
        else: self.p2_dir = path
            
        files = [f for f in os.listdir(path) if f.lower().endswith(('.mp4', '.mov'))]
        lbl_count.configure(text=f"{len(files)} videos cargados")
        
        for f_name in files:
            ctk.CTkLabel(target_frame, text=f"🎥 {f_name}", anchor="w",
                         text_color=TEXT_BODY, font=ctk.CTkFont(size=11)).pack(fill="x", padx=15, pady=2)

    def _refresh_tandas_list(self):
        if not hasattr(self, "_tandas_list_scroll"):
            return
        for w in self._tandas_list_scroll.winfo_children():
            w.destroy()
        for tanda in self.db.get_all_tandas():
            name = tanda.get("tanda_name", "")
            p1   = os.path.basename(tanda.get("p1_folder", ""))[:22]
            p2   = os.path.basename(tanda.get("p2_folder", ""))[:22]
            r = ctk.CTkFrame(self._tandas_list_scroll, fg_color="transparent")
            r.pack(fill="x", pady=2, padx=4)
            r.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                r, text=f"🎬  {name}   ·   {p1} → {p2}",
                anchor="w", text_color=TEXT_BODY, font=ctk.CTkFont(size=11)
            ).grid(row=0, column=0, sticky="w")
            DangerButton(
                r, text="×", width=28, height=26,
                command=lambda n=name: self._delete_tanda_ui(n)
            ).grid(row=0, column=1, padx=(8, 0))

    def _delete_tanda_ui(self, tanda_name: str):
        if messagebox.askyesno("Eliminar tanda", f"¿Eliminar '{tanda_name}'?", parent=self):
            cur = self.db.conn.cursor()
            cur.execute("DELETE FROM batch_tandas WHERE tanda_name = ?", (tanda_name,))
            self.db.conn.commit()
            self._refresh_tandas_list()
            self.reload_dist_lists()

    def process_tanda(self):
        name = self.e_tanda_name.get().strip().upper()
        if not name or not self.p1_dir or not self.p2_dir:
            return messagebox.showwarning("⚠️", "Asegúrate de llenar el nombre y seleccionar P1 y P2.")

        existing = self.db.get_tanda_by_name(name) or {}
        self.db.add_tanda(name, self.p1_dir, self.p2_dir, existing.get("captions_file_path"))
        self._refresh_tandas_list()
        self.reload_dist_lists()
        performance = render_performance.get_render_performance()

        def task():
            import videos
            return videos.render_tanda(name, performance)
            
        def done(success, result):
            self.btn_render.configure(text="⚙️ INICIAR RENDER", state="normal")
            if success: messagebox.showinfo("Éxito", result)
            else: messagebox.showerror("Error", result)
            
        self.btn_render.configure(text="⏳ RENDERIZANDO...", state="disabled")
        WorkerThread(self, done, task).start()

    def _build_dist_frame(self):
        """TAREA 5 — Logística y distribución."""
        f = self._frames["Logistica"]
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure(0, weight=1)

        # ── Header ──────────────────────────────────────────────────────
        PageHeader(
            f, "DISTRIBUCIÓN", "Logística",
            "Reparto anti-colisión de tandas entre cuentas y días."
        ).grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))

        # ── TabView: Por Tandas / Por Cuentas ───────────────────────────
        tabs = ctk.CTkTabview(
            f, fg_color=BG_CARD, corner_radius=CARD_RADIUS,
            segmented_button_fg_color=BG_CARD2,
            segmented_button_selected_color=NEON_CYAN,
            segmented_button_selected_hover_color=self._darken(NEON_CYAN),
            segmented_button_unselected_color=BG_CARD2,
            text_color=TEXT_BODY,
        )
        tabs.grid(row=1, column=0, sticky="nsew", padx=24, pady=10)

        t1 = tabs.add("🚀  Por Tandas")
        t2 = tabs.add("📤  Por Cuentas")
        t3 = tabs.add("TRIALS")

        self._build_dist_tandas_tab(t1)
        self._build_dist_cuentas_tab(t2)
        self._build_dist_trials_tab(t3)

        # Cargar datos iniciales
        self.reload_dist_lists()

    def _build_dist_tandas_tab(self, parent):
        """Contenido del tab Por Tandas (lógica original)."""
        parent.grid_columnconfigure((1, 3), weight=1)

        # Fila 0: Tandas y Categorías
        ctk.CTkLabel(parent, text="Tanda principal:", text_color=TEXT_MUTED).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="e")
        self.c_tandas = ctk.CTkComboBox(
            parent, values=[], fg_color=BG_INPUT, border_color=BORDER,
            command=self._refresh_tanda_caption_label,
        )
        self.c_tandas.grid(row=0, column=1, padx=10, pady=(20, 10), sticky="ew")

        ctk.CTkLabel(parent, text="2da tanda (opcional):", text_color=TEXT_MUTED).grid(row=0, column=2, padx=20, pady=(20, 10), sticky="e")
        self.c_tandas_2 = ctk.CTkComboBox(parent, values=[""], fg_color=BG_INPUT, border_color=BORDER)
        self.c_tandas_2.grid(row=0, column=3, padx=10, pady=(20, 10), sticky="ew")

        ctk.CTkLabel(parent, text="Categoría Destino:", text_color=TEXT_MUTED).grid(row=1, column=0, padx=20, pady=10, sticky="e")
        self.c_dest = ctk.CTkComboBox(parent, values=[], fg_color=BG_INPUT, border_color=BORDER)
        self.c_dest.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # Fila 2: Cuota y Días
        ctk.CTkLabel(parent, text="Videos/día por cuenta:", text_color=TEXT_MUTED).grid(row=2, column=0, padx=20, pady=10, sticky="e")
        self.e_quota = Stepper(parent, value=4, min=1, max=50)
        self.e_quota.grid(row=2, column=1, padx=10, pady=10, sticky="w")

        ctk.CTkLabel(parent, text="Días (o 'MAX'):", text_color=TEXT_MUTED).grid(row=2, column=2, padx=20, pady=10, sticky="e")
        self.e_days = ctk.CTkEntry(parent, fg_color=BG_INPUT, border_color=BORDER, width=80)
        self.e_days.insert(0, "MAX")
        self.e_days.grid(row=2, column=3, padx=10, pady=10, sticky="w")

        # Fila 3: Fill-up
        self.fillup_var = tk.BooleanVar(value=False)
        ToggleRow(parent, "Habilitar 'Fill-up' (Rellenar con historial si faltan)",
                  variable=self.fillup_var).grid(row=3, column=0, columnspan=4,
                                                  padx=20, pady=(10, 10), sticky="ew")

        # Fila 4: captions persistidos por tanda (solo Logística)
        self._build_logistica_caption_controls(
            parent, row=4, columnspan=4,
            selector_attr="c_tandas", label_attr="tandas_lbl_cap",
            padx=20, pady=(0, 10),
        )

        # Botonera
        btn_box = ctk.CTkFrame(parent, fg_color="transparent")
        btn_box.grid(row=5, column=0, columnspan=4, pady=20)

        GhostButton(btn_box, text="Resetear todo", height=BTN_H_LG,
                    command=self._tandas_dist_reset).pack(side="left", padx=(0, 20))
        GhostButton(btn_box, text="VISTA PREVIA", height=BTN_H_LG,
                    command=self.preview_distribution).pack(side="left", padx=10)
        PrimaryButton(btn_box, text="DISTRIBUIR REAL AHORA", height=BTN_H_LG,
                      command=self.start_distribution).pack(side="left", padx=10)

    PERIOD_DAYS = {
        "1 semana": 7,
        "2 semanas": 14,
        "3 semanas": 21,
        "1 mes": 30,
        "MAX": None,
    }

    def _build_logistica_caption_controls(
        self,
        parent,
        *,
        row,
        columnspan,
        selector_attr="c_tandas",
        label_attr="tandas_lbl_cap",
        padx=20,
        pady=(0, 10),
    ):
        cap_row = ctk.CTkFrame(parent, fg_color=BG_CARD2, corner_radius=CARD_RADIUS)
        cap_row.grid(row=row, column=0, columnspan=columnspan, sticky="ew", padx=padx, pady=pady)
        GhostButton(
            cap_row,
            text="Asignar captions a tanda",
            command=lambda attr=selector_attr: self.assign_captions_to_selected_tanda(attr),
        ).pack(side="left", padx=16, pady=12)
        DangerButton(
            cap_row,
            text="Quitar captions",
            command=lambda attr=selector_attr: self.clear_captions_from_selected_tanda(attr),
        ).pack(side="left", padx=8, pady=12)
        label = ctk.CTkLabel(cap_row, text="Sin captions asignados", text_color=TEXT_MUTED)
        label.pack(side="left", padx=10)
        setattr(self, label_attr, label)
        self._refresh_logistica_caption_label(selector_attr, label_attr)

    def _build_dist_trials_tab(self, parent):
        """Trial distribution keeps captions and calendars separate from normal work."""
        parent.grid_columnconfigure(0, weight=1)

        cfg = ctk.CTkFrame(parent, fg_color="transparent")
        cfg.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        ctk.CTkLabel(cfg, text="Videos/dia por cuenta:", text_color=TEXT_MUTED).pack(side="left")
        self.trial_dist_vpd = Stepper(cfg, value=1, min=1, max=50)
        self.trial_dist_vpd.pack(side="left", padx=(8, 20))
        ctk.CTkLabel(cfg, text="Dias:", text_color=TEXT_MUTED).pack(side="left")
        self.trial_dist_days = ctk.CTkEntry(cfg, width=70, fg_color=BG_INPUT, border_color=BORDER)
        self.trial_dist_days.insert(0, "MAX")
        self.trial_dist_days.pack(side="left", padx=8)
        self.trial_accounts_lbl = ctk.CTkLabel(cfg, text="0 cuentas con TRIALS ACTIVOS", text_color=TEXT_MUTED)
        self.trial_accounts_lbl.pack(side="right")

        self.trial_account_scroll = ctk.CTkScrollableFrame(parent, fg_color=BG_CARD2)
        self.trial_account_scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        parent.grid_rowconfigure(1, weight=1)
        self.trial_account_vars = {}
        self.trial_account_panel_frames = {}
        self.trial_expanded_accounts = set()
        self.trial_caption_editors = {}
        self.trial_thumbnail_images = []

        buttons = ctk.CTkFrame(parent, fg_color="transparent")
        buttons.grid(row=2, column=0, pady=(4, 12))
        GhostButton(buttons, text="Guardar captions Trial", command=self._save_trial_captions).pack(side="left", padx=6)
        GhostButton(buttons, text="VISTA PREVIA", command=lambda: self._trial_dist_run_per_account(True)).pack(side="left", padx=6)
        PrimaryButton(buttons, text="DISTRIBUIR TRIALS", command=lambda: self._trial_dist_run_per_account(False)).pack(side="left", padx=6)
        self.trial_dist_result = ctk.CTkTextbox(parent, height=100, fg_color=BG_INPUT, text_color=NEON_CYAN)
        self.trial_dist_result.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))

    def _trial_tanda_files(self, tanda_name=None):
        if not tanda_name:
            return []
        folder = os.path.join(_BASE_DIR, "videos_finales", tanda_name)
        if not os.path.isdir(folder):
            return []
        return sorted(name for name in os.listdir(folder) if name.lower().endswith((".mp4", ".mov", ".avi")))

    def _trial_refresh_account_rows(self):
        for widget in self.trial_account_scroll.winfo_children():
            widget.destroy()
        tandas = [""] + self.db.get_trial_tandas()
        self.trial_account_vars = {}
        self.trial_account_panel_frames = {}
        self.trial_expanded_accounts = set()
        self.trial_caption_editors = {}
        self.trial_thumbnail_images = []
        for account in self.db.get_trials_active_accounts():
            username = account["username"]
            row = ctk.CTkFrame(self.trial_account_scroll, fg_color=BG_CARD)
            row.pack(fill="x", padx=4, pady=4)
            header = ctk.CTkFrame(row, fg_color="transparent")
            header.pack(fill="x", padx=8, pady=6)
            ctk.CTkLabel(header, text=f"@{username} [{account.get('account_type', '')}]", width=220, anchor="w").pack(side="left", padx=8)
            var = tk.StringVar(value="")
            ctk.CTkComboBox(
                header, values=tandas, variable=var, width=260,
                command=lambda _value, u=username: self._trial_on_account_tanda_changed(u),
            ).pack(side="left", padx=8, pady=5)
            GhostButton(
                header, text="Desplegar panel de trials",
                command=lambda u=username: self._trial_toggle_account_panel(u),
            ).pack(side="left", padx=8, pady=5)
            panel = ctk.CTkFrame(row, fg_color=BG_CARD2)
            self.trial_account_panel_frames[username] = panel
            self.trial_account_vars[username] = var
        self.trial_accounts_lbl.configure(text=f"{len(self.trial_account_vars)} cuentas con TRIALS ACTIVOS")

    def _trial_selected_assignments(self):
        return {u: v.get().strip() for u, v in self.trial_account_vars.items() if v.get().strip()}

    def _trial_load_thumbnail(self, label, video_path):
        def task():
            cache = trial_preview_path(video_path)
            if not cache.exists():
                cache.parent.mkdir(parents=True, exist_ok=True)
                from video_editor import render_preview
                render_preview(str(video_path), [], str(cache), timestamp=0.1)
            return cache
        def done(success, result):
            if success:
                try:
                    from PIL import Image
                    image = Image.open(result).convert("RGB"); image.thumbnail((120, 68), Image.Resampling.LANCZOS)
                    preview = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                    self.trial_thumbnail_images.append(preview); label.configure(image=preview, text="")
                    return
                except Exception:
                    pass
            label.configure(text="Sin preview")
        WorkerThread(self, done, task).start()

    def _trial_on_account_tanda_changed(self, username):
        for key in list(self.trial_caption_editors):
            if len(key) == 3 and key[0] == username:
                self.trial_caption_editors.pop(key, None)
        if username in getattr(self, "trial_expanded_accounts", set()):
            self._trial_render_account_panel(username)

    def _trial_toggle_account_panel(self, username):
        expanded = getattr(self, "trial_expanded_accounts", set())
        panel = self.trial_account_panel_frames.get(username)
        if panel is None:
            return
        if username in expanded:
            expanded.remove(username)
            panel.pack_forget()
            for key in list(self.trial_caption_editors):
                if len(key) == 3 and key[0] == username:
                    self.trial_caption_editors.pop(key, None)
            return
        expanded.add(username)
        panel.pack(fill="x", padx=12, pady=(0, 8))
        self._trial_render_account_panel(username)

    def _trial_render_account_panel(self, username):
        panel = self.trial_account_panel_frames.get(username)
        if panel is None:
            return
        for widget in panel.winfo_children():
            widget.destroy()
        for key in list(self.trial_caption_editors):
            if len(key) == 3 and key[0] == username:
                self.trial_caption_editors.pop(key, None)
        variable = self.trial_account_vars.get(username)
        tanda = variable.get().strip() if variable is not None else ""
        if not tanda:
            ctk.CTkLabel(panel, text="Escoge una tanda para esta cuenta.", text_color=TEXT_MUTED).pack(anchor="w", padx=10, pady=8)
            return
        captions = self.db.get_trial_source_captions(tanda)
        folder = os.path.join(_BASE_DIR, "videos_finales", tanda)
        source_groups = group_trial_sources(self._trial_tanda_files(tanda))
        if not source_groups:
            ctk.CTkLabel(panel, text="Esta tanda no tiene videos Forge.", text_color=TEXT_MUTED).pack(anchor="w", padx=10, pady=8)
            return
        for source_key, copies in source_groups:
            row = ctk.CTkFrame(panel, fg_color=BG_CARD)
            row.pack(fill="x", padx=4, pady=4)
            preview_label = ctk.CTkLabel(row, text="Cargando preview", width=120, height=68)
            preview_label.pack(side="left", padx=8, pady=8)
            body = ctk.CTkFrame(row, fg_color="transparent")
            body.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=6)
            ctk.CTkLabel(body, text=f"{tanda} / {source_key} ({len(copies)} copias)", text_color=TEXT_BODY).pack(anchor="w")
            editor = ctk.CTkTextbox(body, height=72, fg_color=BG_INPUT, border_color=BORDER, border_width=1)
            editor.pack(fill="x", pady=(2, 0))
            editor.insert("1.0", captions.get(source_key, ""))
            self.trial_caption_editors[(username, tanda, source_key)] = editor
            self._trial_load_thumbnail(preview_label, os.path.join(folder, copies[0]))

    def _trial_refresh_sources(self, _value=None):
        for username in list(getattr(self, "trial_expanded_accounts", set())):
            self._trial_render_account_panel(username)

    def _save_trial_captions(self):
        if not self.trial_caption_editors:
            if getattr(self, "_trial_saving_silently", False):
                return
            return messagebox.showwarning("Trials", "Selecciona una tanda para al menos una cuenta.")
        for key, editor in self.trial_caption_editors.items():
            if len(key) == 3:
                _username, tanda, source_key = key
            else:
                tanda, source_key = key
            self.db.set_trial_source_caption(tanda, source_key, editor.get("1.0", "end-1c").strip())
        if not getattr(self, "_trial_saving_silently", False):
            messagebox.showinfo("Trials", "Captions Trial guardados.")

    def _trial_missing_caption_sources(self, tanda_name):
        return missing_trial_caption_sources(
            self._trial_tanda_files(tanda_name),
            self.db.get_trial_source_captions(tanda_name),
        )

    def _trial_calendar_root(self):
        return str(trial_calendar_root(_BASE_DIR))

    def _trial_dist_run_per_account(self, preview_only):
        assignments = self._trial_selected_assignments()
        if not assignments:
            return messagebox.showwarning("Trials", "Selecciona una tanda para al menos una cuenta.")
        self._trial_saving_silently = True
        self._save_trial_captions()
        self._trial_saving_silently = False
        missing = [f"{t}/{s}" for t in set(assignments.values()) for s in self._trial_missing_caption_sources(t)]
        if missing:
            return messagebox.showwarning("Captions Trial faltantes", ", ".join(missing))
        try:
            per_day = int(self.trial_dist_vpd.get())
            files_by_tanda = {t: self._trial_tanda_files(t) for t in set(assignments.values())}
            raw_days = self.trial_dist_days.get().strip().upper()
            days = "MAX" if raw_days == "MAX" else int(raw_days)
            if per_day < 1 or (days != "MAX" and days < 1):
                raise ValueError
        except ValueError:
            return messagebox.showwarning("Trials", "Dias invalidos.")
        plan = build_trial_account_plan(assignments, files_by_tanda, per_day, days)
        warnings = reused_trial_tanda_warnings(plan)
        result = "\n".join(warnings + [f"@{u}: {len(v)} videos" + (f" (faltan {plan.shortfalls[u]})" if u in plan.shortfalls else "") for u, v in plan.assigned.items()])
        if preview_only:
            self.trial_dist_result.delete("1.0", "end"); self.trial_dist_result.insert("1.0", result); return
        if plan.shortfalls and not preview_only:
            self.trial_dist_result.delete("1.0", "end")
            self.trial_dist_result.insert("1.0", result)
            return messagebox.showwarning(
                "Trials incompletos",
                "No se calendariza incompleto. Revisa VISTA PREVIA y asigna una tanda con videos suficientes por cuenta.",
            )
        if not messagebox.askyesno("Distribuir Trials", "\n\n".join(warnings + [f"Calendarizar {sum(map(len, plan.assigned.values()))} videos sin reutilizar metadata?"])):
            return
        ids = {r["username"]: r["id"] for r in self.db.get_trials_active_accounts()}
        def task():
            from Organizador import build_calendar_video_filename
            entries = []
            affected = set(plan.assigned)
            for user, files in plan.assigned.items():
                tanda = assignments[user]
                for index, name in enumerate(files):
                    day, slot = index // per_day + 1, index % per_day + 1
                    source_path = os.path.abspath(os.path.join(_BASE_DIR, "videos_finales", tanda, name))
                    entries.append(
                        build_entry(
                            username=user,
                            account_id=ids.get(user),
                            delivery_kind="trial",
                            day=day,
                            slot=slot,
                            tanda=tanda,
                            source_path=source_path,
                            telegram_filename=build_calendar_video_filename(name, tanda, ids.get(user), day, slot),
                            transform_log_id=self.db.get_video_transform_log_id(source_path),
                        )
                    )
            if affected:
                replace_entries(manifest_path(_BASE_DIR), entries, affected, "trial")
            count = len(entries)
            shortages = ", ".join(f"@{u}: faltan {n}" for u, n in plan.shortfalls.items())
            return f"OK: {count} videos Trial" + (f"\nSin reutilizar: {shortages}" if shortages else "")
        def done(success, text):
            self.trial_dist_result.delete("1.0", "end"); self.trial_dist_result.insert("1.0", text)
            if not success: messagebox.showerror("Trials", text)
        WorkerThread(self, done, task).start()

    def _build_dist_cuentas_tab(self, parent):
        """Tab: bloques secuenciales — cada cuenta recibe un bloque distinto del pool."""
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        body = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)

        # Mismo fix que en Forge: sin esto, mouse/trackpad con delta chico de
        # scroll (int(delta/6) trunca a 0 en CTkScrollableFrame) no mueve nada.
        def _cuentas_wheel_fix(event):
            if body.check_if_master_is_canvas(event.widget) and body._parent_canvas.yview() != (0.0, 1.0):
                body._parent_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        body.bind_all("<MouseWheel>", _cuentas_wheel_fix, add="+")

        parent = body

        # ── Diagrama visual ──────────────────────────────────────────────
        diag = Card(parent, title="Flujo de distribución por cuentas")
        diag.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        diag_txt = ctk.CTkTextbox(diag.body, height=85, font=FONT_MONO,
                                  fg_color="transparent", text_color=NEON_CYAN)
        diag_txt.pack(fill="x")
        diag_txt.insert("end",
            "  POOL DE VIDEOS  [vid_001 ... vid_N]  →  bloques secuenciales\n"
            "  ┌──────────────┬──────────────┬──────────────┬─────────────┐\n"
            "  │  Cta 1       │  Cta 2       │  Cta 3       │  Cta N      │\n"
            "  │  vids[0:K]   │  vids[K:2K]  │  vids[2K:3K] │  ...        │\n"
            "  │  (shuffle)   │  (shuffle)   │  (shuffle)   │  (shuffle)  │\n"
            "  └──────────────┴──────────────┴──────────────┴─────────────┘\n"
            "  K = videos/día × días del período   (bloque único por cuenta)"
        )
        diag_txt.configure(state="disabled")

        # ── Config ──────────────────────────────────────────────────────
        cfg = Card(parent, title="Configuración")
        cfg.grid(row=1, column=0, sticky="ew", padx=16, pady=6)
        cfg = cfg.body
        cfg.grid_columnconfigure((1, 3, 5), weight=1)

        # Fila 0: Tanda fuente
        ctk.CTkLabel(cfg, text="Tanda fuente:", text_color=TEXT_MUTED).grid(
            row=0, column=0, padx=(16, 8), pady=(16, 8), sticky="e")
        self.acct_dist_tanda = ctk.CTkComboBox(
            cfg, values=[], fg_color=BG_INPUT, border_color=BORDER,
            command=self._acct_on_tanda_selection_changed,
        )
        self.acct_dist_tanda.grid(row=0, column=1, columnspan=2, padx=(0, 16), pady=(16, 8), sticky="ew")

        ctk.CTkLabel(cfg, text="2da tanda:", text_color=TEXT_MUTED).grid(
            row=0, column=3, padx=(8, 8), pady=(16, 8), sticky="e")
        self.acct_dist_tanda_2 = ctk.CTkComboBox(
            cfg, values=[""], fg_color=BG_INPUT, border_color=BORDER,
            command=self._acct_on_tanda_selection_changed,
        )
        self.acct_dist_tanda_2.grid(row=0, column=4, columnspan=2, padx=(0, 16), pady=(16, 8), sticky="ew")

        self._build_logistica_caption_controls(
            cfg, row=1, columnspan=6,
            selector_attr="acct_dist_tanda", label_attr="acct_dist_lbl_cap",
            padx=(16, 16), pady=(0, 8),
        )

        self._build_logistica_caption_controls(
            cfg, row=2, columnspan=6,
            selector_attr="acct_dist_tanda_2", label_attr="acct_dist_lbl_cap_2",
            padx=(16, 16), pady=(0, 8),
        )

        ctk.CTkLabel(cfg, text="Modo captions T1:", text_color=TEXT_MUTED).grid(
            row=3, column=0, padx=(16, 8), pady=(0, 8), sticky="e")
        self.acct_dist_caption_mode_1 = ctk.CTkComboBox(
            cfg, values=["General", "Individual"], fg_color=BG_INPUT, border_color=BORDER,
            command=self._acct_on_caption_mode_change,
        )
        self.acct_dist_caption_mode_1.set("General")
        self.acct_dist_caption_mode_1.grid(row=3, column=1, padx=(0, 16), pady=(0, 8), sticky="ew")
        ctk.CTkLabel(cfg, text="Modo captions T2:", text_color=TEXT_MUTED).grid(
            row=3, column=2, padx=(8, 8), pady=(0, 8), sticky="e")
        self.acct_dist_caption_mode_2 = ctk.CTkComboBox(
            cfg, values=["General", "Individual"], fg_color=BG_INPUT, border_color=BORDER,
            command=self._acct_on_caption_mode_change,
        )
        self.acct_dist_caption_mode_2.set("General")
        self.acct_dist_caption_mode_2.grid(row=3, column=3, padx=(0, 16), pady=(0, 8), sticky="ew")
        self.acct_individual_captions_btn = GhostButton(
            cfg, text="Editar captions individuales", state="disabled",
            command=self._acct_refresh_individual_captions,
        )
        self.acct_individual_captions_btn.grid(row=3, column=4, columnspan=2, padx=8, pady=(0, 8), sticky="w")

        # Fila 1: Videos al día + Período + total calculado
        ctk.CTkLabel(cfg, text="Videos al día:", text_color=TEXT_MUTED).grid(
            row=4, column=0, padx=(16, 8), pady=(4, 16), sticky="e")
        self.acct_dist_vpd = Stepper(
            cfg, value=3, min=1, max=50,
            command=lambda _: self._acct_dist_update_total()
        )
        self.acct_dist_vpd.grid(row=4, column=1, padx=(0, 16), pady=(4, 16), sticky="w")

        ctk.CTkLabel(cfg, text="Período:", text_color=TEXT_MUTED).grid(
            row=4, column=2, padx=(8, 8), pady=(4, 16), sticky="e")
        self.acct_dist_period = ctk.CTkComboBox(
            cfg, values=list(self.PERIOD_DAYS.keys()),
            fg_color=BG_INPUT, border_color=BORDER,
            command=lambda _: self._acct_dist_update_total())
        self.acct_dist_period.set("1 semana")
        self.acct_dist_period.grid(row=4, column=3, padx=(0, 16), pady=(4, 16), sticky="ew")

        self.acct_dist_total_lbl = ctk.CTkLabel(
            cfg, text="= 21 videos/cuenta",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=NEON_CYAN)
        self.acct_dist_total_lbl.grid(row=4, column=4, columnspan=2, padx=(0, 16), pady=(4, 16), sticky="w")
        self._acct_dist_update_total()

        # ── Cuentas ──────────────────────────────────────────────────────
        acc_card = Card(parent, title="Cuentas destino")
        acc_card.grid(row=2, column=0, sticky="ew", padx=16, pady=6)
        acc = acc_card.body
        acc.grid_columnconfigure(0, weight=1)

        acc_hdr = ctk.CTkFrame(acc, fg_color="transparent")
        acc_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        GhostButton(acc_hdr, text="Limpiar", width=70,
                    command=self._acct_dist_clear).pack(side="right", padx=4)
        GhostButton(acc_hdr, text="+ Suicide", width=80,
                    command=lambda: self._acct_dist_load_file("suicide")).pack(side="right", padx=4)
        PrimaryButton(acc_hdr, text="+ Promo", width=80,
                      command=lambda: self._acct_dist_load_file("promo")).pack(side="right", padx=4)

        # ── Selector de categoría ─────────────────────────────────────────
        cat_row = ctk.CTkFrame(acc, fg_color="transparent")
        cat_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 2))
        ctk.CTkLabel(cat_row, text="Categoría:", font=FONT_BODY,
                     text_color=TEXT_MUTED).pack(side="left", padx=(0, 8))
        self.acct_dist_cat = ctk.CTkComboBox(cat_row, values=[], width=180,
                                              fg_color=BG_INPUT, border_color=BORDER,
                                              button_color=BORDER, text_color=TEXT_BODY,
                                              dropdown_fg_color=BG_CARD2)
        self.acct_dist_cat.pack(side="left", padx=(0, 8))
        GhostButton(cat_row, text="+ Cargar categoría",
                    command=self._acct_dist_load_category).pack(side="left")

        self.acct_dist_list = ctk.CTkTextbox(acc, height=90, fg_color=BG_INPUT,
                                              text_color=TEXT_BODY, font=FONT_MONO)
        self.acct_dist_list.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 4))

        add_row = ctk.CTkFrame(acc, fg_color="transparent")
        add_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.acct_dist_entry = ctk.CTkEntry(add_row, fg_color=BG_INPUT, border_color=BORDER,
                                             placeholder_text="@cuenta_nueva", width=200)
        self.acct_dist_entry.pack(side="left", padx=(0, 8))
        PrimaryButton(add_row, text="Agregar",
                      command=self._acct_dist_add).pack(side="left", padx=(0, 4))
        DangerButton(add_row, text="Última",
                     command=self._acct_dist_remove_last).pack(side="left")

        # ── Botones principales ──────────────────────────────────────────
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.grid(row=3, column=0, pady=16)
        GhostButton(btn_row, text="Resetear todo", height=BTN_H_LG,
                    command=self._acct_dist_reset).pack(side="left", padx=(0, 20))
        GhostButton(btn_row, text="PREVISUALIZAR", height=BTN_H_LG,
                    command=lambda: self._acct_dist_run(preview_only=True)).pack(side="left", padx=10)
        PrimaryButton(btn_row, text="EJECUTAR POR CUENTAS", height=BTN_H_LG,
                      command=lambda: self._acct_dist_run(preview_only=False)).pack(side="left", padx=10)

        lane_card = Card(parent, title="Agregar carril al calendario existente")
        lane_card.grid(row=4, column=0, sticky="ew", padx=16, pady=(2, 8))
        lane = lane_card.body
        lane.grid_columnconfigure(1, weight=1)
        lane.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(lane, text="Destino:", text_color=TEXT_MUTED).grid(
            row=0, column=0, padx=(14, 6), pady=(12, 6), sticky="e")
        self.acct_lane_target = ctk.CTkComboBox(
            lane,
            values=[
                "instagram_reel", "instagram_trial_reel", "instagram_story",
                "instagram_post", "facebook_story", "facebook_page_post",
                "facebook_reel", "facebook_marketplace_listing",
            ],
            fg_color=BG_INPUT, border_color=BORDER, width=230,
        )
        self.acct_lane_target.set("instagram_story")
        self.acct_lane_target.grid(row=0, column=1, padx=6, pady=(12, 6), sticky="ew")
        ctk.CTkLabel(lane, text="Carpeta de finales por cuenta:", text_color=TEXT_MUTED).grid(
            row=0, column=2, padx=(10, 6), pady=(12, 6), sticky="e")
        self.acct_lane_root = ctk.CTkEntry(
            lane, fg_color=BG_INPUT, border_color=BORDER,
            placeholder_text="Raíz con una subcarpeta por cuenta",
        )
        self.acct_lane_root.grid(row=0, column=3, padx=6, pady=(12, 6), sticky="ew")
        GhostButton(
            lane, text="Elegir carpeta", width=110,
            command=self._acct_lane_choose_root,
        ).grid(row=0, column=4, padx=(4, 14), pady=(12, 6))

        ctk.CTkLabel(lane, text="Fecha inicial:", text_color=TEXT_MUTED).grid(
            row=1, column=0, padx=(14, 6), pady=6, sticky="e")
        self.acct_lane_start_date = ctk.CTkEntry(lane, fg_color=BG_INPUT, border_color=BORDER, width=130)
        self.acct_lane_start_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.acct_lane_start_date.grid(row=1, column=1, padx=6, pady=6, sticky="w")
        ctk.CTkLabel(lane, text="Días / cada N días:", text_color=TEXT_MUTED).grid(
            row=1, column=2, padx=(10, 6), pady=6, sticky="e")
        self.acct_lane_horizon = ctk.CTkEntry(lane, fg_color=BG_INPUT, border_color=BORDER, width=62)
        self.acct_lane_horizon.insert(0, "7")
        self.acct_lane_horizon.grid(row=1, column=3, padx=(6, 2), pady=6, sticky="w")
        self.acct_lane_every_days = ctk.CTkEntry(lane, fg_color=BG_INPUT, border_color=BORDER, width=62)
        self.acct_lane_every_days.insert(0, "1")
        self.acct_lane_every_days.grid(row=1, column=3, padx=(76, 2), pady=6, sticky="w")
        ctk.CTkLabel(lane, text="Horas (HH:MM):", text_color=TEXT_MUTED).grid(
            row=2, column=0, padx=(14, 6), pady=6, sticky="e")
        self.acct_lane_times = ctk.CTkEntry(
            lane, fg_color=BG_INPUT, border_color=BORDER,
            placeholder_text="09:00,16:00",
        )
        self.acct_lane_times.insert(0, "09:00,16:00")
        self.acct_lane_times.grid(row=2, column=1, padx=6, pady=6, sticky="ew")
        ctk.CTkLabel(lane, text="Caption / aviso de Story:", text_color=TEXT_MUTED).grid(
            row=2, column=2, padx=(10, 6), pady=6, sticky="e")
        self.acct_lane_caption = ctk.CTkEntry(lane, fg_color=BG_INPUT, border_color=BORDER)
        self.acct_lane_caption.grid(row=2, column=3, padx=(6, 14), pady=6, sticky="ew")
        ctk.CTkLabel(lane, text="Título Marketplace:", text_color=TEXT_MUTED).grid(
            row=3, column=0, padx=(14, 6), pady=6, sticky="e")
        self.acct_lane_market_title = ctk.CTkEntry(lane, fg_color=BG_INPUT, border_color=BORDER)
        self.acct_lane_market_title.grid(row=3, column=1, padx=6, pady=6, sticky="ew")
        ctk.CTkLabel(lane, text="Precio / condición:", text_color=TEXT_MUTED).grid(
            row=3, column=2, padx=(10, 6), pady=6, sticky="e")
        market_fields = ctk.CTkFrame(lane, fg_color="transparent")
        market_fields.grid(row=3, column=3, padx=(6, 14), pady=6, sticky="ew")
        self.acct_lane_market_price = ctk.CTkEntry(
            market_fields, fg_color=BG_INPUT, border_color=BORDER,
            placeholder_text="Precio", width=100,
        )
        self.acct_lane_market_price.pack(side="left", padx=(0, 6))
        self.acct_lane_market_condition = ctk.CTkEntry(
            market_fields, fg_color=BG_INPUT, border_color=BORDER,
            placeholder_text="Condición", width=120,
        )
        self.acct_lane_market_condition.pack(side="left")
        ctk.CTkLabel(
            lane,
            text="Fecha inicial: ancla los reels heredados que aún no tienen fecha explícita.",
            text_color=TEXT_MUTED,
        ).grid(row=4, column=0, columnspan=5, padx=14, pady=(2, 0), sticky="w")
        lane_buttons = ctk.CTkFrame(lane, fg_color="transparent")
        lane_buttons.grid(row=5, column=0, columnspan=5, pady=(8, 12))
        self._load_lane_defaults()
        GhostButton(
            lane_buttons, text="Previsualizar carril",
            command=lambda: self._acct_multichannel_run(preview_only=True),
        ).pack(side="left", padx=6)
        GhostButton(
            lane_buttons, text="Ver calendario",
            command=lambda: self.show_frame("Calendario"),
        ).pack(side="left", padx=6)
        GhostButton(
            lane_buttons, text="Guardar defaults",
            command=self._save_lane_defaults,
        ).pack(side="left", padx=6)
        PrimaryButton(
            lane_buttons, text="Agregar al calendario",
            command=lambda: self._acct_multichannel_run(preview_only=False),
        ).pack(side="left", padx=6)

        # ── Resultados ───────────────────────────────────────────────────
        self.acct_dist_result = ctk.CTkTextbox(parent, fg_color=BG_CARD2, height=200,
                                                text_color=NEON_CYAN, font=FONT_MONO)
        self.acct_dist_result.grid(row=5, column=0, sticky="nsew", padx=16, pady=(0, 16))

    # ── Lógica Logística ─────────────────────────────────────────────────────
    def reload_dist_lists(self, event=None):
        try:
            # La lista de logística se sincroniza con el disco: registra en la DB
            # cualquier carpeta nueva de videos_finales/ y oculta tandas Forge
            # huérfanas (carpeta renombrada/borrada). Ver DatabaseManager.list_and_sync_tandas.
            vf_root = os.path.join(_BASE_DIR, "videos_finales")
            tandas = self.db.list_and_sync_tandas(vf_root)
            trial_tandas = self.db.get_trial_tandas()
            normal_tandas = [name for name in tandas if name not in set(trial_tandas)]

            if hasattr(self, "c_tandas"):
                self.c_tandas.configure(values=normal_tandas)
                if not self.c_tandas.get() and normal_tandas: self.c_tandas.set(normal_tandas[0])
                self._refresh_tanda_caption_label()

            if hasattr(self, "c_tandas_2"):
                self.c_tandas_2.configure(values=[""] + normal_tandas)

            if hasattr(self, "acct_dist_tanda"):
                self.acct_dist_tanda.configure(values=normal_tandas)
                if not self.acct_dist_tanda.get() and normal_tandas:
                    self.acct_dist_tanda.set(normal_tandas[0])
                self._refresh_tanda_caption_label()

            if hasattr(self, "acct_dist_tanda_2"):
                acct_tanda_2_values = [""] + normal_tandas
                self.acct_dist_tanda_2.configure(values=acct_tanda_2_values)
                if self.acct_dist_tanda_2.get() not in acct_tanda_2_values:
                    self.acct_dist_tanda_2.set("")
                self._acct_update_individual_captions_button()

            if hasattr(self, "trial_account_scroll"):
                active_trials = len(self.db.get_trials_active_accounts())
                self.trial_accounts_lbl.configure(text=f"{active_trials} cuentas con TRIALS ACTIVOS")
                self._trial_refresh_account_rows()
                self._trial_refresh_sources()

            cats = self.db.get_categories()
            if hasattr(self, "c_dest"):
                self.c_dest.configure(values=cats)
                if not self.c_dest.get() and cats: self.c_dest.set(cats[0])
            if hasattr(self, "acct_dist_cat"):
                self.acct_dist_cat.configure(values=cats)
                if not self.acct_dist_cat.get() and cats: self.acct_dist_cat.set(cats[0])
        except Exception as e:
            print(f"⚠️ Error al refrescar listas dist: {e}")

    def _refresh_tanda_caption_label(self, _value=None):
        self._refresh_logistica_caption_label("c_tandas", "tandas_lbl_cap")
        self._refresh_logistica_caption_label("acct_dist_tanda", "acct_dist_lbl_cap")
        self._refresh_logistica_caption_label("acct_dist_tanda_2", "acct_dist_lbl_cap_2")

    def _acct_on_tanda_selection_changed(self, _value=None):
        self._refresh_tanda_caption_label()
        self._acct_update_individual_captions_button()

    def _get_logistica_caption_tanda_name(self, selector_attr):
        selector = getattr(self, selector_attr, None)
        if selector is None:
            return ""
        return selector.get().strip()

    def _refresh_logistica_caption_label(self, selector_attr, label_attr):
        label = getattr(self, label_attr, None)
        if label is None:
            return
        tanda_name = self._get_logistica_caption_tanda_name(selector_attr)
        tanda = self.db.get_tanda_by_name(tanda_name) if tanda_name else None
        path = (tanda or {}).get("captions_file_path") or ""
        if path:
            label.configure(text=os.path.basename(path), text_color=NEON_CYAN)
        else:
            label.configure(text="Sin captions asignados", text_color=TEXT_MUTED)

    def assign_captions_to_selected_tanda(self, selector_attr="c_tandas"):
        tanda_name = self._get_logistica_caption_tanda_name(selector_attr)
        if not tanda_name:
            return messagebox.showwarning("⚠️", "Selecciona una tanda primero.")
        path = filedialog.askopenfilename(filetypes=[("Archivos de Texto", "*.txt")])
        if not path:
            return
        if not self.db.set_tanda_captions(tanda_name, path):
            return messagebox.showerror("Error", f"No encontré la tanda '{tanda_name}'.")
        self._refresh_tanda_caption_label()
        messagebox.showinfo("Captions asignados", f"'{os.path.basename(path)}' quedó asignado a '{tanda_name}'.")

    def clear_captions_from_selected_tanda(self, selector_attr="c_tandas"):
        tanda_name = self._get_logistica_caption_tanda_name(selector_attr)
        if not tanda_name:
            return messagebox.showwarning("⚠️", "Selecciona una tanda primero.")
        if not messagebox.askyesno("Quitar captions", f"¿Quitar los captions de '{tanda_name}'?"):
            return
        if not self.db.set_tanda_captions(tanda_name, None):
            return messagebox.showerror("Error", f"No encontré la tanda '{tanda_name}'.")
        self._refresh_tanda_caption_label()

    def preview_distribution(self):
        tanda = self.c_tandas.get()
        dest = self.c_dest.get()
        tanda_2 = self.c_tandas_2.get().strip()
        days_input = self.e_days.get()
        
        try: quota = int(self.e_quota.get())
        except ValueError: return messagebox.showwarning("⚠️", "Cuota diaria inválida.")
            
        if not tanda or not dest: return messagebox.showwarning("⚠️", "Selecciona Tanda y Categoría Destino.")
            
        def task():
            import Organizador
            res = ""
            if tanda_2:
                res = Organizador.preview_distribution_tanda(tanda, dest, quota, self.fillup_var.get(), days_input)
                res += "\n\n" + "═" * 70 + "\n"
                res += f"   🎲 SEGUNDA TANDA OPCIONAL: {tanda_2}\n"
                res += "═" * 70 + "\n\n"
                res += Organizador.preview_distribution_tanda(tanda_2, dest, quota, self.fillup_var.get(), days_input)
            else:
                res = Organizador.preview_distribution_tanda(tanda, dest, quota, self.fillup_var.get(), days_input)
            return res
            
        def done(success, result):
            if success:
                win = ctk.CTkToplevel(self)
                win.title(f"📊 Plan de Distribución: {tanda}")
                self._fit_toplevel(win, 950, 700)
                win.configure(fg_color=BG_APP)
                txt = ctk.CTkTextbox(win, fg_color=BG_CARD, text_color=NEON_CYAN, font=FONT_MONO)
                txt.pack(fill="both", expand=True, padx=20, pady=20)
                txt.insert("end", result)
                txt.configure(state="disabled")
            else:
                messagebox.showerror("Error en Simulación", result)
        
        WorkerThread(self, done, task).start()

    def start_distribution(self):
        tanda = self.c_tandas.get()
        dest = self.c_dest.get()
        days_input = self.e_days.get()
        tanda_2 = self.c_tandas_2.get().strip()
        if tanda_2 == tanda: tanda_2 = ""
        
        try: quota = int(self.e_quota.get())
        except ValueError: return messagebox.showwarning("⚠️", "Meta diaria inválida.")
            
        if not tanda or not dest: return messagebox.showwarning("⚠️", "Faltan datos.")
        label_tandas = tanda if not tanda_2 else f"{tanda} + {tanda_2}"

        if not messagebox.askyesno("Confirmación", f"¿Distribuir '{label_tandas}' a la categoría '{dest}'?"): return
            
        def task():
            import Organizador
            return Organizador.distribute_tanda(tanda, dest, quota, self.fillup_var.get(), days_input, tanda_name_2=tanda_2 if tanda_2 else None)
            
        def done(success, result):
            if success: messagebox.showinfo("Éxito", result)
            else: messagebox.showerror("Error", result)
            self.refresh_dashboard()
            
        WorkerThread(self, done, task).start()

    # ── Lógica Por Cuentas ───────────────────────────────────────────────────

    def _acct_dist_accounts(self) -> list[str]:
        raw = self.acct_dist_list.get("1.0", "end").strip()
        return [a.strip() for a in raw.splitlines() if a.strip()]

    def _acct_dist_selected_tandas(self) -> list[str]:
        return [tanda for tanda, _mode in self._acct_dist_selected_tanda_modes()]

    def _acct_dist_selected_tanda_modes(self) -> list[tuple[str, str]]:
        tandas = []
        for attr in ("acct_dist_tanda", "acct_dist_tanda_2"):
            selector = getattr(self, attr, None)
            value = selector.get().strip() if selector is not None else ""
            if value and value not in [tanda for tanda, _mode in tandas]:
                mode_attr = "acct_dist_caption_mode_2" if attr.endswith("_2") else "acct_dist_caption_mode_1"
                mode_selector = getattr(self, mode_attr, None)
                raw_mode = mode_selector.get().strip().lower() if mode_selector is not None else "general"
                mode = "individual" if raw_mode == "individual" else "general"
                tandas.append((value, mode))
        return tandas

    def _acct_individual_caption_tandas(self) -> list[str]:
        return [
            tanda
            for tanda, mode in self._acct_dist_selected_tanda_modes()
            if mode == "individual"
        ]

    def _acct_caption_mode_map(self) -> dict[str, str]:
        return dict(self._acct_dist_selected_tanda_modes())

    def _acct_dist_load_file(self, category: str):
        fpath = os.path.join(_BASE_DIR, f"accounts_{category}.txt")
        if not os.path.exists(fpath):
            messagebox.showwarning("⚠️", f"No encontré: {fpath}")
            return
        existing = self._acct_dist_accounts()
        with open(fpath, "r", encoding="utf-8") as fh:
            for line in fh:
                acc = line.strip()
                if acc and acc not in existing:
                    self.acct_dist_list.insert("end", acc + "\n")

    def _acct_dist_load_category(self):
        cat = self.acct_dist_cat.get()
        if not cat:
            messagebox.showwarning("⚠️", "Seleccioná una categoría primero.")
            return
        accounts = self.db.get_accounts_by_type(cat)
        if not accounts:
            messagebox.showwarning("⚠️", f"No hay cuentas en la categoría «{cat}».")
            return
        existing = self._acct_dist_accounts()
        added = 0
        for acc in accounts:
            if acc not in existing:
                self.acct_dist_list.insert("end", acc + "\n")
                added += 1
        if added == 0:
            messagebox.showinfo("ℹ️", f"Todas las cuentas de «{cat}» ya están en la lista.")

    def _acct_dist_clear(self):
        self.acct_dist_list.delete("1.0", "end")

    def _refresh_dist_frame(self):
        """Destruye y reconstruye el frame de Logística completo (equivalente a F5)."""
        f = self._frames["Logistica"]
        for w in f.winfo_children():
            w.destroy()
        self._build_dist_frame()

    def _acct_dist_reset(self):
        self._refresh_dist_frame()

    def _tandas_dist_reset(self):
        self._refresh_dist_frame()

    def _acct_dist_add(self):
        acc = self.acct_dist_entry.get().strip()
        if acc and acc not in self._acct_dist_accounts():
            self.acct_dist_list.insert("end", acc + "\n")
        self.acct_dist_entry.delete(0, "end")

    def _acct_dist_remove_last(self):
        lines = [l for l in self.acct_dist_list.get("1.0", "end").strip().splitlines() if l.strip()]
        if lines:
            lines.pop()
            self.acct_dist_list.delete("1.0", "end")
            if lines:
                self.acct_dist_list.insert("end", "\n".join(lines) + "\n")

    def _acct_dist_update_total(self, *_):
        try:
            vpd = int(self.acct_dist_vpd.get())
        except ValueError:
            vpd = 0
        period_str = self.acct_dist_period.get()
        if str(period_str).strip().upper() == "MAX":
            self.acct_dist_total_lbl.configure(text="= MAX según tanda")
            return
        days = self.PERIOD_DAYS.get(period_str, 7)
        total = vpd * days
        self.acct_dist_total_lbl.configure(text=f"= {total} videos/cuenta")

    def _acct_dist_load_hist(self) -> dict:
        if os.path.exists(_ACCT_HIST_FILE):
            try:
                with open(_ACCT_HIST_FILE, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                pass
        return {}

    def _acct_dist_save_hist(self, history: dict):
        with open(_ACCT_HIST_FILE, "w", encoding="utf-8") as fh:
            json.dump(history, fh, indent=2, ensure_ascii=False)

    def _acct_lane_choose_root(self):
        path = filedialog.askdirectory(title="Carpeta raiz de finales por cuenta", parent=self)
        if path:
            self.acct_lane_root.delete(0, "end")
            self.acct_lane_root.insert(0, path)

    def _load_lane_defaults(self):
        try:
            raw = self.db.get_social_publishing_setting("por_cuentas_lane_defaults", "")
            values = json.loads(raw) if raw else {}
            target = values.get("target", "instagram_story")
            if target in self.acct_lane_target.cget("values"):
                self.acct_lane_target.set(target)
            for widget, key, default in (
                (self.acct_lane_horizon, "horizon_days", "7"),
                (self.acct_lane_every_days, "every_days", "1"),
                (self.acct_lane_times, "times", "09:00,16:00"),
            ):
                value = str(values.get(key, default))
                widget.delete(0, "end")
                widget.insert(0, value)
        except (AttributeError, TypeError, ValueError):
            return

    def _save_lane_defaults(self):
        try:
            values = {
                "target": self.acct_lane_target.get().strip(),
                "horizon_days": int(self.acct_lane_horizon.get()),
                "every_days": int(self.acct_lane_every_days.get()),
                "times": self.acct_lane_times.get().strip(),
            }
            expand_lane_slots(
                self.acct_lane_start_date.get().strip(),
                values["horizon_days"],
                values["every_days"],
                [part.strip() for part in values["times"].split(",") if part.strip()],
            )
            self.db.set_social_publishing_setting(
                "por_cuentas_lane_defaults", json.dumps(values, ensure_ascii=True)
            )
        except (AttributeError, TypeError, ValueError) as error:
            messagebox.showwarning("Defaults de carril", str(error), parent=self)
            return
        messagebox.showinfo("Defaults de carril", "Preferencias predeterminadas guardadas.", parent=self)

    def _acct_multichannel_run(self, preview_only: bool = True):
        accounts = self._acct_dist_accounts()
        root_text = self.acct_lane_root.get().strip()
        target = self.acct_lane_target.get().strip()
        start_date = self.acct_lane_start_date.get().strip()
        times = [value.strip() for value in self.acct_lane_times.get().split(",") if value.strip()]
        caption = self.acct_lane_caption.get().strip()
        if len(caption) > 3500:
            messagebox.showerror("Carril", "Caption/aviso demasiado largo (máximo 3500 caracteres).", parent=self)
            return
        marketplace_title = self.acct_lane_market_title.get().strip()
        marketplace_price = self.acct_lane_market_price.get().strip()
        marketplace_condition = self.acct_lane_market_condition.get().strip()
        try:
            horizon_days = int(self.acct_lane_horizon.get())
            every_days = int(self.acct_lane_every_days.get())
            slots = expand_lane_slots(start_date, horizon_days, every_days, times)
            if not accounts:
                raise ValueError("Carga las cuentas destino en Por Cuentas.")
            if not root_text or not Path(root_text).is_dir():
                raise ValueError("Selecciona una carpeta raiz existente.")
            if not target:
                raise ValueError("Selecciona el destino del carril.")
            if target == "facebook_marketplace_listing" and (not marketplace_title or not marketplace_price):
                raise ValueError("Marketplace requiere título y precio.")
        except ValueError as error:
            messagebox.showwarning("Carril", str(error), parent=self)
            return

        root = Path(root_text)
        account_rows = {row["username"]: row for row in self.db.get_all_accounts()}
        finals_by_account = {}
        partial_notices = []
        extension_filter = {".mp4", ".mov", ".m4v", ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
        video_targets = {"instagram_reel", "instagram_trial_reel", "facebook_reel"}
        if target == "facebook_marketplace_listing":
            extension_filter = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
        for username in accounts:
            account_dir = root / username
            if not account_dir.is_dir() and len(accounts) == 1:
                account_dir = root
            if not account_dir.is_dir():
                messagebox.showwarning(
                    "Carril", f"Falta la subcarpeta de finales para @{username}: {root / username}", parent=self
                )
                return
            account_finals = sorted(
                (path for path in account_dir.rglob("*") if path.is_file() and path.suffix.lower() in extension_filter),
                key=lambda path: str(path).casefold(),
            )
            if target in video_targets:
                from Organizador import _tanda_video_inventory

                videos, notice = _tanda_video_inventory(
                    str(account_dir), extensions=(".mp4", ".mov", ".m4v")
                )
                if notice and not notice.startswith("Tanda Forge parcial:"):
                    messagebox.showwarning("Inventario Forge", f"@{username}: {notice}", parent=self)
                    return
                if notice:
                    partial_notices.append(f"@{username}: {notice}")
                allowed_videos = set(videos)
                account_finals = [path for path in account_finals if path.name in allowed_videos]
            finals_by_account[username] = account_finals
            if len(finals_by_account[username]) < len(slots):
                messagebox.showwarning(
                    "Finales insuficientes",
                    f"@{username}: el carril requiere {len(slots)} archivos finales y hay "
                    f"{len(finals_by_account[username])}.",
                    parent=self,
                )
                return

        seen_final_paths = {}
        for username, paths in finals_by_account.items():
            for path in paths[:len(slots)]:
                resolved_path = str(path.resolve()).casefold()
                previous_owner = seen_final_paths.get(resolved_path)
                if previous_owner and previous_owner != username:
                    messagebox.showwarning(
                        "Final compartido",
                        f"El mismo archivo final aparece para @{previous_owner} y @{username}. "
                        "Cada cuenta necesita su propio final.",
                        parent=self,
                    )
                    return
                seen_final_paths[resolved_path] = username

        account_ids = {row["username"]: row.get("id") for row in self.db.get_all_accounts()}
        lane_id = str(uuid.uuid4())
        candidates = []
        try:
            for username in accounts:
                account = account_rows.get(username)
                if not account:
                    raise ValueError(f"La cuenta @{username} no existe en la base local.")
                va_name = account.get("assigned_va") or "Sin Asignar"
                timezone = self.db.get_va_timezone(va_name)
                is_story = target in {"instagram_story", "facebook_story"}
                story_link = self.db.resolve_story_link_for_account(username) if is_story else ""
                if is_story and not story_link:
                    raise ValueError(f"Configura el enlace de Story de @{username} en Cuentas.")
                delivery_kind = "trial" if target == "instagram_trial_reel" else "normal"
                request = LaneRequest(
                    username=username,
                    account_id=account_ids.get(username),
                    tanda=root.name,
                    delivery_kind=delivery_kind,
                    publication_target=target,
                    timezone=timezone,
                    media_kind="image" if target == "facebook_marketplace_listing" else "mixed",
                    lane_id=lane_id,
                    plan_id=lane_id,
                    start_date=start_date,
                    horizon_days=horizon_days,
                    every_days=every_days,
                    times=times,
                    caption=caption,
                    story_link_url=story_link,
                    story_announcement_text=caption if is_story else "",
                    platform_payload=(
                        {
                            "title": marketplace_title,
                            "price": marketplace_price,
                            "condition": marketplace_condition,
                            "description": caption,
                        }
                        if target == "facebook_marketplace_listing"
                        else {}
                    ),
                )
                entries = build_lane_entries(request, finals_by_account[username])
                for entry, source_path in zip(entries, finals_by_account[username]):
                    extension = source_path.suffix.lower()
                    entry["media_kind"] = "video" if extension in {".mp4", ".mov", ".m4v"} else "image"
                    if target in {"instagram_reel", "instagram_trial_reel", "facebook_reel"} and entry["media_kind"] != "video":
                        raise ValueError(f"{target} necesita finales de video.")
                    if target == "facebook_marketplace_listing" and entry["media_kind"] != "image":
                        raise ValueError("Marketplace acepta finales de imagen en este carril.")
                candidates.extend(entries)

            manifest_file = manifest_path(_BASE_DIR)
            schedule_resolution_cache = {}
            selected_account_names = set(accounts)

            def schedule_resolver(entry):
                if entry.get("username") not in selected_account_names:
                    return {}
                return resolve_legacy_reel_schedule(
                    entry, start_date, self.db, schedule_resolution_cache
                )

            current_entries = load_entries(manifest_file, require_source=False)
            scheduled_paths = {}
            for existing in current_entries:
                source_path = str(existing.get("source_path") or "").strip()
                if not source_path:
                    continue
                path_key = os.path.normcase(os.path.realpath(source_path)).casefold()
                scheduled_paths.setdefault(path_key, existing)
            candidate_paths = set()
            for entry in candidates:
                path_key = os.path.normcase(
                    os.path.realpath(str(entry.get("source_path") or ""))
                ).casefold()
                previous = scheduled_paths.get(path_key)
                if previous:
                    previous_schedule = " ".join(
                        value for value in (
                            str(previous.get("scheduled_date") or ""),
                            str(previous.get("scheduled_time") or ""),
                        ) if value
                    ) or f"dia {previous.get('day')} slot {previous.get('slot')}"
                    raise ValueError(
                        f"El final {Path(entry['source_path']).name} ya esta calendarizado "
                        f"para @{previous.get('username')} ({previous.get('publication_target') or 'Reel'}, "
                        f"{previous_schedule}). Usa otro final de Forge."
                    )
                if path_key in candidate_paths:
                    raise ValueError(
                        f"El mismo archivo final aparece mas de una vez en los carriles: "
                        f"{Path(entry['source_path']).name}."
                    )
                candidate_paths.add(path_key)
            resolved_entries = []
            for entry in current_entries:
                schedule = schedule_resolver(entry)
                resolved_entries.append({**entry, **schedule} if schedule else entry)
            plan = merge_scheduled_entries(resolved_entries, candidates)
        except (OSError, ValueError) as error:
            messagebox.showerror("Carril", str(error), parent=self)
            return

        lines = [
            "PREVISUALIZACION DE CARRIL" if preview_only else "CONFIRMACION DE CARRIL",
            f"Destino: {target}",
            f"Periodo: {start_date} + {horizon_days - 1} dias; cada {every_days} dia(s)",
            f"Cuentas: {len(accounts)} | Publicaciones nuevas: {len(candidates)}",
            "",
        ]
        if partial_notices:
            lines.extend(["AVISO: TANDAS FORGE PARCIALES"])
            lines.extend(f"- {notice}" for notice in partial_notices)
            lines.append("")
        selected_names = set(accounts)
        for entry in plan.entries:
            if entry.get("username") not in selected_names:
                continue
            if not (start_date <= entry.get("scheduled_date", "") <= (date.fromisoformat(start_date) + timedelta(days=horizon_days - 1)).isoformat()):
                continue
            marker = "NUEVA" if entry in candidates else "EXISTENTE"
            lines.append(
                f"{entry.get('scheduled_date')} {entry.get('scheduled_time')} "
                f"@{entry.get('username')} {entry.get('publication_target')} "
                f"[{marker}] {entry.get('telegram_filename')}"
            )
        if plan.conflicts:
            lines.extend(["", "CONFLICTOS:"])
            lines.extend(
                f"@{conflict.username} {conflict.scheduled_date} {conflict.scheduled_time}: "
                f"ya existe una publicacion. No se guardo el plan."
                for conflict in plan.conflicts
            )

        result_text = "\n".join(lines)
        if not preview_only:
            if plan.conflicts:
                self.acct_dist_result.configure(state="normal")
                self.acct_dist_result.delete("1.0", "end")
                self.acct_dist_result.insert("end", result_text)
                self.acct_dist_result.configure(state="disabled")
                return
            if not messagebox.askyesno("Agregar carril", result_text + "\n\n¿Confirmar y agregar?", parent=self):
                return
            try:
                saved = append_scheduled_entries(manifest_file, candidates, schedule_resolver)
            except (OSError, ValueError) as error:
                messagebox.showerror("No se pudo guardar el carril", str(error), parent=self)
                return
            if saved.conflicts:
                result_text += "\n\nEl calendario cambio desde la vista previa. No se guardo; vuelve a previsualizar."
            else:
                result_text += f"\n\nAgregadas {len(candidates)} entradas. No se copiaron archivos."

        self.acct_dist_result.configure(state="normal")
        self.acct_dist_result.delete("1.0", "end")
        self.acct_dist_result.insert("end", result_text)
        self.acct_dist_result.configure(state="disabled")

    def _acct_dist_run(self, preview_only: bool = True):
        selected_tandas = self._acct_dist_selected_tandas()
        tanda = selected_tandas[0] if selected_tandas else ""
        accounts = self._acct_dist_accounts()
        if not selected_tandas:
            messagebox.showwarning("⚠️", "Selecciona una tanda fuente")
            return
        individual_tandas = self._acct_individual_caption_tandas()
        if individual_tandas:
            missing = [
                f"{t}/{source}"
                for t in individual_tandas
                for source in self._acct_missing_individual_captions(t)
            ]
            if missing:
                return messagebox.showwarning(
                    "Captions individuales faltantes",
                    "Falta asignar caption a: " + ", ".join(missing),
                )
        if not accounts:
            messagebox.showwarning("⚠️", "Agrega al menos una cuenta")
            return
        try:
            vpd = int(self.acct_dist_vpd.get())
            if vpd <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Videos al día debe ser un número positivo")
            return
        period_str = self.acct_dist_period.get()
        max_period = str(period_str).strip().upper() == "MAX"
        days = self.PERIOD_DAYS.get(period_str, 7)
        n = None if max_period else vpd * days

        folders = {
            source_tanda: os.path.join(_BASE_DIR, "videos_finales", source_tanda)
            for source_tanda in selected_tandas
        }

        def task():
            nonlocal days, n
            import re
            from Organizador import build_calendar_video_filename
            caption_mode_map = self._acct_caption_mode_map()

            def forge_vid_id(fname):
                return source_key_from_filename(fname)

            all_vids, partial_notices = _acct_inventory_summary(folders)
            if not all_vids:
                raise ValueError("No se encontraron videos en las tandas seleccionadas")

            def item_key(item):
                return (item["tanda"], item["name"])

            def item_name(item):
                return item["name"]

            def item_display(item):
                if len(selected_tandas) > 1:
                    return f"{item['tanda']} / {item['name']}"
                return item["name"]

            if max_period:
                n = len(all_vids) // len(accounts)
                if n < 1:
                    raise ValueError(
                        f"No hay suficientes videos ({len(all_vids)}) para "
                        f"{len(accounts)} cuentas. MAX necesita al menos 1 video por cuenta."
                    )
                days = math.ceil(n / vpd)
                needed = n * len(accounts)
            else:
                needed = len(accounts) * vpd * days
            if len(all_vids) < needed:
                raise ValueError(
                    f"No hay suficientes videos ({len(all_vids)}) para "
                    f"{len(accounts)} cuentas × {vpd} vid/día × {days} días = {needed} necesarios"
                )

            db_account_ids = {
                str(row.get("username")): row.get("id")
                for row in self.db.get_all_accounts()
            }
            account_ids = {
                acc: db_account_ids.get(acc) or idx + 1
                for idx, acc in enumerate(accounts)
            }

            pool = all_vids[:]
            random.shuffle(pool)

            # plan[acc] = [[day0_vids], [day1_vids], ...]
            # Antichoque: mismo vid_id no se repite en la misma cuenta el mismo día (duro)
            # ni en la misma cuenta en ningún día (preferido)
            # ni en distintas cuentas el mismo día (penalizado)
            plan = {acc: [[] for _ in range(days)] for acc in accounts}
            assigned = set()
            acc_lifetime_vid_ids = {acc: set() for acc in accounts}

            for day_idx in range(days):
                day_vid_ids_used = set()
                slots_today = min(vpd, max(0, n - (day_idx * vpd)))

                for slot in range(slots_today):
                    slot_vid_ids_used = set()
                    accs_shuffled = accounts[:]
                    random.shuffle(accs_shuffled)

                    for acc_index, acc in enumerate(accs_shuffled):
                        acc_today_vid_ids = {forge_vid_id(item_name(v)) for v in plan[acc][day_idx]}
                        preferred_tanda = None
                        if len(selected_tandas) > 1 and n >= len(selected_tandas):
                            preferred_tanda = selected_tandas[(slot + acc_index) % len(selected_tandas)]
                        available = [
                            v for v in pool
                            if item_key(v) not in assigned
                            and forge_vid_id(item_name(v)) not in acc_today_vid_ids
                        ]
                        if preferred_tanda:
                            preferred = [v for v in available if v["tanda"] == preferred_tanda]
                            if preferred:
                                available = preferred
                        candidates = []
                        for v in available:
                            vid_id = forge_vid_id(item_name(v))
                            score = 0
                            if vid_id in acc_lifetime_vid_ids[acc]:
                                score += 200  # penalizar reutilización en misma cuenta
                            if vid_id in day_vid_ids_used:
                                score += 100  # penalizar mismo vid_id en distintas cuentas hoy
                            if vid_id in slot_vid_ids_used:
                                score += 50   # penalizar mismo slot entre cuentas
                            score += random.random()
                            candidates.append((score, v))

                        if not candidates:
                            raise ValueError(
                                f"Sin candidatos para '{acc}' día {day_idx+1} slot {slot+1}. "
                                f"Reducí cuentas, días o videos/día."
                            )

                        candidates.sort(key=lambda x: x[0])
                        chosen = candidates[0][1]
                        vid_id = forge_vid_id(item_name(chosen))

                        plan[acc][day_idx].append(chosen)
                        assigned.add(item_key(chosen))
                        acc_lifetime_vid_ids[acc].add(vid_id)
                        day_vid_ids_used.add(vid_id)
                        slot_vid_ids_used.add(vid_id)

            lines = []
            if partial_notices:
                lines += ["AVISO: TANDAS FORGE PARCIALES"]
                lines += [f"- {notice}" for notice in partial_notices]
                lines.append("")
            label = "👁️  PREVISUALIZACIÓN" if preview_only else "🚀  EJECUTANDO"
            total_per_acc = n
            period_detail = f"{days} días × {vpd} videos/día = {total_per_acc}/cuenta"
            if max_period and total_per_acc % vpd:
                period_detail = f"{total_per_acc}/cuenta en {days} días (último día parcial)"
            lines += [label, "=" * 60,
                      f"📦  Tanda      : {' + '.join(selected_tandas)}",
                      f"📦  Pool total  : {len(all_vids)} videos en {len(selected_tandas)} tanda(s)",
                      f"📅  Período     : {period_str}  ({period_detail})",
                      f"🛡️  Antichoque  : vid_id único por cuenta/día activo",
                      f"👥  Cuentas    : {len(plan)}", ""]

            for acc, day_lists in plan.items():
                total = sum(len(d) for d in day_lists)
                lines.append(f"📱  {acc}  →  {total} videos")
                for day_idx, day_vids in enumerate(day_lists):
                    lines.append(f"  Día {day_idx + 1}:")
                    for i, vid in enumerate(day_vids, 1):
                        lines.append(f"    {i:02d}. {item_display(vid)}  [{forge_vid_id(item_name(vid))}]")
                lines.append("")

            if not preview_only:
                entries = []
                affected = set()
                logical_names = set()
                total_copiados = 0
                for acc, day_lists in plan.items():
                    for day_idx, day_vids in enumerate(day_lists):
                        day_path = os.path.join(cal_root, f"Dia_{day_idx + 1}", acc)
                        for slot_idx, item in enumerate(day_vids, 1):
                            vid_name = item["name"]
                            item_tanda = item["tanda"]
                            src = os.path.abspath(os.path.join(folders[item_tanda], vid_name))
                            dst_name = build_calendar_video_filename(
                                vid_name,
                                item_tanda,
                                account_ids[acc],
                                day_idx + 1,
                                slot_idx,
                            )
                            dst = os.path.join(day_path, dst_name)
                            if dst_name in logical_names:
                                dst_name = build_calendar_video_filename(
                                    vid_name,
                                    item_tanda,
                                    account_ids[acc],
                                    day_idx + 1,
                                    slot_idx,
                                    collision_suffix=random.randint(1000, 9999),
                                )
                                dst = os.path.join(day_path, dst_name)
                            logical_names.add(dst_name)
                            entries.append(
                                build_entry(
                                    username=acc,
                                    account_id=account_ids[acc],
                                    delivery_kind="normal",
                                    day=day_idx + 1,
                                    slot=slot_idx,
                                    tanda=item_tanda,
                                    source_path=src,
                                    telegram_filename=dst_name,
                                    transform_log_id=self.db.get_video_transform_log_id(src),
                                    caption_mode=caption_mode_map.get(item_tanda, "general"),
                                )
                            )
                            affected.add(acc)
                            total_copiados += 1

                if affected:
                    replace_entries(
                        manifest_path(_BASE_DIR), entries, affected, "normal",
                        publication_target="instagram_reel",
                    )

                lines += ["=" * 60,
                          f"✅  Calendario actualizado: {manifest_path(_BASE_DIR)}",
                          f"📅  Días organizados       : Dia_1 → Dia_{days}",
                          f"📋  Cuentas                : {len(plan)}",
                          f"🧾  Rutas registradas      : {total_copiados}"]

            return "\n".join(lines)

        def done(success, result):
            self.acct_dist_result.configure(state="normal")
            self.acct_dist_result.delete("1.0", "end")
            self.acct_dist_result.insert("end", result if success else f"❌  Error:\n{result}")
            self.acct_dist_result.configure(state="disabled")
            if not preview_only and success:
                messagebox.showinfo("✅ Listo",
                                    "Distribución completada.\n"
                                    "Cargá el panel Telegram para ver los videos por cuenta.")
            elif not success:
                messagebox.showerror("Error en distribución", result)

        WorkerThread(self, done, task).start()

    def _build_calendar_frame(self):
        f = self._frames["Calendario"]
        f.grid_rowconfigure(2, weight=1)
        f.grid_columnconfigure(0, weight=1)
        PageHeader(f, "DISTRIBUCIÓN", "Calendario", "Agenda manual por cuenta y hora local.").grid(
            row=0, column=0, sticky="ew", padx=24, pady=(20, 10))

        filters = ctk.CTkFrame(f, fg_color="transparent")
        filters.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))
        ctk.CTkLabel(filters, text="Desde:", text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        self.calendar_start = ctk.CTkEntry(filters, width=125, fg_color=BG_INPUT, border_color=BORDER)
        self.calendar_start.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.calendar_start.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(filters, text="Días:", text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        self.calendar_days = ctk.CTkEntry(filters, width=65, fg_color=BG_INPUT, border_color=BORDER)
        self.calendar_days.insert(0, "30")
        self.calendar_days.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(filters, text="Cuenta:", text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        account_names = [row.get("username", "") for row in self.db.get_all_accounts() if row.get("username")]
        self.calendar_account = ctk.CTkComboBox(
            filters, values=["Todas", *sorted(account_names)], width=190,
            fg_color=BG_INPUT, border_color=BORDER,
        )
        self.calendar_account.set("Todas")
        self.calendar_account.pack(side="left", padx=(0, 12))
        GhostButton(filters, text="Actualizar", command=self._refresh_calendar_view).pack(side="left")
        GhostButton(filters, text="Sincronizar publicados", command=self._sync_calendar_published).pack(side="left", padx=(8, 0))

        content = ctk.CTkFrame(f, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 18))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        table_card = Card(content, title="Publicaciones calendarizadas")
        table_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        table = table_card.body
        table.grid_rowconfigure(0, weight=1)
        table.grid_columnconfigure(0, weight=1)
        columns = ("Fecha", "Hora", "Cuenta", "Destino", "Medio", "Estado")
        self.calendar_tree = ttk.Treeview(
            table, columns=columns, show="headings", style="Premium.Treeview", selectmode="browse"
        )
        widths = {"Fecha": 100, "Hora": 65, "Cuenta": 120, "Destino": 185, "Medio": 70, "Estado": 90}
        for column in columns:
            self.calendar_tree.heading(column, text=column)
            self.calendar_tree.column(column, width=widths[column], anchor="w" if column in {"Destino", "Cuenta"} else "center")
        self.calendar_tree.bind("<<TreeviewSelect>>", self._show_calendar_entry)
        tree_scroll = ttk.Scrollbar(table, orient="vertical", command=self.calendar_tree.yview)
        self.calendar_tree.configure(yscrollcommand=tree_scroll.set)
        self.calendar_tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        tree_scroll.grid(row=0, column=1, sticky="ns", pady=8, padx=(0, 6))

        detail_card = Card(content, title="Detalle y vista previa")
        detail_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        detail = detail_card.body
        detail.grid_rowconfigure(0, weight=1)
        detail.grid_columnconfigure(0, weight=1)
        self.calendar_detail = ctk.CTkTextbox(detail, height=210, fg_color=BG_CARD2, text_color=TEXT_BODY)
        self.calendar_detail.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 6))
        self.calendar_preview = ctk.CTkLabel(
            detail, text="Selecciona una publicación", text_color=TEXT_MUTED,
            fg_color=BG_CARD2, corner_radius=4, height=250,
        )
        self.calendar_preview.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.calendar_view_entries = {}

    def _refresh_calendar_view(self):
        if not hasattr(self, "calendar_tree"):
            return
        account_names = [row.get("username", "") for row in self.db.get_all_accounts() if row.get("username")]
        account_values = ["Todas", *sorted(account_names)]
        selected_account = self.calendar_account.get().strip()
        self.calendar_account.configure(values=account_values)
        if selected_account not in account_values:
            self.calendar_account.set("Todas")
        try:
            start = date.fromisoformat(self.calendar_start.get().strip())
            days = int(self.calendar_days.get().strip())
            if days < 1 or days > 366:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Calendario", "Usa una fecha YYYY-MM-DD y un rango de 1 a 366 días.", parent=self)
            return
        account_filter = self.calendar_account.get().strip()
        from calendar_manifest import load_entries, manifest_path, publication_target_for_entry
        from por_cuentas_lanes import resolve_legacy_reel_schedule

        manifest = manifest_path(_BASE_DIR)
        try:
            if manifest.exists():
                entries = load_entries(manifest, require_source=True)
            else:
                import organizadortg
                entries = [
                    {
                        **row,
                        "source_path": row.get("path", ""),
                        "day": str(row.get("day", "Dia_1")).replace("Dia_", ""),
                    }
                    for row in organizadortg.scan_calendar_structure()
                ]
        except (OSError, ValueError) as error:
            messagebox.showerror("Calendario", f"No se pudo leer el manifiesto: {error}", parent=self)
            return
        self.calendar_tree.delete(*self.calendar_tree.get_children())
        self.calendar_view_entries = {}
        end = start + timedelta(days=days - 1)
        rows = []
        schedule_resolution_cache = {}
        for entry in entries:
            username = entry.get("username", "")
            if account_filter != "Todas" and username != account_filter:
                continue
            resolved = dict(entry)
            if not (resolved.get("scheduled_date") and resolved.get("scheduled_time")):
                try:
                    schedule = resolve_legacy_reel_schedule(
                        resolved, start.isoformat(), self.db, schedule_resolution_cache
                    )
                    resolved.update(schedule)
                except ValueError:
                    pass
            scheduled_date = resolved.get("scheduled_date") or ""
            if scheduled_date:
                try:
                    local_date = date.fromisoformat(scheduled_date)
                except ValueError:
                    continue
                if local_date < start or local_date > end:
                    continue
                shown_date = local_date.isoformat()
            else:
                day_number = int(resolved.get("day") or 1)
                local_date = start + timedelta(days=max(0, day_number - 1))
                if local_date > end:
                    continue
                shown_date = f"Dia {day_number}"
            rows.append((
                local_date,
                resolved.get("scheduled_time") or "--:--",
                username,
                publication_target_for_entry(resolved),
                resolved.get("media_kind") or "video",
                resolved.get("manual_status") or "planned",
                resolved,
                shown_date,
            ))
        rows.sort(key=lambda row: (row[0], row[1], row[2], row[3], row[6].get("slot", 0)))
        for index, row in enumerate(rows):
            iid = str(index)
            self.calendar_view_entries[iid] = row[6]
            self.calendar_tree.insert("", "end", iid=iid, values=(row[7], row[1], "@" + row[2], row[3], row[4], row[5]))
        self.calendar_detail.configure(state="normal")
        self.calendar_detail.delete("1.0", "end")
        self.calendar_detail.insert("end", f"{len(rows)} publicaciones en el periodo")
        self.calendar_detail.configure(state="disabled")
        self.calendar_preview.configure(image=None, text="Selecciona una publicación")
        self.calendar_image_ref = None

    def _show_calendar_entry(self, _event=None):
        selection = self.calendar_tree.selection()
        if not selection:
            return
        entry = self.calendar_view_entries.get(selection[0])
        if not entry:
            return
        target = entry.get("publication_target") or "instagram_reel"
        details = [
            f"Cuenta: @{entry.get('username', '')}",
            f"Destino: {target}",
            f"Fecha: {entry.get('scheduled_date') or 'según día legacy'} {entry.get('scheduled_time') or ''} {entry.get('timezone') or ''}",
            f"Estado: {entry.get('manual_status') or 'planned'}",
            f"Archivo: {entry.get('source_path', '')}",
        ]
        if entry.get("caption"):
            details.extend(["", "Caption:", entry["caption"]])
        if entry.get("story_link_url"):
            details.extend(["", f"Enlace Story: {entry['story_link_url']}"])
        if entry.get("story_announcement_text"):
            details.extend(["", f"Texto Story: {entry['story_announcement_text']}"])
        for label, key in (("Título", "title"), ("Precio", "price"), ("Condición", "condition"), ("Descripción", "description")):
            value = (entry.get("platform_payload") or {}).get(key)
            if value:
                details.append(f"{label}: {value}")
        self.calendar_detail.configure(state="normal")
        self.calendar_detail.delete("1.0", "end")
        self.calendar_detail.insert("end", "\n".join(details))
        self.calendar_detail.configure(state="disabled")
        self.calendar_image_ref = None
        path = entry.get("source_path", "")
        if Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            try:
                from PIL import Image, ImageOps
                with Image.open(path) as source:
                    image = ImageOps.exif_transpose(source).convert("RGB")
                    image.thumbnail((460, 290), Image.Resampling.LANCZOS)
                    self.calendar_image_ref = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                self.calendar_preview.configure(image=self.calendar_image_ref, text="")
                return
            except Exception:
                pass
        self.calendar_preview.configure(image=None, text="Vista previa no disponible para este archivo")

    def _sync_calendar_published(self):
        entries = list(self.calendar_view_entries.values())
        manifest = manifest_path(_BASE_DIR)
        if not entries:
            return messagebox.showinfo("Calendario", "No hay publicaciones en el rango actual.", parent=self)

        def task():
            import organizadortg
            from airtable_sync import fetch_published_video_hashes, load_airtable_config
            from calendar_manifest import update_entries_status

            published = fetch_published_video_hashes(load_airtable_config())
            statuses = {}
            for entry in entries:
                entry_id = entry.get("id")
                path = entry.get("source_path") or entry.get("path")
                if not entry_id or not path or not Path(path).is_file():
                    continue
                content_hash = organizadortg._source_sha256(path)
                media_kind = entry.get("media_kind") or (
                    "video" if Path(path).suffix.lower() in {".mp4", ".mov", ".m4v"} else "image"
                )
                if media_kind == "video" and not entry.get("lane_id"):
                    publication_hash = content_hash
                else:
                    publication_hash = organizadortg._account_publication_hash(
                        entry.get("username", ""),
                        entry.get("publication_target") or "instagram_reel",
                        content_hash,
                        media_kind,
                    )
                if publication_hash in published:
                    statuses[str(entry_id)] = "published"
            updated = update_entries_status(manifest, statuses) if statuses else set()
            return len(updated)

        def done(success, result):
            if not success:
                messagebox.showerror("Sincronización", str(result), parent=self)
                return
            self._refresh_calendar_view()
            messagebox.showinfo("Sincronización", f"Marcadas como publicadas: {result}", parent=self)

        WorkerThread(self, done, task).start()

    def _build_tg_frame(self):
        """TAREA 6 — Bot Telegram."""
        f = self._frames["Telegram"]
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure((0, 1), weight=1)

        # ── Header ──────────────────────────────────────────────────────
        PageHeader(
            f, "DISTRIBUCIÓN", "Telegram",
            "Envío programado vía Telegram."
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 10))

        # ── Panel Izquierdo: Cuentas y Controles ────────────────────────
        ctrl_card = Card(f, title="Cuentas programadas")
        ctrl_card.grid(row=1, column=0, sticky="nsew", padx=(24, 12), pady=10)
        ctrl = ctrl_card.body
        ctrl.grid_rowconfigure(6, weight=1)
        ctrl.grid_columnconfigure(0, weight=1)

        # Fila 0: título + botón cargar
        hdr_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        hdr_row.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        hdr_row.grid_columnconfigure(0, weight=1)
        self.btn_load_tg = GhostButton(hdr_row, text="Cargar",
                                       command=self.load_organized_accounts)
        self.btn_load_tg.grid(row=0, column=1, sticky="e")

        # Fila 1: filtro + seleccionar todos/ninguno
        filter_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        filter_row.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        filter_row.grid_columnconfigure(0, weight=1)
        self._tg_only_with_videos = tk.BooleanVar(value=True)
        tg_filter_toggle = ToggleRow(
            filter_row, "Solo con publicaciones", variable=self._tg_only_with_videos
        )
        tg_filter_toggle.switch.configure(command=self.load_organized_accounts)
        tg_filter_toggle.grid(row=0, column=0, sticky="w")
        sel_frame = ctk.CTkFrame(filter_row, fg_color="transparent")
        sel_frame.grid(row=0, column=1, sticky="e")
        GhostButton(sel_frame, text="Todos", width=72,
                    command=lambda: self.list_tg.select_set(0, "end")).pack(side="left", padx=(0, 4))
        GhostButton(sel_frame, text="Ninguno", width=78,
                    command=lambda: self.list_tg.selection_clear(0, "end")).pack(side="left")

        # Fila 2: toggle "Configurar Horarios"
        self._schedule_panel_expanded = False
        sched_header = ctk.CTkFrame(ctrl, fg_color="transparent")
        sched_header.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        sched_header.grid_columnconfigure(0, weight=1)
        self.btn_toggle_sched = GhostButton(
            sched_header, text="▶ Configurar Horarios", anchor="w",
            command=self._toggle_schedule_panel,
        )
        self.btn_toggle_sched.grid(row=0, column=0, sticky="ew")
        topic_mode_row = ctk.CTkFrame(sched_header, fg_color="transparent")
        topic_mode_row.grid(row=0, column=1, sticky="e", padx=(10, 0))
        ctk.CTkLabel(topic_mode_row, text="Topics:", text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        self.tg_topic_mode = ctk.CTkComboBox(
            topic_mode_row,
            values=["Por identidad y fecha", "Separados por tipo"],
            width=190,
            fg_color=BG_INPUT,
            border_color=BORDER,
            command=self._save_tg_topic_mode,
        )
        saved_topic_mode = self.db.get_social_publishing_setting("telegram_topic_mode", "account_by_day")
        self.tg_topic_mode.set(
            "Separados por tipo" if saved_topic_mode == "separate_by_type" else "Por identidad y fecha"
        )
        self.tg_topic_mode.pack(side="left")

        # Fila 3: panel de horarios (oculto inicialmente)
        self.sched_panel = ctk.CTkScrollableFrame(ctrl, fg_color=BG_INPUT, height=160)
        # NO se ejecuta .grid() aquí — se invoca en _toggle_schedule_panel al expandir

        # Fila 4: modo express
        self._tg_express_mode = tk.BooleanVar(value=False)
        express_toggle = ToggleRow(
            ctrl,
            "Envío express",
            variable=self._tg_express_mode,
            fg_color=BG_CARD2,
        )
        express_toggle.grid(row=4, column=0, sticky="ew", pady=(8, 4))

        # Fila 5: reset opcional de topics
        self._tg_reset_topics = tk.BooleanVar(value=False)
        reset_topics_toggle = ToggleRow(
            ctrl,
            "Borrar topics existentes y recrear",
            variable=self._tg_reset_topics,
            fg_color=BG_CARD2,
        )
        reset_topics_toggle.grid(row=5, column=0, sticky="ew", pady=(4, 10))

        # Fila 5: listbox con selección múltiple
        self.list_tg = tk.Listbox(ctrl, bg=self.themed(BG_INPUT), fg=self.themed(TEXT_BODY),
                                  selectbackground=self.themed(ACCENT),
                                  selectforeground=self.themed(ACCENT_TEXT),
                                  selectmode=tk.EXTENDED,
                                  borderwidth=0, highlightthickness=1,
                                  highlightbackground=self.themed(BORDER), font=FONT_BODY)
        self.list_tg.grid(row=6, column=0, sticky="nsew", pady=(0, 10))

        # Controles inferiores
        bot_ctrl = ctk.CTkFrame(ctrl, fg_color="transparent")
        bot_ctrl.grid(row=7, column=0, sticky="ew", pady=(10, 20))
        
        ctk.CTkLabel(bot_ctrl, text="Fecha Inicio (YYYY-MM-DD):", text_color=TEXT_MUTED).pack(side="left")
        self.e_date_tg = ctk.CTkEntry(bot_ctrl, fg_color=BG_INPUT, border_color=BORDER, width=120)
        self.e_date_tg.pack(side="left", padx=10)
        self.e_date_tg.insert(0, datetime.now().strftime("%Y-%m-%d"))

        btn_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_row.grid(row=8, column=0, sticky="ew", pady=(0, 0))
        
        self.btn_start_tg = PrimaryButton(btn_row, text="▶ INICIAR", fg_color=TELEGRAM,
                                          text_color=TEXT_ON_DANGER, command=self.start_tg_bot)
        self.btn_start_tg.pack(side="left", expand=True, padx=(0, 5))
        
        self.btn_pause_tg = GhostButton(btn_row, text="⏸ PAUSAR",
                                          state="disabled", command=self.pause_tg_bot)
        self.btn_pause_tg.pack(side="left", expand=True, padx=5)
        
        self.btn_stop_tg = DangerButton(btn_row, text="⏹ DETENER",
                                         state="disabled", command=self.stop_tg_bot)
        self.btn_stop_tg.pack(side="left", expand=True, padx=(5, 0))

        cleanup_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        cleanup_row.grid(row=9, column=0, sticky="ew", pady=(8, 0))
        self.btn_delete_calendar_tg = DangerButton(
            cleanup_row,
            text="Borrar calendarizaciones",
            command=self.delete_selected_calendarizations,
        )
        self.btn_delete_calendar_tg.pack(side="left", fill="x", expand=True)

        # ── Panel Derecho: Live Log ─────────────────────────────────────
        log_card = Card(f, title="Registro de actividad")
        log_card.grid(row=1, column=1, sticky="nsew", padx=(12, 24), pady=10)
        log = log_card.body
        log.grid_rowconfigure(0, weight=1)
        log.grid_columnconfigure(0, weight=1)
        
        self.tg_log = ctk.CTkTextbox(log, fg_color=BG_INPUT, text_color=TEXT_BODY, font=FONT_MONO,
                                     border_width=1, border_color=BORDER)
        self.tg_log.grid(row=0, column=0, sticky="nsew")
        
        self.tg_log.tag_config("INFO", foreground=self.themed(INFO))
        self.tg_log.tag_config("SUCCESS", foreground=self.themed(SUCCESS))
        self.tg_log.tag_config("WARNING", foreground=self.themed(WARNING))
        self.tg_log.tag_config("ERROR", foreground=self.themed(DANGER))
        
        self.pb_tg = ctk.CTkProgressBar(log, fg_color=BG_INPUT, progress_color=NEON_CYAN)
        self.pb_tg.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.pb_tg.set(0)

    # ── Horarios: toggle / editor de grilla ─────────────────────────────────

    def _toggle_schedule_panel(self):
        """Expande o colapsa el panel de configuración de horarios."""
        self._schedule_panel_expanded = not self._schedule_panel_expanded
        if self._schedule_panel_expanded:
            self.btn_toggle_sched.configure(text="▼ Configurar Horarios")
            self.sched_panel.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 4))
            self._refresh_schedule_panel()
        else:
            self.btn_toggle_sched.configure(text="▶ Configurar Horarios")
            self.sched_panel.grid_forget()

    def _refresh_schedule_panel(self):
        """Reconstruye la grilla de sets × días con los slots actuales (o 'default')."""
        for w in self.sched_panel.winfo_children():
            w.destroy()

        vas = self.db.get_vas()
        cats = self.db.get_categories() or DEFAULT_CATEGORIES

        # Header
        header = ctk.CTkFrame(self.sched_panel, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(header, text="Set (VA / Categoría)", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11, weight="bold"), width=140,
                     anchor="w").pack(side="left", padx=(4, 4))
        for d in DAY_NAMES:
            ctk.CTkLabel(header, text=d, text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=11, weight="bold"), width=52).pack(side="left")
        ctk.CTkLabel(header, text="", width=120).pack(side="left")  # espacio botones

        # Filas por VA × categoría
        for va in vas:
            for cat in cats:
                self._render_set_row(va, cat)

    def _render_set_row(self, va_name: str, category: str):
        import json
        r = ctk.CTkFrame(self.sched_panel, fg_color=BG_CARD2, corner_radius=4)
        r.pack(fill="x", pady=2, padx=2)
        ctk.CTkLabel(r, text=f"{va_name} / {category}", text_color=TEXT_BODY,
                     font=ctk.CTkFont(size=11), width=140, anchor="w").pack(side="left", padx=(4, 4))

        for dow in range(7):
            row_data = self.db.get_schedule_config(va_name, category, dow)
            if row_data:
                slots = json.loads(row_data["time_slots"])
                txt = ",".join(s.replace(":00 ", "").replace(" AM", "a").replace(" PM", "p") for s in slots)
                color = TEXT_BODY
            else:
                txt = "def"
                color = TEXT_MUTED
            ctk.CTkLabel(r, text=txt, text_color=color,
                         font=ctk.CTkFont(size=10), width=52).pack(side="left")

        ctk.CTkButton(r, text="Editar", width=56, height=22, fg_color=NEON_PURPLE,
                      hover_color=self._darken(NEON_PURPLE), text_color=TEXT_H1,
                      command=lambda v=va_name, c=category: self._edit_set_schedule(v, c)
                      ).pack(side="left", padx=(2, 2))
        ctk.CTkButton(r, text="Default", width=56, height=22, fg_color=BG_INPUT,
                      hover_color=BORDER, text_color=TEXT_MUTED,
                      command=lambda v=va_name, c=category: self._reset_set_schedule(v, c)
                      ).pack(side="left", padx=(0, 4))

    def _edit_set_schedule(self, va_name: str, category: str):
        """Abre un popup para editar los 7 días del set."""
        import json
        from organizadortg import DEFAULT_SCHEDULE

        win = ctk.CTkToplevel(self)
        win.title(f"Horarios — {va_name} / {category}")
        self._fit_toplevel(win, 520, 420)
        win.grab_set()

        ctk.CTkLabel(win, text=f"⏰ {va_name} / {category}",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT_H1
                     ).pack(pady=(12, 4))
        ctk.CTkLabel(win, text="Horas separadas por coma. Formato: 8:00 AM, 1:00 PM, 7:00 PM",
                     text_color=TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(pady=(0, 8))

        entries = {}
        for dow in range(7):
            row_frame = ctk.CTkFrame(win, fg_color="transparent")
            row_frame.pack(fill="x", padx=20, pady=2)
            ctk.CTkLabel(row_frame, text=DAY_NAMES[dow], width=50, anchor="w",
                         text_color=TEXT_BODY).pack(side="left")
            cfg = self.db.get_schedule_config(va_name, category, dow)
            if cfg:
                current = ", ".join(json.loads(cfg["time_slots"]))
            else:
                current = ", ".join(DEFAULT_SCHEDULE[dow])
            e = ctk.CTkEntry(row_frame, fg_color=BG_INPUT, border_color=BORDER, width=400)
            e.insert(0, current)
            e.pack(side="left", padx=8)
            entries[dow] = e

        def save_all():
            for dow, entry in entries.items():
                raw = entry.get().strip()
                if not raw:
                    self.db.delete_schedule_config(va_name, category, dow)
                    continue
                slots = [s.strip() for s in raw.split(",") if s.strip()]
                self.db.set_schedule_config(va_name, category, dow, slots)
            win.destroy()
            self._refresh_schedule_panel()

        btn_row_w = ctk.CTkFrame(win, fg_color="transparent")
        btn_row_w.pack(pady=14)
        ctk.CTkButton(btn_row_w, text="💾 Guardar", fg_color=SUCCESS, text_color=BG_APP,
                      hover_color=self._darken(SUCCESS), command=save_all).pack(side="left", padx=6)
        ctk.CTkButton(btn_row_w, text="Cancelar", fg_color=BG_CARD2, text_color=TEXT_BODY,
                      hover_color=BORDER, command=win.destroy).pack(side="left", padx=6)

    def _reset_set_schedule(self, va_name: str, category: str):
        """Borra la config de los 7 días del set — vuelve al DEFAULT_SCHEDULE."""
        if not messagebox.askyesno(
            "Restaurar default",
            f"¿Restaurar horarios estratégicos ET para {va_name} / {category}?",
            parent=self,
        ):
            return
        for dow in range(7):
            self.db.delete_schedule_config(va_name, category, dow)
        self._refresh_schedule_panel()

    # ── Lógica Bot Telegram ──────────────────────────────────────────────────
    def _save_tg_topic_mode(self, selected):
        mode = "separate_by_type" if selected == "Separados por tipo" else "account_by_day"
        self.db.set_social_publishing_setting("telegram_topic_mode", mode)

    def load_organized_accounts(self):
        try:
            date_str = self.e_date_tg.get().strip()
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return messagebox.showwarning("⚠️", "Formato de fecha inválido. Usa YYYY-MM-DD.")

        only_with_publications = self._tg_only_with_videos.get() if self._tg_only_with_videos else False
        accounts = self.db.get_all_accounts()
        import organizadortg as telegram_bot
        for diagnostic_line in _telegram_runtime_diagnostics(self.db):
            self.bot_log(diagnostic_line, "INFO")

        enriched = []
        for acc in accounts:
            publication_counts = telegram_bot.count_account_calendar_publications(acc["username"])
            total = publication_counts["total"]
            if only_with_publications and total == 0:
                continue
            enriched.append({
                "username": acc["username"],
                "assigned_va": acc.get("assigned_va", "Sin Asignar"),
                "total_videos": total,
                "video_label": telegram_bot.format_account_calendar_publication_label(publication_counts),
                "account_type": acc.get("account_type", ""),
            })

        self._tg_accounts = enriched
        self.list_tg.delete(0, "end")
        for acc in enriched:
            tag = acc.get("account_type", "").upper() or "—"
            self.list_tg.insert("end", f"@{acc['username']}  [{tag}]  ({acc['assigned_va']})  {acc['video_label']}")
        self.list_tg.select_set(0, "end")  # seleccionar todas por defecto

        self.bot_log(f"Cargadas {len(enriched)} cuentas para {date_str}{'  (solo con publicaciones)' if only_with_publications else ''}.", "INFO")

    def bot_log(self, message: str, level="INFO"):
        """Escribe en la consola del bot (thread-safe)."""
        def update():
            self.tg_log.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n", level)
            self.tg_log.see("end")
        self.after(0, update)

    def _selected_tg_account_names(self) -> list[str]:
        selected_indices = list(self.list_tg.curselection())
        return [
            self._tg_accounts[i]['username']
            for i in selected_indices
            if i < len(self._tg_accounts)
        ]

    def delete_selected_calendarizations(self):
        if self.tg_controller and self.tg_controller.is_running:
            return messagebox.showwarning(
                "Bot en ejecucion",
                "Deten el bot de Telegram antes de borrar calendarizaciones.",
                parent=self,
            )

        selected_accounts = self._selected_tg_account_names()
        if not selected_accounts:
            return messagebox.showwarning(
                "Sin seleccion",
                "Selecciona al menos una cuenta para borrar sus calendarizaciones.",
                parent=self,
            )

        preview = "\n".join(f"@{name}" for name in selected_accounts[:12])
        if len(selected_accounts) > 12:
            preview += f"\n... y {len(selected_accounts) - 12} mas"
        if not messagebox.askyesno(
            "Borrar calendarizaciones",
            "Se eliminaran las carpetas CALENDARIO_POSTEO\\Dia_* de estas cuentas.\n"
            "No se borran cuentas, topics ni videos fuente.\n\n"
            f"{preview}\n\nContinuar?",
            parent=self,
        ):
            return

        import organizadortg as telegram_bot
        summary = telegram_bot.delete_calendarizations_for_accounts(selected_accounts)
        if summary["failed"]:
            detail = "\n".join(
                f"{failure['path']}: {failure['error']}"
                for failure in summary["failures"][:5]
            )
            messagebox.showerror(
                "Error al borrar",
                f"No se pudieron borrar {summary['failed']} carpeta(s).\n\n{detail}",
                parent=self,
            )
        else:
            messagebox.showinfo(
                "Calendarizaciones borradas",
                f"{summary['deleted_folders']} carpeta(s) eliminadas.\n"
                f"{summary['deleted_files']} archivo(s) calendarizados eliminados.",
                parent=self,
            )
        self.bot_log(
            "Borradas calendarizaciones: "
            f"{summary['deleted_folders']} carpetas, "
            f"{summary['deleted_files']} archivos, "
            f"{summary['failed']} fallos.",
            "WARNING" if summary["failed"] else "SUCCESS",
        )
        self.load_organized_accounts()

    def start_tg_bot(self):
        date_str = self.e_date_tg.get().strip()

        if self.tg_controller and self.tg_controller.is_paused:
            self.tg_controller.resume()
            self.btn_pause_tg.configure(state="normal")
            self.btn_start_tg.configure(state="disabled")
            self.bot_log("▶ Bot reanudado.", "SUCCESS")
            self.set_bot_status(True)
            return

        if self.tg_controller and self.tg_controller.is_running:
            return messagebox.showinfo("Info", "El bot ya está en ejecución.")

        selected_accounts = self._selected_tg_account_names()
        if not selected_accounts:
            return messagebox.showwarning("⚠️", "Selecciona al menos una cuenta en la lista antes de iniciar.")

        reset_topics_var = getattr(self, "_tg_reset_topics", None)
        reset_topics = bool(reset_topics_var.get()) if reset_topics_var is not None else False
        express_mode_var = getattr(self, "_tg_express_mode", None)
        express_mode = bool(express_mode_var.get()) if express_mode_var is not None else False
        topic_mode = "separate_by_type" if self.tg_topic_mode.get() == "Separados por tipo" else "account_by_day"
        if reset_topics:
            if not messagebox.askyesno(
                "Borrar topics existentes",
                "Esto intentara borrar los topics ya registrados en los grupos Telegram "
                "de las cuentas seleccionadas y luego recrearlos. Continuar?",
                parent=self,
            ):
                return

        self.bot_log(f"Cuentas seleccionadas ({len(selected_accounts)}): {', '.join('@' + u for u in selected_accounts)}", "INFO")

        import organizadortg as telegram_bot
        self.bot_log("📝 Captions: se resuelven por tanda desde Logística.", "INFO")
        if express_mode:
            self.bot_log("Envío express activado: se omite el mensaje de metadata.", "WARNING")
        if reset_topics:
            self.bot_log("🧹 Reset de topics activado: se borraran y recrearan antes del envio.", "WARNING")
        self.tg_controller = telegram_bot.TelegramBotController(
            date_str,
            selected_accounts,
            reset_topics=reset_topics,
            express_mode=express_mode,
            db_manager=self.db,
            topic_mode=topic_mode,
        )
        
        self.btn_start_tg.configure(state="disabled")
        self.btn_pause_tg.configure(state="normal")
        self.btn_stop_tg.configure(state="normal")
        
        self.bot_log("🚀 Iniciando Bot...", "INFO")
        self.set_bot_status(True)
        self.pb_tg.set(0)
        
        # Redirigir prints del bot al log UI
        def custom_print(*args, **kwargs):
            msg = " ".join(map(str, args))
            lvl = "INFO"
            msg_lower = msg.lower()
            if "no se pudo" in msg_lower or "unable to open" in msg_lower or "exception" in msg_lower:
                lvl = "ERROR"
            if "error" in msg.lower() or "falló" in msg.lower(): lvl = "ERROR"
            elif "éxito" in msg.lower() or "enviado" in msg.lower(): lvl = "SUCCESS"
            elif "esperando" in msg.lower(): lvl = "WARNING"
            self.bot_log(msg, lvl)
            
        import builtins
        self._original_print = builtins.print
        builtins.print = custom_print
        
        def worker():
            self.tg_controller.start()
            
        def done(success, result):
            builtins.print = self._original_print
            self.btn_start_tg.configure(state="normal")
            self.btn_pause_tg.configure(state="disabled")
            self.btn_stop_tg.configure(state="disabled")
            self.set_bot_status(False)
            self.pb_tg.set(1)

            for message, level in _telegram_done_logs(success, result):
                self.bot_log(message, level)
            return
            
            if success: self.bot_log("✅ Proceso completado exitosamente.", "SUCCESS")
            else: self.bot_log("❌ El bot se detuvo por un error o cancelación.", "ERROR")
            
        WorkerThread(self, done, worker).start()

    def pause_tg_bot(self):
        if self.tg_controller and self.tg_controller.is_running:
            self.tg_controller.pause()
            self.btn_pause_tg.configure(state="disabled")
            self.btn_start_tg.configure(state="normal")
            self.bot_log("⏸ Bot pausado por el usuario.", "WARNING")
            self.set_bot_status(False)

    def stop_tg_bot(self):
        if self.tg_controller and self.tg_controller.is_running:
            if messagebox.askyesno("Confirmar", "¿Estás seguro de detener el envío?"):
                self.tg_controller.stop()
                self.btn_pause_tg.configure(state="disabled")
                self.btn_stop_tg.configure(state="disabled")
                self.bot_log("⏹ Señal de detención enviada...", "ERROR")

    # ── Panel Estado de Cuentas ───────────────────────────────────────────────
    def _build_cuentas_frame(self):
        f = self._frames["Cuentas"]
        f.grid_rowconfigure(2, weight=1)
        f.grid_columnconfigure(0, weight=1)

        PageHeader(
            f, "DISTRIBUCIÓN", "Cuentas",
            "Gestiona las cuentas destino, sus marcas, VAs y categorías."
        ).grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))

        add_card = Card(f, title="Añadir cuentas destino")
        add_card.grid(row=1, column=0, sticky="ew", padx=24, pady=(14, 10))
        add_body = add_card.body
        add_body.grid_columnconfigure(0, weight=1)
        add_body.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(add_body, text="Una cuenta por línea", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        self.txt_accounts = ctk.CTkTextbox(add_body, fg_color=BG_INPUT, border_color=BORDER,
                                            border_width=1, height=74)
        self.txt_accounts.grid(row=1, column=0, rowspan=3, sticky="nsew", padx=(0, 16), pady=(4, 0))

        ctk.CTkLabel(add_body, text="Categoría", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=1, sticky="w")
        self.c_bulk_cat = ctk.CTkComboBox(add_body, values=[], fg_color=BG_INPUT,
                                           border_color=BORDER)
        self.c_bulk_cat.grid(row=1, column=1, sticky="ew", pady=(4, 8))
        ctk.CTkLabel(add_body, text="VA asignado", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=2, column=1, sticky="w")
        self.c_bulk_va = ctk.CTkComboBox(add_body, values=[], fg_color=BG_INPUT,
                                          border_color=BORDER)
        self.c_bulk_va.grid(row=3, column=1, sticky="ew", pady=(4, 10))
        PrimaryButton(add_body, text="Añadir cuentas",
                      command=self.add_bulk_accounts).grid(row=4, column=1, sticky="e")

        accounts_card = Card(f, title="Cuentas destino")
        accounts_card.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 20))
        accounts_body = accounts_card.body
        accounts_body.grid_rowconfigure(2, weight=1)
        accounts_body.grid_columnconfigure(0, weight=1)

        accounts_header = ctk.CTkFrame(accounts_body, fg_color="transparent")
        accounts_header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        accounts_header.grid_columnconfigure(0, weight=1)
        self._acc_header_lbl = ctk.CTkLabel(
            accounts_header, text="0 cuentas", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_BODY,
        )
        self._acc_header_lbl.grid(row=0, column=0, sticky="w")
        self.btn_airtable_config = GhostButton(
            accounts_header, text="Conectar y preparar Airtable", width=205,
            command=self.configure_airtable,
        )
        self.btn_airtable_config.grid(row=0, column=1, padx=(0, 8), sticky="e")
        self.btn_airtable_sync = PrimaryButton(
            accounts_header, text="Sincronizar Airtable", width=155,
            command=self.sync_airtable_accounts,
        )
        self.btn_airtable_sync.grid(row=0, column=2, padx=(0, 8), sticky="e")
        self.btn_airtable_mirror = GhostButton(
            accounts_header, text="Sincronizar GUI → Airtable", width=205,
            command=self.sync_gui_to_airtable,
        )
        self.btn_airtable_mirror.grid(row=0, column=3, padx=(0, 8), sticky="e")
        GhostButton(accounts_header, text="Actualizar", width=110,
                    command=self._admin_load_accounts).grid(row=0, column=4, sticky="e")

        columns = ctk.CTkFrame(accounts_body, fg_color=BG_CARD2, corner_radius=BTN_RADIUS)
        columns.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        columns.grid_columnconfigure(0, weight=1)
        for index, (title, width) in enumerate([
            ("Cuenta", 0), ("Etiqueta", 105), ("Seguidores", 78), ("Estado", 98),
            ("Categoría", 120), ("VA", 150), ("Notas", 150), ("Limitaciones", 108), ("", 28),
        ]):
            ctk.CTkLabel(columns, text=title, text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=10, weight="bold"), width=width,
                         anchor="w" if index == 0 else "center").grid(
                             row=0, column=index, padx=(12, 4) if index == 0 else (2, 2), pady=6,
                             sticky="ew" if index == 0 else "")

        self._acc_scroll = ctk.CTkScrollableFrame(accounts_body, fg_color="transparent", height=380)
        self._acc_scroll.grid(row=2, column=0, sticky="nsew")
        self._acc_scroll.grid_columnconfigure(0, weight=1)
        self._admin_refresh()

    def configure_airtable(self):
        """Prepara una tabla existente y guarda la configuración local al terminar."""
        try:
            current = load_airtable_config()
        except AirtableSyncError:
            current = AirtableConfig("", "", "Cuentas")

        token = simpledialog.askstring(
            "Airtable", "Personal Access Token (lectura y edición de columnas):",
            initialvalue=current.personal_access_token, show="*", parent=self,
        )
        if token is None:
            return
        base_id = simpledialog.askstring(
            "Airtable", "Base ID (empieza por app):",
            initialvalue=current.base_id, parent=self,
        )
        if base_id is None:
            return
        table_name = simpledialog.askstring(
            "Airtable", "Nombre exacto de la tabla:",
            initialvalue=current.table_name, parent=self,
        )
        if table_name is None:
            return
        config = AirtableConfig(token, base_id, table_name)
        self.btn_airtable_config.configure(state="disabled", text="Conectando...")

        def task():
            return prepare_airtable_account_table(config)

        def done(success, result):
            self.btn_airtable_config.configure(
                state="normal", text="Conectar y preparar Airtable"
            )
            if not success:
                messagebox.showerror("Airtable", result, parent=self)
                return
            try:
                save_airtable_config(config)
            except AirtableSyncError as exc:
                messagebox.showerror("Airtable", str(exc), parent=self)
                return
            messagebox.showinfo(
                "Airtable", airtable_schema_preparation_text(result), parent=self
            )

        WorkerThread(self, done, task).start()

    def sync_airtable_accounts(self):
        """Descarga Airtable y pide confirmación antes de modificar SQLite local."""
        self.btn_airtable_sync.configure(state="disabled", text="Sincronizando...")

        def task():
            config = load_airtable_config()
            remote_rows = fetch_airtable_accounts(config)
            return build_account_sync_plan(remote_rows, self.db.get_all_accounts())

        def done(success, result):
            self.btn_airtable_sync.configure(state="normal", text="Sincronizar Airtable")
            if not success:
                messagebox.showerror("Airtable", result, parent=self)
                return
            plan = result
            if not plan.changed:
                messagebox.showinfo("Airtable", "No hay cambios desde Airtable.", parent=self)
                return
            if not messagebox.askyesno(
                "Revisar sincronización", airtable_sync_review_text(plan), parent=self,
            ):
                return
            try:
                counts = self.db.apply_airtable_account_plan(plan)
            except Exception:
                messagebox.showerror(
                    "Airtable",
                    "No se pudo aplicar la sincronización local. Cierra otras GUIs y vuelve a intentarlo.",
                    parent=self,
                )
                return
            self.refresh_dashboard()
            self._admin_load_accounts()
            if hasattr(self, "reload_dist_lists"):
                self.reload_dist_lists()
            messagebox.showinfo(
                "Airtable",
                "Sincronización completada: "
                f"{counts['created']} creadas, {counts['updated']} actualizadas, "
                f"{counts['deleted']} eliminadas.",
                parent=self,
            )

        WorkerThread(self, done, task).start()

    def sync_gui_to_airtable(self):
        """Previsualiza y aplica un espejo completo de las cuentas locales a Airtable."""
        self.btn_airtable_mirror.configure(state="disabled", text="Comparando...")

        def task():
            config = load_airtable_config()
            records = fetch_airtable_records(config)
            plan = build_airtable_mirror_plan(self.db.get_all_accounts(), records)
            return config, plan

        def done(success, result):
            if not success:
                self.btn_airtable_mirror.configure(state="normal", text="Sincronizar GUI → Airtable")
                messagebox.showerror("Airtable", result, parent=self)
                return
            config, plan = result
            if not plan.changed:
                self.btn_airtable_mirror.configure(state="normal", text="Sincronizar GUI → Airtable")
                messagebox.showinfo("Airtable", "Airtable ya coincide con la GUI.", parent=self)
                return
            if not messagebox.askyesno(
                "Confirmar espejo GUI → Airtable",
                airtable_mirror_review_text(plan),
                parent=self,
            ):
                self.btn_airtable_mirror.configure(state="normal", text="Sincronizar GUI → Airtable")
                return
            self.btn_airtable_mirror.configure(text="Aplicando...")

            def apply_task():
                return apply_airtable_mirror_plan(config, plan)

            def apply_done(applied, counts):
                self.btn_airtable_mirror.configure(state="normal", text="Sincronizar GUI → Airtable")
                if not applied:
                    messagebox.showerror("Airtable", counts, parent=self)
                    return
                messagebox.showinfo(
                    "Airtable",
                    "Espejo completado: "
                    f"{counts['created']} creadas, {counts['updated']} actualizadas, "
                    f"{counts['deleted']} eliminadas.",
                    parent=self,
                )

            WorkerThread(self, apply_done, apply_task).start()

        WorkerThread(self, done, task).start()

    def _build_verify_legacy_frame(self):
        """Aísla el verificador HTTP heredado de la gestión operativa de cuentas."""
        f = self._frames["VerifyLegacy"]
        f.grid_rowconfigure(0, weight=1)
        f.grid_columnconfigure(0, weight=1)
        self._verify_legacy_panel = AccountStatusPanel(f, self.db)
        self._verify_legacy_panel.grid(row=0, column=0, sticky="nsew")

    # ── AI Advisor (Gemini Integration) ──────────────────────────────────────
    def _build_ai_frame(self):
        """TAREA 7 — AI Advisor con Gemini."""
        f = self._frames["AIAdvisor"]
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure(0, weight=1)

        # ── Header ──────────────────────────────────────────────────────
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="🤖  AI Strategy Advisor",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TEXT_H1).grid(row=0, column=0, sticky="w")
        
        # ── Área Central ────────────────────────────────────────────────
        center = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        center.grid(row=1, column=0, sticky="nsew", padx=24, pady=(10, 24))
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)

        ctrl_bar = ctk.CTkFrame(center, fg_color="transparent")
        ctrl_bar.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        
        ctk.CTkLabel(ctrl_bar, text="Analizar Base de Datos y Sugerir Distribución",
                     text_color=TEXT_MUTED, font=ctk.CTkFont(size=14)).pack(side="left")
        
        self.btn_ai = ctk.CTkButton(ctrl_bar, text="✨ EJECUTAR ANÁLISIS", fg_color=NEON_PURPLE,
                                    hover_color=self._darken(NEON_PURPLE), height=BTN_H_LG,
                                    font=ctk.CTkFont(weight="bold"), command=self.run_ai_analysis)
        self.btn_ai.pack(side="right")

        self.ai_textbox = ctk.CTkTextbox(center, fg_color=BG_INPUT, text_color=NEON_CYAN,
                                         font=ctk.CTkFont(family="Consolas", size=13),
                                         border_width=1, border_color=BORDER)
        self.ai_textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.ai_textbox.insert("end", "Presiona 'Ejecutar Análisis' para que Gemini evalúe tu inventario y distribución de VAs.\n\n")
        self.ai_textbox.configure(state="disabled")

    def run_ai_analysis(self):
        self.btn_ai.configure(state="disabled", text="⏳ ANALIZANDO...")
        self.ai_textbox.configure(state="normal")
        self.ai_textbox.insert("end", "🤖 Conectando con Gemini...\n")
        self.ai_textbox.configure(state="disabled")

        def task():
            accounts = self.db.get_all_accounts()
            tandas = self.db.get_all_tandas()
            
            va_count = {}
            total_videos = 0
            for a in accounts:
                va = a.get("assigned_va", "Sin Asignar")
                va_count[va] = va_count.get(va, 0) + 1
                total_videos += a.get("videos_posted", 0)

            stats = {
                "total_accounts": len(accounts),
                "total_videos_sent": total_videos,
                "tandas_active": len(tandas),
                "va_distribution": va_count,
            }
            
            SYSTEM_PROMPT = "Eres un Asistente Experto en Automatización de Redes Sociales para Instagram.\nAnaliza estos datos de un sistema local de distribución (Método IG VIDEOS) y da recomendaciones concretas. Sé directo (max 200 palabras). Da 3 recomendaciones numeradas sobre cómo asignar cuotas a los VAs o advertencias de escasez de tandas."
            
            import google.generativeai as genai
            try:
                # El modelo está instanciado según lo configurado globalmente (API KEY)
                model = genai.GenerativeModel("gemini-2.5-flash")
                response = model.generate_content(SYSTEM_PROMPT + "\n\nDatos:\n" + str(stats))
                return response.text
            except Exception as e:
                # Fallback al modelo genérico en caso de que 2.5 falle o no esté soportado
                try:
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(SYSTEM_PROMPT + "\n\nDatos:\n" + str(stats))
                    return response.text
                except Exception as inner_e:
                    return f"Error conectando a Gemini: {str(inner_e)}\n\n(Verifica que GOOGLE_API_KEY esté configurada en tu entorno)."

        def done(success, result):
            self.btn_ai.configure(state="normal", text="✨ EJECUTAR ANÁLISIS")
            self.ai_textbox.configure(state="normal")
            if success:
                self.ai_textbox.delete("1.0", "end")
                self.ai_textbox.insert("end", "✅ ANÁLISIS COMPLETADO:\n\n")
                self.ai_textbox.insert("end", result)
            else:
                self.ai_textbox.insert("end", f"\n❌ ERROR: {result}")
            self.ai_textbox.configure(state="disabled")

        WorkerThread(self, done, task).start()


    # ══════════════════════════════════════════════════════════════════════
    # EDICIÓN DE VIDEO: FOTOS SOBRE FRAMES
    def _build_video_editor_frame(self):
        self.editor_rows = []
        f = self._frames["VideoEditor"]
        f.grid_rowconfigure(0, weight=1)
        f.grid_columnconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(f, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        PageHeader(scroll, kicker="CONTENIDO", title="Edición de video",
                   description="Colocá una o varias fotos durante milisegundos en frames específicos",
                   action=("Preview", self.editor_preview)).grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))

        source = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        source.grid(row=1, column=0, sticky="ew", padx=24, pady=14)
        source.grid_columnconfigure(1, weight=1)
        self.editor_video_paths = []
        self.editor_video_info = {}
        self.editor_timeline_map = {}
        self.editor_timeline_info = None
        ctk.CTkLabel(source, text="Videos base", text_color=NEON_CYAN,
                     font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=18, pady=16, sticky="w")
        self.editor_video = ctk.CTkEntry(source, fg_color=BG_INPUT, border_color=BORDER,
                                         placeholder_text="Elegí un MP4 o MOV")
        self.editor_video.grid(row=0, column=1, padx=8, pady=16, sticky="ew")
        PrimaryButton(source, text="Elegir videos", command=self.editor_choose_video).grid(row=0, column=2, padx=18, pady=16)
        self.editor_info = ctk.CTkLabel(source, text="Sin videos seleccionados", text_color=TEXT_MUTED)
        self.editor_info.grid(row=1, column=0, columnspan=3, padx=18, pady=(0, 14), sticky="w")

        timeline = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        timeline.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 14))
        timeline.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(timeline, text="Timeline y frame", text_color=NEON_CYAN,
                     font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=18, pady=(14, 8), sticky="w")
        self.editor_timeline_video = ctk.CTkComboBox(timeline, values=["Elegí videos primero"],
                                                      state="readonly", command=self.editor_timeline_video_changed,
                                                      fg_color=BG_INPUT, border_color=BORDER)
        self.editor_timeline_video.grid(row=0, column=1, padx=8, pady=(14, 8), sticky="ew")
        self.editor_timeline_time = ctk.CTkLabel(timeline, text="Elegí un video para usar el timeline", text_color=TEXT_MUTED)
        self.editor_timeline_time.grid(row=1, column=0, columnspan=2, padx=18, pady=(0, 4), sticky="w")
        self.editor_timeline_slider = ctk.CTkSlider(timeline, from_=0, to=1, number_of_steps=1,
                                                     command=self.editor_timeline_changed,
                                                     fg_color=BG_INPUT, progress_color=ACCENT, button_color=NEON_CYAN)
        self.editor_timeline_slider.grid(row=2, column=0, columnspan=2, padx=18, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(timeline, text="Aplicar este frame a:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=3, column=0, padx=18, pady=(0, 14), sticky="w")
        controls = ctk.CTkFrame(timeline, fg_color="transparent")
        controls.grid(row=3, column=1, padx=(8, 18), pady=(0, 14), sticky="e")
        self.editor_timeline_target = ctk.CTkComboBox(controls, values=["Foto 1"], state="readonly",
                                                       command=self.editor_timeline_target_changed,
                                                       fg_color=BG_INPUT, border_color=BORDER, width=120)
        self.editor_timeline_target.set("Foto 1")
        self.editor_timeline_target.pack(side="left", padx=(0, 8))
        GhostButton(controls, text="Usar frame", command=self.editor_apply_timeline_frame).pack(side="left", padx=(0, 8))
        PrimaryButton(controls, text="Ver frame", command=self.editor_preview_timeline).pack(side="left")

        self.editor_rows_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        self.editor_rows_frame.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 14))
        self.editor_rows_frame.grid_columnconfigure(0, weight=1)
        hdr = ctk.CTkFrame(self.editor_rows_frame, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 4))
        ctk.CTkLabel(hdr, text="Fotos y ubicación", text_color=NEON_PURPLE,
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        GhostButton(hdr, text="＋ Agregar foto", command=self.editor_add_row).pack(side="right")
        self.editor_global_enabled = tk.BooleanVar(value=True)
        global_config = ctk.CTkFrame(self.editor_rows_frame, fg_color=BG_CARD2, corner_radius=8)
        global_config.grid(row=1, column=0, sticky="ew", padx=18, pady=(4, 6))
        self._build_editor_global_config(global_config)
        self.editor_add_row()

        actions = ctk.CTkFrame(scroll, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 14))
        PrimaryButton(actions, text="👁️  Preview en frame aleatorio", command=self.editor_preview).pack(side="left", padx=(0, 8))
        self.btn_editor_render = PrimaryButton(
            actions, text="Renderizar video", command=self.editor_render)
        self.btn_editor_render.pack(side="right")
        self._build_render_performance_control(actions, "Edición").pack(side="right", padx=(0, 8))
        self.editor_status = ctk.CTkLabel(actions, text="Configurá el video y las fotos.", text_color=TEXT_MUTED)
        self.editor_status.pack(side="left", padx=16)

        preview = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        preview.grid(row=5, column=0, sticky="nsew", padx=24, pady=(0, 24))
        ctk.CTkLabel(preview, text="Vista previa del frame aleatorio", text_color=TEXT_BODY,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(14, 4))
        self.editor_preview_label = ctk.CTkLabel(preview, text="El preview aparecerá acá", text_color=TEXT_MUTED,
                                                 width=720, height=360)
        self.editor_preview_label.pack(padx=18, pady=(0, 14))

    def editor_choose_video(self):
        paths = filedialog.askopenfilenames(title="Videos base", filetypes=[("Videos", "*.mp4 *.mov *.mkv *.avi"), ("Todos", "*.*")])
        if not paths:
            return
        self.editor_video_paths = list(paths)
        self.editor_video_info = {}
        self.editor_video.delete(0, "end")
        self.editor_video.insert(0, paths[0] if len(paths) == 1 else f"{len(paths)} videos seleccionados")
        path = paths[0]
        choices = [f"{index + 1}. {os.path.basename(video)}" for index, video in enumerate(paths)]
        self.editor_timeline_map = dict(zip(choices, paths))
        self.editor_timeline_video.configure(values=choices)
        self.editor_timeline_video.set(choices[0])
        try:
            import video_editor
            info = video_editor.probe_video(path)
            self.editor_video_info[path] = info
            self._editor_load_timeline(path)
            self.editor_info.configure(text=f"{info['width']}×{info['height']} · {info['fps']:.2f} FPS · {info['duration']:.1f} s")
        except Exception as exc:
            self.editor_info.configure(text=f"No se pudo leer el video: {exc}", text_color=DANGER)

    def _editor_photo_video_batch_enabled(self):
        selected_photos = sum(bool(item["photo"].get().strip()) for item in self.editor_rows)
        return len(self.editor_video_paths) > 1 and selected_photos > 1

    def _editor_update_timeline_range(self, reset=False):
        info = self.editor_timeline_info
        if not info:
            return
        limit_seconds = min(5.0, info["duration"]) if self._editor_photo_video_batch_enabled() else info["duration"]
        max_frame = max(0, round(limit_seconds * info["fps"]) - 1)
        current_frame = 0 if reset else min(round(float(self.editor_timeline_slider.get())), max_frame)
        self.editor_timeline_slider.configure(from_=0, to=max(1, max_frame), number_of_steps=max(1, max_frame))
        self.editor_timeline_slider.set(current_frame)
        self.editor_timeline_changed(current_frame)

    def _editor_cartesian_batch(self, videos, overlays):
        return len(videos) * len(overlays) > 1

    def _editor_load_timeline(self, path):
        try:
            import video_editor
            info = self.editor_video_info.get(path) or video_editor.probe_video(path)
            self.editor_video_info[path] = info
            self.editor_timeline_info = info
            self._editor_update_timeline_range(reset=True)
        except Exception as exc:
            self.editor_timeline_info = None
            self.editor_timeline_time.configure(text=f"No se pudo preparar el timeline: {exc}", text_color=DANGER)

    def editor_timeline_video_changed(self, choice):
        path = self.editor_timeline_map.get(choice)
        if path:
            self._editor_load_timeline(path)

    def editor_timeline_changed(self, value):
        info = self.editor_timeline_info
        if not info:
            return
        frame = max(0, round(float(value)))
        seconds = frame / info["fps"]
        minutes, remainder = divmod(seconds, 60)
        batch_note = "  ·  Lote: primeros 5 s" if self._editor_photo_video_batch_enabled() else ""
        self.editor_timeline_time.configure(
            text=f"Frame {frame}  ·  {int(minutes):02d}:{remainder:06.3f}  ·  {info['fps']:.2f} FPS{batch_note}",
            text_color=TEXT_BODY,
        )

    def _editor_timeline_item(self):
        try:
            index = int(self.editor_timeline_target.get().split()[1]) - 1
            return self.editor_rows[index]
        except (IndexError, ValueError, AttributeError):
            return None

    def _editor_refresh_timeline_targets(self):
        if not hasattr(self, "editor_timeline_target"):
            return
        choices = [f"Foto {index}" for index in range(1, len(self.editor_rows) + 1)] or ["Foto 1"]
        current = self.editor_timeline_target.get()
        self.editor_timeline_target.configure(values=choices)
        self.editor_timeline_target.set(current if current in choices else choices[0])

    def _editor_reindex_rows(self):
        for index, item in enumerate(self.editor_rows, start=1):
            item["frame"].grid(row=index + 1, column=0, sticky="ew", padx=18, pady=6)
            item["label"].configure(text=f"Foto {index}")

    def editor_timeline_target_changed(self, _choice):
        item = self._editor_timeline_item()
        if (not item or self._editor_photo_video_batch_enabled()
                or (self.editor_global_enabled.get() and not item["manual_var"].get())):
            return
        if not self.editor_timeline_info:
            return
        try:
            frame = max(0, float(item["Frame"].get()))
            self.editor_timeline_slider.set(frame)
            self.editor_timeline_changed(frame)
        except ValueError:
            pass

    def editor_apply_timeline_frame(self):
        item = self._editor_timeline_item()
        if not item or not self.editor_timeline_info:
            return messagebox.showwarning("Timeline", "Elegí un video y una foto antes de aplicar el frame.")
        frame = str(round(float(self.editor_timeline_slider.get())))
        apply_to_all = (self._editor_photo_video_batch_enabled()
                        or (self.editor_global_enabled.get() and not item["manual_var"].get()))
        targets = self.editor_rows if apply_to_all else [item]
        for target in targets:
            target["Frame"].delete(0, "end")
            target["Frame"].insert(0, frame)
        if apply_to_all:
            self.editor_status.configure(text=f"Frame {frame} asignado a todas las fotos del lote.", text_color=SUCCESS)
            return
        self.editor_status.configure(text=f"Frame {frame} asignado a {self.editor_timeline_target.get()}.", text_color=SUCCESS)

    def editor_preview_timeline(self):
        try:
            videos, overlays = self._editor_collect()
        except Exception as exc:
            return messagebox.showwarning("Preview", str(exc))
        if self._editor_cartesian_batch(videos, overlays):
            try:
                photo_index = int(self.editor_timeline_target.get().split()[1]) - 1
                overlays = [overlays[photo_index]]
            except (IndexError, ValueError, AttributeError):
                pass
        video = self.editor_timeline_map.get(self.editor_timeline_video.get(), videos[0])
        info = self.editor_timeline_info or self.editor_video_info.get(video)
        if not info:
            return messagebox.showwarning("Timeline", "Elegí un video válido para el timeline.")
        timestamp = round(float(self.editor_timeline_slider.get())) / info["fps"]
        overlays = self._editor_overlays_for_source(video, overlays)
        self.editor_status.configure(text="Generando preview del frame elegido…", text_color=WARNING)

        def task():
            import video_editor
            return video_editor.render_preview(video, overlays, timestamp=timestamp)

        def done(success, result):
            if not success:
                self.editor_status.configure(text="Error de preview", text_color=DANGER)
                return messagebox.showerror("Preview", result)
            path, actual_time = result
            from PIL import Image
            image = Image.open(path).convert("RGB")
            image.thumbnail((760, 420), Image.Resampling.LANCZOS)
            self.editor_preview_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
            self.editor_preview_label.configure(image=self.editor_preview_image, text="")
            self.editor_status.configure(text=f"Preview del timeline en {actual_time:.3f} s.", text_color=SUCCESS)

        WorkerThread(self, done, task).start()

    def _build_editor_global_config(self, container):
        container.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        ctk.CTkLabel(header, text="Configuración global de fotos", text_color=NEON_CYAN,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.editor_global_switch = ctk.CTkSwitch(
            header, text="Aplicar a todas", variable=self.editor_global_enabled,
            command=self._editor_refresh_config_modes, progress_color=ACCENT, button_color=NEON_CYAN,
        )
        self.editor_global_switch.pack(side="right")
        ctk.CTkLabel(container, text="El frame se toma del timeline. Activá “Editar individual” solo para excepciones.",
                     text_color=TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=1, column=0, sticky="w", padx=12)

        fields = ctk.CTkFrame(container, fg_color="transparent")
        fields.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 2))
        specs = [("Duración ms", "500"), ("Tamaño %", "25"), ("X %", "50"),
                 ("Y %", "50"), ("Transparencia %", "100")]
        self.editor_global_entries = {}
        for column, (label, default) in enumerate(specs):
            ctk.CTkLabel(fields, text=label, text_color=TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=0, column=column, padx=3)
            entry = ctk.CTkEntry(fields, width=88, fg_color=BG_INPUT, border_color=BORDER)
            entry.insert(0, default)
            entry.grid(row=1, column=column, padx=3)
            self.editor_global_entries[label] = entry
        self.editor_global_ratio = ctk.CTkComboBox(fields, values=["Original", "9:16", "1:1", "4:5", "16:9", "6:19"],
                                                   width=100, fg_color=BG_INPUT, border_color=BORDER)
        self.editor_global_ratio.set("9:16")
        self.editor_global_ratio.grid(row=1, column=5, padx=3)
        ctk.CTkLabel(fields, text="Relación", text_color=TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=0, column=5, padx=3)
        self.editor_global_position = ctk.CTkComboBox(
            fields, values=["Manual X/Y", "Centro", "Arriba izquierda", "Arriba centro", "Arriba derecha",
                            "Abajo izquierda", "Abajo centro", "Abajo derecha"], width=130,
            fg_color=BG_INPUT, border_color=BORDER,
        )
        self.editor_global_position.set("Manual X/Y")
        self.editor_global_position.grid(row=1, column=6, padx=3)
        ctk.CTkLabel(fields, text="Posición", text_color=TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=0, column=6, padx=3)

        move = ctk.CTkFrame(container, fg_color="transparent")
        move.grid(row=3, column=0, sticky="ew", padx=12, pady=(2, 10))
        move.grid_columnconfigure(1, weight=1)
        move.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(move, text="Mover X", text_color=TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=0, column=0, padx=(0, 5))
        global_x_value = ctk.CTkLabel(move, text="50%", text_color=TEXT_BODY, font=ctk.CTkFont(size=10), width=35)
        global_x_value.grid(row=0, column=2, padx=(5, 14))
        self.editor_global_x_slider = ctk.CTkSlider(
            move, from_=0, to=100, number_of_steps=100, fg_color=BG_INPUT, progress_color=ACCENT, button_color=NEON_CYAN,
            command=lambda value: self._editor_position_slider_changed(self.editor_global_entries["X %"], global_x_value, value),
        )
        self.editor_global_x_slider.set(50)
        self.editor_global_x_slider.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(move, text="Mover Y", text_color=TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=0, column=3, padx=(0, 5))
        global_y_value = ctk.CTkLabel(move, text="50%", text_color=TEXT_BODY, font=ctk.CTkFont(size=10), width=35)
        global_y_value.grid(row=0, column=5, padx=(5, 0))
        self.editor_global_y_slider = ctk.CTkSlider(
            move, from_=0, to=100, number_of_steps=100, fg_color=BG_INPUT, progress_color=ACCENT, button_color=NEON_CYAN,
            command=lambda value: self._editor_position_slider_changed(self.editor_global_entries["Y %"], global_y_value, value),
        )
        self.editor_global_y_slider.set(50)
        self.editor_global_y_slider.grid(row=0, column=4, sticky="ew")
        self.editor_global_controls = [*self.editor_global_entries.values(), self.editor_global_ratio,
                                       self.editor_global_position, self.editor_global_x_slider, self.editor_global_y_slider]

    def _editor_refresh_config_modes(self):
        global_enabled = self.editor_global_enabled.get()
        for control in getattr(self, "editor_global_controls", []):
            control.configure(state="normal" if global_enabled else "disabled")
        for item in self.editor_rows:
            individual = item["manual_var"].get() or not global_enabled
            for control in item["config_controls"]:
                control.configure(state="normal" if individual else "disabled")

    def _editor_position_slider_changed(self, entry, label, value):
        percentage = max(0, min(100, round(float(value))))
        entry.delete(0, "end")
        entry.insert(0, str(percentage))
        label.configure(text=f"{percentage}%")

    def editor_add_row(self):
        row = ctk.CTkFrame(self.editor_rows_frame, fg_color=BG_CARD2, corner_radius=8)
        row.grid(row=len(self.editor_rows) + 2, column=0, sticky="ew", padx=18, pady=6)
        row.grid_columnconfigure(1, weight=1)
        idx = len(self.editor_rows) + 1
        photo_label = ctk.CTkLabel(row, text=f"Foto {idx}", text_color=NEON_CYAN,
                                   font=ctk.CTkFont(size=12, weight="bold"), width=60)
        photo_label.grid(row=0, column=0, rowspan=2, padx=12, pady=10)
        photo = ctk.CTkEntry(row, fg_color=BG_INPUT, border_color=BORDER, placeholder_text="Archivo de imagen")
        photo.grid(row=0, column=1, padx=6, pady=(10, 4), sticky="ew")
        ctk.CTkButton(row, text="Elegir fotos", width=90, command=lambda e=photo: self.editor_choose_photo(e)).grid(row=0, column=2, padx=6, pady=(10, 4))
        manual_var = tk.BooleanVar(value=False)
        ctk.CTkSwitch(row, text="Editar individual", variable=manual_var, progress_color=ACCENT,
                      button_color=NEON_CYAN, command=self._editor_refresh_config_modes).grid(row=0, column=3, padx=6, pady=(10, 4))
        fields = ctk.CTkFrame(row, fg_color="transparent")
        fields.grid(row=1, column=1, columnspan=2, sticky="ew", padx=6, pady=(0, 10))
        specs = [("Frame", "0"), ("Duración ms", "500"), ("Tamaño %", "25"), ("X %", "50"), ("Y %", "50"), ("Transparencia %", "100")]
        entries = {}
        for col, (field_label, default) in enumerate(specs):
            ctk.CTkLabel(fields, text=field_label, text_color=TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=0, column=col, padx=3)
            ent = ctk.CTkEntry(fields, width=74, fg_color=BG_INPUT, border_color=BORDER)
            ent.insert(0, default)
            ent.grid(row=1, column=col, padx=3)
            entries[field_label] = ent
        ratio = ctk.CTkComboBox(fields, values=["Original", "9:16", "1:1", "4:5", "16:9", "6:19"], width=100,
                                fg_color=BG_INPUT, border_color=BORDER)
        ratio.set("9:16")
        ratio.grid(row=1, column=6, padx=3)
        ctk.CTkLabel(fields, text="Relación", text_color=TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=0, column=6, padx=3)
        position = ctk.CTkComboBox(fields, values=["Manual X/Y", "Centro", "Arriba izquierda", "Arriba centro", "Arriba derecha", "Abajo izquierda", "Abajo centro", "Abajo derecha"], width=125,
                                   fg_color=BG_INPUT, border_color=BORDER)
        position.set("Manual X/Y")
        position.grid(row=1, column=7, padx=3)
        move = ctk.CTkFrame(row, fg_color="transparent")
        move.grid(row=2, column=1, columnspan=2, sticky="ew", padx=6, pady=(0, 10))
        move.grid_columnconfigure(1, weight=1)
        move.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(move, text="Mover X", text_color=TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=0, column=0, padx=(0, 5), sticky="w")
        x_value = ctk.CTkLabel(move, text="50%", text_color=TEXT_BODY, font=ctk.CTkFont(size=10), width=35)
        x_value.grid(row=0, column=2, padx=(5, 14))
        x_slider = ctk.CTkSlider(move, from_=0, to=100, number_of_steps=100, fg_color=BG_INPUT,
                                 progress_color=ACCENT, button_color=NEON_CYAN,
                                 command=lambda value, e=entries["X %"], lbl=x_value: self._editor_position_slider_changed(e, lbl, value))
        x_slider.set(50)
        x_slider.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(move, text="Mover Y", text_color=TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=0, column=3, padx=(0, 5), sticky="w")
        y_value = ctk.CTkLabel(move, text="50%", text_color=TEXT_BODY, font=ctk.CTkFont(size=10), width=35)
        y_value.grid(row=0, column=5, padx=(5, 0))
        y_slider = ctk.CTkSlider(move, from_=0, to=100, number_of_steps=100, fg_color=BG_INPUT,
                                 progress_color=ACCENT, button_color=NEON_CYAN,
                                 command=lambda value, e=entries["Y %"], lbl=y_value: self._editor_position_slider_changed(e, lbl, value))
        y_slider.set(50)
        y_slider.grid(row=0, column=4, sticky="ew")
        ctk.CTkLabel(fields, text="Posición", text_color=TEXT_MUTED, font=ctk.CTkFont(size=10)).grid(row=0, column=7, padx=3)
        ctk.CTkButton(row, text="✕", width=28, fg_color=DANGER, command=lambda r=row: self.editor_remove_row(r)).grid(row=0, column=4, rowspan=2, padx=10)
        config_controls = [*entries.values(), ratio, position, x_slider, y_slider]
        self.editor_rows.append({"frame": row, "label": photo_label, "photo": photo, "ratio": ratio, "position": position,
                                 "manual_var": manual_var, "config_controls": config_controls, **entries})
        self._editor_reindex_rows()
        self._editor_refresh_timeline_targets()
        self._editor_refresh_config_modes()
        self._editor_update_timeline_range()

    def editor_choose_photo(self, entry):
        paths = filedialog.askopenfilenames(title="Fotos para overlay", filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp"), ("Todos", "*.*")])
        if paths:
            entry.delete(0, "end")
            entry.insert(0, paths[0])
            for path in paths[1:]:
                self.editor_add_row()
                new_entry = self.editor_rows[-1]["photo"]
                new_entry.delete(0, "end")
                new_entry.insert(0, path)
            self._editor_update_timeline_range()

    def editor_remove_row(self, row):
        if len(self.editor_rows) == 1:
            return
        item = next((item for item in self.editor_rows if item["frame"] == row), None)
        if item:
            self.editor_rows.remove(item)
            row.destroy()
            self._editor_reindex_rows()
            self._editor_refresh_timeline_targets()
            self._editor_update_timeline_range()

    def _editor_read_overlay_config(self, entries, ratio, position, frame, label):
        try:
            values = {key: float(entries[key].get()) for key in ["Duración ms", "Tamaño %", "X %", "Y %", "Transparencia %"]}
        except ValueError:
            raise ValueError(f"Los valores numéricos de {label} no son válidos.")
        if (frame < 0 or values["Duración ms"] <= 0
                or not 0 <= values["Tamaño %"] <= 100
                or not 0 <= values["X %"] <= 100
                or not 0 <= values["Y %"] <= 100
                or not 0 <= values["Transparencia %"] <= 100):
            raise ValueError(f"Revisá frame, duración, tamaño y transparencia de {label}.")
        return {"frame": int(frame), "duration_ms": values["Duración ms"], "size": values["Tamaño %"],
                "x": values["X %"], "y": values["Y %"], "opacity": values["Transparencia %"],
                "ratio": ratio.get(), "position": position.get()}

    def _editor_collect(self):
        missing_videos = [path for path in self.editor_video_paths if not os.path.isfile(path)]
        if missing_videos:
            raise ValueError("No se encontraron los videos seleccionados: " + ", ".join(missing_videos))
        videos = list(self.editor_video_paths)
        video = videos[0] if videos else ""
        if not video or not os.path.isfile(video):
            raise ValueError("Elegí un video base válido.")
        if self._editor_photo_video_batch_enabled() and self.editor_timeline_info:
            self._editor_update_timeline_range()
        overlays = []
        global_enabled = self.editor_global_enabled.get()
        global_frame = round(float(self.editor_timeline_slider.get())) if self.editor_timeline_info else 0
        global_config = None
        if global_enabled:
            global_config = self._editor_read_overlay_config(
                self.editor_global_entries, self.editor_global_ratio, self.editor_global_position,
                global_frame, "la configuración global",
            )
        for i, item in enumerate(self.editor_rows, start=1):
            photo = item["photo"].get().strip()
            if not photo or not os.path.isfile(photo):
                raise ValueError(f"Elegí la imagen de la Foto {i}.")
            if global_config is not None and not item["manual_var"].get():
                overlay = dict(global_config)
            else:
                overlay = self._editor_read_overlay_config(
                    item, item["ratio"], item["position"], float(item["Frame"].get()), f"la Foto {i}",
                )
            overlay["photo"] = photo
            overlays.append(overlay)
        if self._editor_photo_video_batch_enabled() and self.editor_timeline_info:
            shared_frame = round(float(self.editor_timeline_slider.get()))
            for index, overlay in enumerate(overlays):
                overlay["frame"] = shared_frame
                self.editor_rows[index]["Frame"].delete(0, "end")
                self.editor_rows[index]["Frame"].insert(0, str(shared_frame))
        return videos, overlays

    def _editor_overlays_for_source(self, source, overlays):
        """Clone shared N x M overlays with frame numbers for one source FPS."""
        if not self._editor_photo_video_batch_enabled() or not self.editor_timeline_info:
            return overlays
        import video_editor
        source_info = self.editor_video_info.get(source)
        if source_info is None:
            source_info = video_editor.probe_video(source)
            self.editor_video_info[source] = source_info
        timestamp = round(float(self.editor_timeline_slider.get())) / self.editor_timeline_info["fps"]
        return [
            {**overlay, "frame": video_editor.timestamp_to_source_frame(timestamp, source_info["fps"])}
            for overlay in overlays
        ]

    def editor_preview(self):
        try:
            videos, overlays = self._editor_collect()
        except Exception as exc:
            return messagebox.showwarning("Preview", str(exc))
        if self._editor_cartesian_batch(videos, overlays):
            try:
                photo_index = int(self.editor_timeline_target.get().split()[1]) - 1
                overlays = [overlays[photo_index]]
            except (IndexError, ValueError, AttributeError):
                pass
        video = videos[0]
        overlays = self._editor_overlays_for_source(video, overlays)
        self.editor_status.configure(text="Generando preview…", text_color=WARNING)
        def task():
            import video_editor
            return video_editor.render_preview(video, overlays)
        def done(success, result):
            if not success:
                self.editor_status.configure(text="Error de preview", text_color=DANGER)
                return messagebox.showerror("Preview", result)
            path, timestamp = result
            from PIL import Image
            image = Image.open(path).convert("RGB")
            image.thumbnail((760, 420), Image.Resampling.LANCZOS)
            self.editor_preview_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
            self.editor_preview_label.configure(image=self.editor_preview_image, text="")
            self.editor_status.configure(text=f"Preview en {timestamp:.2f} s (frame aleatorio)", text_color=SUCCESS)
        WorkerThread(self, done, task).start()

    def editor_render(self):
        if getattr(self, "_editor_render_active", False):
            return
        try:
            videos, overlays = self._editor_collect()
        except Exception as exc:
            return messagebox.showwarning("Renderizar", str(exc))
        import video_editor
        pairs = video_editor.build_photo_video_pairs(videos, overlays)
        if len(pairs) > 1:
            output_dir = filedialog.askdirectory(title="Carpeta donde guardar los videos editados")
            if not output_dir:
                return
            jobs, occupied = [], set()
            def reserve_output(stem, label):
                output = os.path.join(output_dir, f"{stem}_{label}_editado.mp4")
                suffix = 2
                while output in occupied or os.path.exists(output):
                    output = os.path.join(output_dir, f"{stem}_{label}_editado_{suffix}.mp4")
                    suffix += 1
                occupied.add(output)
                return output

            for source, overlay, photo_index in pairs:
                stem = os.path.splitext(os.path.basename(source))[0]
                source_overlays = self._editor_overlays_for_source(source, [overlay])
                jobs.append((source, reserve_output(stem, f"foto{photo_index:02d}"), source_overlays))
            return self._editor_render_batch(jobs)
        video = videos[0]
        output = filedialog.asksaveasfilename(title="Guardar video editado", defaultextension=".mp4",
                                              filetypes=[("MP4", "*.mp4")], initialfile="video_editado.mp4")
        if not output:
            return
        performance = render_performance.get_render_performance()
        InstagramAutoPro._set_editor_render_active(self, True)
        self.editor_status.configure(text="Renderizando con FFmpeg…", text_color=WARNING)
        def task():
            import video_editor
            return video_editor.render_video(
                video, output, overlays, performance.ffmpeg_threads)
        def done(success, result):
            InstagramAutoPro._set_editor_render_active(self, False)
            self.editor_status.configure(text="✅ Video guardado" if success else "❌ Error de render", text_color=SUCCESS if success else DANGER)
            if success:
                messagebox.showinfo("Edición completada", f"Video guardado en:\n{result}")
                if hasattr(self, "db") and hasattr(self.db, "save_video_transform_log"):
                    import video_editor
                    self.db.save_video_transform_log(
                        "video_editor",
                        os.path.abspath(video),
                        os.path.abspath(result),
                        {
                            "input_path": os.path.abspath(video),
                            "overlays": video_editor.describe_overlay_log(overlays),
                            "ffmpeg_threads": performance.ffmpeg_threads,
                        },
                    )
            else:
                messagebox.showerror("Renderizar", result)
        try:
            WorkerThread(self, done, task).start()
        except Exception:
            InstagramAutoPro._set_editor_render_active(self, False)
            raise

    def _set_editor_render_active(self, active):
        self._editor_render_active = active
        button = getattr(self, "btn_editor_render", None)
        if button is not None:
            button.configure(state="disabled" if active else "normal")

    def _editor_render_batch(self, jobs):
        """Render one job per requested video/photo combination."""
        if getattr(self, "_editor_render_active", False):
            return
        performance = render_performance.get_render_performance()
        InstagramAutoPro._set_editor_render_active(self, True)
        self.editor_status.configure(text=f"Renderizando {len(jobs)} videos con FFmpeg…", text_color=WARNING)

        def task():
            import video_editor
            with ThreadPoolExecutor(max_workers=performance.workers) as pool:
                futures = [
                    pool.submit(video_editor.render_video, source, output, job_overlays,
                                performance.ffmpeg_threads)
                    for source, output, job_overlays in jobs
                ]
                return [future.result() for future in futures]

        def done(success, result):
            InstagramAutoPro._set_editor_render_active(self, False)
            self.editor_status.configure(text="✅ Videos guardados" if success else "❌ Error de render",
                                         text_color=SUCCESS if success else DANGER)
            if success:
                messagebox.showinfo("Edición completada",
                                    f"{len(result)} videos guardados en:\n{os.path.dirname(result[0])}")
                if hasattr(self, "db") and hasattr(self.db, "save_video_transform_log"):
                    import video_editor
                    for source, output, job_overlays in jobs:
                        self.db.save_video_transform_log(
                            "video_editor",
                            os.path.abspath(source),
                            os.path.abspath(output),
                            {
                                "input_path": os.path.abspath(source),
                                "overlays": video_editor.describe_overlay_log(job_overlays),
                                "ffmpeg_threads": performance.ffmpeg_threads,
                            },
                        )
            else:
                messagebox.showerror("Renderizar lote", result)

        try:
            WorkerThread(self, done, task).start()
        except Exception:
            InstagramAutoPro._set_editor_render_active(self, False)
            raise


    # FORGE DE METADATA
    # ══════════════════════════════════════════════════════════════════════
    def _build_photo_forge_frame(self):
        f = self._frames["PhotoForge"]
        f.grid_rowconfigure(2, weight=1)
        f.grid_columnconfigure(0, weight=1)
        PageHeader(
            f, "CONTENIDO", "Photo Forge",
            "Genera finales independientes por identidad sin modificar las imágenes fuente.",
        ).grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))

        settings = Card(f, title="Lote de imágenes")
        settings.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 10))
        form = settings.body
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(form, text="Nombre del lote:", text_color=TEXT_MUTED).grid(
            row=0, column=0, padx=(14, 6), pady=12, sticky="e")
        self.photo_forge_batch = ctk.CTkEntry(form, fg_color=BG_INPUT, border_color=BORDER)
        self.photo_forge_batch.insert(0, "Fotos_" + datetime.now().strftime("%Y%m%d"))
        self.photo_forge_batch.grid(row=0, column=1, padx=6, pady=12, sticky="ew")
        ctk.CTkLabel(form, text="Salida:", text_color=TEXT_MUTED).grid(
            row=0, column=2, padx=(14, 6), pady=12, sticky="e")
        self.photo_forge_output = ctk.CTkEntry(
            form, fg_color=BG_INPUT, border_color=BORDER,
            placeholder_text=os.path.join(_BASE_DIR, "imagenes_finales"),
        )
        self.photo_forge_output.insert(0, os.path.join(_BASE_DIR, "imagenes_finales"))
        self.photo_forge_output.grid(row=0, column=3, padx=6, pady=12, sticky="ew")
        GhostButton(form, text="Elegir", width=74, command=self._photo_forge_choose_output).grid(
            row=0, column=4, padx=(4, 14), pady=12)
        self.photo_forge_mirror_var = tk.BooleanVar(value=False)
        ToggleRow(form, "Espejo horizontal", variable=self.photo_forge_mirror_var).grid(
            row=1, column=1, padx=6, pady=(0, 10), sticky="w")

        content = ctk.CTkFrame(f, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 10))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure((0, 1), weight=1)
        source_card = Card(content, title="Imágenes fuente")
        source_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        source = source_card.body
        source.grid_rowconfigure(0, weight=1)
        source.grid_columnconfigure(0, weight=1)
        self.photo_forge_sources = tk.Listbox(
            source, bg=self.themed(BG_INPUT), fg=self.themed(TEXT_BODY),
            selectbackground=self.themed(ACCENT), selectforeground=self.themed(ACCENT_TEXT),
            selectmode=tk.EXTENDED, borderwidth=0, highlightthickness=1,
            highlightbackground=self.themed(BORDER), font=FONT_BODY,
        )
        self.photo_forge_sources.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 6))
        self.photo_forge_sources.bind("<<ListboxSelect>>", self._photo_forge_show_preview)
        self.photo_forge_preview = ctk.CTkLabel(
            source, text="Selecciona una imagen", text_color=TEXT_MUTED,
            fg_color=BG_CARD2, corner_radius=4, height=170,
        )
        self.photo_forge_preview.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        source_buttons = ctk.CTkFrame(source, fg_color="transparent")
        source_buttons.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        PrimaryButton(source_buttons, text="Agregar imágenes", command=self._photo_forge_add_images).pack(side="left", padx=(0, 6))
        GhostButton(source_buttons, text="Quitar seleccionadas", command=self._photo_forge_remove_images).pack(side="left")

        account_card = Card(content, title="Identidades destino")
        account_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        account = account_card.body
        account.grid_rowconfigure(0, weight=1)
        account.grid_columnconfigure(0, weight=1)
        self.photo_forge_accounts = tk.Listbox(
            account, bg=self.themed(BG_INPUT), fg=self.themed(TEXT_BODY),
            selectbackground=self.themed(ACCENT), selectforeground=self.themed(ACCENT_TEXT),
            selectmode=tk.EXTENDED, borderwidth=0, highlightthickness=1,
            highlightbackground=self.themed(BORDER), font=FONT_BODY,
        )
        self.photo_forge_accounts.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 6))
        account_buttons = ctk.CTkFrame(account, fg_color="transparent")
        account_buttons.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        GhostButton(account_buttons, text="Todas", command=lambda: self.photo_forge_accounts.select_set(0, "end")).pack(side="left", padx=(0, 6))
        GhostButton(account_buttons, text="Ninguna", command=lambda: self.photo_forge_accounts.selection_clear(0, "end")).pack(side="left")
        GhostButton(account_buttons, text="Actualizar", command=self._photo_forge_reload_accounts).pack(side="right")
        self.photo_forge_account_rows = []
        self._photo_forge_reload_accounts()

        actions = ctk.CTkFrame(f, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 8))
        GhostButton(actions, text="Previsualizar", command=self._photo_forge_preview).pack(side="left", padx=(0, 8))
        self.photo_forge_run_button = PrimaryButton(actions, text="Generar finales por cuenta", command=self._photo_forge_run)
        self.photo_forge_run_button.pack(side="left")
        self.photo_forge_result = ctk.CTkTextbox(f, height=95, fg_color=BG_CARD2, text_color=TEXT_BODY)
        self.photo_forge_result.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 16))
        self.photo_forge_result.insert("end", "Los originales se conservan. Cada identidad recibe un archivo final separado, byte por byte idéntico al original.")

    def _photo_forge_reload_accounts(self):
        if not hasattr(self, "photo_forge_accounts"):
            return
        self.photo_forge_account_rows = self.db.get_all_accounts()
        self.photo_forge_accounts.delete(0, "end")
        for row in self.photo_forge_account_rows:
            self.photo_forge_accounts.insert("end", f"@{row.get('username', '')}  ·  {row.get('account_type', '')}")
        self.photo_forge_accounts.select_set(0, "end")

    def _photo_forge_choose_output(self):
        path = filedialog.askdirectory(title="Carpeta base de imágenes finales", parent=self)
        if path:
            self.photo_forge_output.delete(0, "end")
            self.photo_forge_output.insert(0, path)

    def _photo_forge_add_images(self):
        paths = filedialog.askopenfilenames(
            title="Seleccionar imágenes fuente",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp *.tif *.tiff"), ("Todos", "*.*")],
            parent=self,
        )
        existing = {self.photo_forge_sources.get(index).casefold() for index in range(self.photo_forge_sources.size())}
        for path in paths:
            if path.casefold() not in existing:
                self.photo_forge_sources.insert("end", path)
                existing.add(path.casefold())

    def _photo_forge_remove_images(self):
        for index in reversed(self.photo_forge_sources.curselection()):
            self.photo_forge_sources.delete(index)
        self._photo_forge_show_preview()

    def _photo_forge_show_preview(self, _event=None):
        selection = self.photo_forge_sources.curselection()
        if not selection:
            self.photo_forge_preview.configure(image=None, text="Selecciona una imagen")
            self.photo_forge_preview_ref = None
            return
        path = self.photo_forge_sources.get(selection[0])
        try:
            from PIL import Image, ImageOps
            with Image.open(path) as source:
                dimensions = source.size
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((520, 250), Image.Resampling.LANCZOS)
                self.photo_forge_preview_ref = ctk.CTkImage(
                    light_image=image, dark_image=image, size=image.size
                )
            self.photo_forge_preview.configure(
                image=self.photo_forge_preview_ref,
                text=f"{os.path.basename(path)} · {dimensions[0]}×{dimensions[1]}",
                compound="top",
            )
        except Exception:
            self.photo_forge_preview.configure(image=None, text=f"No se pudo previsualizar: {os.path.basename(path)}")
            self.photo_forge_preview_ref = None

    def _photo_forge_selected_accounts(self):
        return [self.photo_forge_account_rows[index] for index in self.photo_forge_accounts.curselection()]

    def _photo_forge_preview(self):
        source_count = self.photo_forge_sources.size()
        accounts = self._photo_forge_selected_accounts()
        if not source_count or not accounts:
            return messagebox.showwarning("Photo Forge", "Selecciona imágenes e identidades.", parent=self)
        self.photo_forge_result.configure(state="normal")
        self.photo_forge_result.delete("1.0", "end")
        self.photo_forge_result.insert(
            "end",
            f"Lote: {self.photo_forge_batch.get().strip()}\n"
            f"Imágenes: {source_count} · Identidades: {len(accounts)} · Finales: {source_count * len(accounts)}\n"
            f"Salida: {os.path.join(self.photo_forge_output.get().strip(), self.photo_forge_batch.get().strip())}\n"
            + (
                "Se aplicará espejo horizontal. JPEG se re-codifica en calidad 100; el original no cambia."
                if self.photo_forge_mirror_var.get()
                else "Se preservan los bytes del archivo. No hay conversión ni modificación del original."
            ),
        )
        self.photo_forge_result.configure(state="disabled")

    def _photo_forge_run(self):
        source_paths = [self.photo_forge_sources.get(index) for index in range(self.photo_forge_sources.size())]
        accounts = self._photo_forge_selected_accounts()
        output_root = self.photo_forge_output.get().strip()
        batch_name = self.photo_forge_batch.get().strip()
        mirror_horizontal = bool(self.photo_forge_mirror_var.get())
        if not source_paths or not accounts or not output_root or not batch_name:
            return messagebox.showwarning("Photo Forge", "Completa imágenes, identidades, lote y salida.", parent=self)
        total = len(source_paths) * len(accounts)
        confirmation = (
            f"Se crearán hasta {total} archivos finales en carpetas separadas por identidad.\n"
            f"Espejo horizontal: {'sí' if mirror_horizontal else 'no'}.\n"
        )
        if mirror_horizontal:
            confirmation += "JPEG se re-codifica en calidad 100.\n"
        confirmation += "Las imágenes fuente se conservarán sin modificar.\n\n¿Continuar?"
        if not messagebox.askyesno(
            "Generar Photo Forge",
            confirmation,
            parent=self,
        ):
            return
        account_rows = [dict(row) for row in accounts]
        self.photo_forge_run_button.configure(state="disabled")
        self.photo_forge_result.configure(state="normal")
        self.photo_forge_result.delete("1.0", "end")
        self.photo_forge_result.insert("end", f"Validando fuentes y generando {total} finales...")
        self.photo_forge_result.configure(state="disabled")

        def task():
            import photo_forge
            plan = photo_forge.plan_photo_copies(
                source_paths, account_rows, output_root, batch_name, mirror_horizontal
            )
            return photo_forge.create_photo_copies(plan, output_root, batch_name)

        def done(success, result):
            self.photo_forge_run_button.configure(state="normal")
            self.photo_forge_result.configure(state="normal")
            self.photo_forge_result.delete("1.0", "end")
            if success:
                self.photo_forge_result.insert(
                    "end",
                    f"Finales nuevos: {len(result['created'])} · Ya existentes: {len(result['existing'])}\n"
                    f"Manifiesto: {result['manifest_path']}\n"
                    "Cada salida pertenece a una identidad; no se copiaron archivos al calendario.",
                )
                self.acct_lane_root.delete(0, "end")
                self.acct_lane_root.insert(0, result["batch_dir"])
                self.show_frame("Logistica")
                messagebox.showinfo(
                    "Photo Forge",
                    f"Finales generados: {len(result['created'])}\n{result['batch_dir']}",
                    parent=self,
                )
            else:
                self.photo_forge_result.insert("end", f"Error: {result}")
                messagebox.showerror("Photo Forge", str(result), parent=self)
            self.photo_forge_result.configure(state="disabled")

        WorkerThread(self, done, task).start()

    def _build_transform_log_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Logs de transformacion",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_BODY,
        ).grid(row=0, column=0, sticky="w")
        GhostButton(header, text="Actualizar", command=self.refresh_transform_log_table).grid(row=0, column=1)

        table_wrap = ctk.CTkFrame(panel, fg_color="transparent")
        table_wrap.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 8))
        table_wrap.grid_columnconfigure(0, weight=1)
        columns = ("process", "output", "source", "tanda", "rotation", "crop", "speed", "created")
        self.transform_log_tree = ttk.Treeview(
            table_wrap,
            columns=columns,
            show="headings",
            style="Premium.Treeview",
            height=8,
        )
        widths = {
            "process": 95,
            "output": 220,
            "source": 180,
            "tanda": 130,
            "rotation": 80,
            "crop": 70,
            "speed": 80,
            "created": 145,
        }
        for column in columns:
            self.transform_log_tree.heading(column, text=column.title())
            self.transform_log_tree.column(column, width=widths[column], anchor="w")
        self.transform_log_tree.bind("<<TreeviewSelect>>", self._on_transform_log_select)
        self.transform_log_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table_wrap, orient="vertical", command=self.transform_log_tree.yview)
        self.transform_log_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 0))

        self.transform_log_detail = tk.Text(
            panel,
            height=8,
            wrap="word",
            bg=self.themed(BG_INPUT),
            fg=self.themed(TEXT_BODY),
            insertbackground=self.themed(TEXT_BODY),
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.themed(BORDER),
            font=FONT_MONO,
        )
        self.transform_log_detail.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 14))
        self._transform_log_rows = {}
        self.refresh_transform_log_table()
        return panel

    def refresh_transform_log_table(self):
        tree = getattr(self, "transform_log_tree", None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        self._transform_log_rows = {}
        for row in self.db.list_video_transform_logs(limit=500):
            try:
                details = json.loads(row["details_json"])
            except Exception:
                details = {}
            summary = _format_transform_summary(details)
            item = tree.insert(
                "",
                "end",
                values=(
                    row["process_kind"],
                    row["output_filename"],
                    os.path.basename(row["source_path"]),
                    row.get("tanda_name") or "",
                    summary["rotation"],
                    summary["crop"],
                    summary["speed"],
                    row["created_at"],
                ),
            )
            self._transform_log_rows[item] = row

    def _on_transform_log_select(self, _event=None):
        tree = getattr(self, "transform_log_tree", None)
        detail = getattr(self, "transform_log_detail", None)
        if tree is None or detail is None:
            return
        selection = tree.selection()
        if not selection:
            return
        row = self._transform_log_rows.get(selection[0])
        try:
            details = json.loads(row["details_json"]) if row else {}
        except Exception:
            details = {}
        detail.delete("1.0", "end")
        detail.insert("1.0", json.dumps(details, ensure_ascii=False, indent=2))

    def _build_forge_frame(self):
        self.forge_video_paths = []
        self.forge_meta_assignments = []

        f = self._frames["Forge"]
        f.grid_rowconfigure(0, weight=1)
        f.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(f, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # CTkScrollableFrame divide el delta de la rueda entre 6 y trunca a
        # int, así que mice/trackpads que mandan deltas chicos (smooth-scroll)
        # terminan con paso 0 y la rueda no hace nada. Forzamos mínimo 1 unidad.
        def _forge_wheel_fix(event):
            if scroll.check_if_master_is_canvas(event.widget) and scroll._parent_canvas.yview() != (0.0, 1.0):
                scroll._parent_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        scroll.bind_all("<MouseWheel>", _forge_wheel_fix, add="+")

        # ── Header ──────────────────────────────────────────────────────
        PageHeader(scroll, kicker="CONTENIDO", title="Forge de Metadata",
                   description="Inyecta fingerprints iPhone únicos · 276,000 combinaciones disponibles",
                   action=("Tanda", self.forge_preview_metadata)
                   ).grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))

        # ── Top: dos tarjetas (Videos | Config) ─────────────────────────
        top = ctk.CTkFrame(scroll, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", padx=24, pady=(14, 0))
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=1)

        # — Tarjeta Paso 1: Lista de videos —
        card_vids = ctk.CTkFrame(top, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        card_vids.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        card_vids.grid_rowconfigure(1, weight=1)
        card_vids.grid_columnconfigure(0, weight=1)

        hdr_v = ctk.CTkFrame(card_vids, fg_color="transparent")
        hdr_v.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 6))
        ctk.CTkLabel(hdr_v, text="1.  Videos a Procesar",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=NEON_CYAN).pack(side="left")
        self.forge_lbl_count = ctk.CTkLabel(hdr_v, text="0 videos",
                                             font=ctk.CTkFont(size=11),
                                             text_color=TEXT_MUTED)
        self.forge_lbl_count.pack(side="right")

        self.forge_lst = tk.Listbox(
            card_vids, bg=self.themed(BG_INPUT), fg=self.themed(TEXT_BODY),
            selectbackground=self.themed(ACCENT), selectforeground=self.themed(ACCENT_TEXT),
            selectmode=tk.EXTENDED,
            borderwidth=0, highlightthickness=1, highlightbackground=self.themed(BORDER),
            font=FONT_BODY, height=9
        )
        self.forge_lst.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 6))

        btn_v = ctk.CTkFrame(card_vids, fg_color="transparent")
        btn_v.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 16))
        PrimaryButton(btn_v, text="＋  Agregar Videos",
                      command=self.forge_add_videos).pack(side="left", padx=(0, 8))
        GhostButton(btn_v, text="−  Quitar",
                    command=self.forge_remove_video).pack(side="left")

        # — Tarjeta Paso 2: Config —
        card_cfg = ctk.CTkFrame(top, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        card_cfg.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        card_cfg.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card_cfg, text="2.  Configuración",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=NEON_PURPLE).grid(row=0, column=0, columnspan=2,
                                                  sticky="w", padx=18, pady=(16, 8))

        # NOTE: "Copias por vídeo" is read via int(self.e_forge_copies.get())
        # in both forge_preview_metadata and forge_process, so a Stepper
        # (whose .get() already returns an int) is a safe drop-in.
        # "Días a distribuir" is read via self.e_forge_days.get().strip()
        # or "MAX" in forge_process — a Stepper.get() returns an int, which
        # has no .strip(), so this field MUST stay a CTkEntry.
        self.forge_trial_mode_var = tk.StringVar(value="Normal")
        ctk.CTkLabel(card_cfg, text="Tipo de tanda:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11), anchor="e"
                     ).grid(row=1, column=0, padx=(18, 8), pady=7, sticky="e")
        self.forge_trial_mode = SegmentedControl(
            card_cfg, values=["Normal", "Trials"], default="Normal",
            command=self.forge_trial_mode_var.set,
        )
        self.forge_trial_mode.grid(row=1, column=1, padx=(0, 18), pady=7, sticky="ew")

        cfg_rows = [
            ("Nombre de tanda:",   "e_forge_tanda",   None,    None),
            ("Copias por vídeo:",   "e_forge_copies",  None,    "stepper"),
            ("Días a distribuir:", "e_forge_days",     "MAX",   None),
        ]
        for row_i, (lbl, attr, default, kind) in enumerate(cfg_rows, start=2):
            ctk.CTkLabel(card_cfg, text=lbl, text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=11), anchor="e"
                         ).grid(row=row_i, column=0, padx=(18, 8), pady=7, sticky="e")
            if kind == "stepper":
                widget = Stepper(card_cfg, value=4, min=1, max=50)
                widget.grid(row=row_i, column=1, padx=(0, 18), pady=7, sticky="w")
                setattr(self, attr, widget)
            else:
                widget = ctk.CTkEntry(card_cfg, fg_color=BG_INPUT,
                                      border_color=BORDER)
                if default:
                    widget.insert(0, default)
                widget.grid(row=row_i, column=1, padx=(0, 18), pady=7, sticky="ew")
                setattr(self, attr, widget)

        self.forge_profile_var = tk.StringVar(value="Legacy MP4")
        ctk.CTkLabel(card_cfg, text="Perfil de salida:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11), anchor="e").grid(
                         row=5, column=0, padx=(18, 8), pady=7, sticky="e")
        profile_frame = ctk.CTkFrame(card_cfg, fg_color="transparent")
        profile_frame.grid(row=5, column=1, padx=(0, 18), pady=7, sticky="ew")
        SegmentedControl(profile_frame, values=["Legacy MP4", "iPhone SDR", "iPhone HLG"],
                         default="Legacy MP4", command=self.forge_profile_var.set).pack(fill="x")

        # ── Eje Efectos (qué efectos) ────────────────────────────────────
        ctk.CTkLabel(card_cfg, text="Efectos", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).grid(
                         row=6, column=0, columnspan=2, sticky="w", padx=18, pady=(8, 2))
        self.forge_efectos_var = tk.StringVar(value="Default")
        SegmentedControl(card_cfg, values=["Default", "Light", "Medio", "Alto", "Custom"],
                         default="Default", command=self._forge_on_efectos_change).grid(
                             row=7, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 6))

        # ── Eje Fuerza (cuánta intensidad) ────────────────────────────────
        ctk.CTkLabel(card_cfg, text="Fuerza", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).grid(
                         row=8, column=0, columnspan=2, sticky="w", padx=18, pady=(4, 2))
        self.forge_fuerza_var = tk.StringVar(value="Default")
        SegmentedControl(card_cfg, values=["Default", "Light", "Medio", "Alto", "Custom"],
                         default="Default", command=self._forge_on_fuerza_change).grid(
                             row=9, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 6))

        # Panel de Fuerza=Custom (slider general + rangos por efecto + espejo)
        FORGE_RANGE_ROWS = [
            ("crop",       "Recorte (px)",   "2",     "10"),
            ("zoom",       "Zoom (factor)",  "1.00",  "1.05"),
            ("rotate",     "Rotación (°)",   "-1.5",  "1.5"),
            ("brightness", "Brillo (Δ)",     "-0.03", "0.03"),
            ("contrast",   "Contraste (×)",  "0.94",  "1.06"),
            ("saturation", "Saturación (×)", "0.90",  "1.10"),
            ("gamma",      "Gamma (×)",      "0.95",  "1.05"),
            ("noise",      "Grano",          "4",     "8"),
            ("speed",      "Velocidad (×)",  "0.985", "1.015"),
            ("trim",       "Trim (ms)",      "0",     "150"),
        ]
        self.forge_custom_panel = ctk.CTkFrame(card_cfg, fg_color="transparent")
        self.forge_custom_panel.grid_columnconfigure(2, weight=1)
        self._forge_custom_row = 10   # grid row inside card_cfg (reuse the old slider row)

        ctk.CTkLabel(self.forge_custom_panel, text="Intensidad general", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))
        self.forge_strength_slider = ctk.CTkSlider(self.forge_custom_panel, from_=0, to=100, number_of_steps=100)
        self.forge_strength_slider.set(50)
        self.forge_strength_slider.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        self.forge_range_entries = {}
        for i, (param, label, dmin, dmax) in enumerate(FORGE_RANGE_ROWS):
            rr = 2 + i
            ctk.CTkLabel(self.forge_custom_panel, text=label, text_color=TEXT_BODY,
                         font=ctk.CTkFont(size=11)).grid(row=rr, column=0, sticky="w", pady=2)
            e_min = ctk.CTkEntry(self.forge_custom_panel, width=64, fg_color=BG_INPUT, border_color=BORDER)
            e_min.insert(0, dmin)
            e_min.grid(row=rr, column=1, padx=(8, 4), pady=2)
            e_max = ctk.CTkEntry(self.forge_custom_panel, width=64, fg_color=BG_INPUT, border_color=BORDER)
            e_max.insert(0, dmax)
            e_max.grid(row=rr, column=2, sticky="w", padx=(4, 0), pady=2)
            self.forge_range_entries[param] = (e_min, e_max)

        self.forge_custom_mirror_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.forge_custom_panel, text="Espejo horizontal",
                        variable=self.forge_custom_mirror_var,
                        font=ctk.CTkFont(size=11), text_color=TEXT_BODY).grid(
                            row=2 + len(FORGE_RANGE_ROWS), column=0, columnspan=3, sticky="w", pady=(6, 0))

        # — Micro-ediciones por copia (variant engine) —
        self.FORGE_FX_DEFS = [
            ("crop",   "Recorte de bordes"),
            ("mirror", "Espejo horizontal"),
            ("zoom",   "Zoom leve"),
            ("rotate", "Rotación mínima"),
            ("color",  "Filtro de color"),
            ("noise",  "Grano sutil"),
            ("speed",  "Micro-velocidad"),
            ("trim",   "Recorte de ms"),
        ]
        fx_frame = ctk.CTkFrame(card_cfg, fg_color="transparent")
        fx_frame.grid(row=11, column=0, columnspan=2, sticky="ew",
                      padx=18, pady=(4, 16))
        fx_frame.grid_columnconfigure(0, weight=1)
        fx_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(fx_frame, text="Micro-ediciones por copia:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=NEON_PURPLE).grid(row=0, column=0,
                                                  sticky="w", pady=(0, 4))
        self.forge_fx_vars = {}
        for i, (key, lbl) in enumerate(self.FORGE_FX_DEFS):
            var = tk.BooleanVar(value=True)
            self.forge_fx_vars[key] = var
            ToggleRow(fx_frame, lbl, variable=var).grid(
                row=1 + i // 2, column=i % 2, sticky="ew", padx=(0, 8), pady=3)
        self.fx_frame = fx_frame

        # ── Tabla Preview ────────────────────────────────────────────────
        preview_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        preview_card.grid(row=2, column=0, sticky="nsew", padx=24, pady=(14, 0))
        preview_card.grid_rowconfigure(1, weight=1)
        preview_card.grid_columnconfigure(0, weight=1)

        ph = ctk.CTkFrame(preview_card, fg_color="transparent")
        ph.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        ctk.CTkLabel(ph, text="Vista Previa de Metadata",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT_BODY).pack(side="left")
        ctk.CTkLabel(ph, text="(genera el preview para ver las asignaciones)",
                     font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(side="left", padx=10)

        tree_wrap = ctk.CTkFrame(preview_card, fg_color="transparent")
        tree_wrap.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 14))
        tree_wrap.grid_rowconfigure(0, weight=1)
        tree_wrap.grid_columnconfigure(0, weight=1)

        cols = ("Video", "Modelo iPhone", "Ciudad", "Carrier", "iOS")
        self.forge_tree = ttk.Treeview(tree_wrap, columns=cols, show="headings",
                                       style="Premium.Treeview", height=10)
        col_w = {"Video": 200, "Modelo iPhone": 190, "Ciudad": 140, "Carrier": 170, "iOS": 70}
        for col in cols:
            self.forge_tree.heading(col, text=col)
            self.forge_tree.column(col, width=col_w[col], anchor="center")
        scr = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.forge_tree.yview)
        self.forge_tree.configure(yscrollcommand=scr.set)
        self.forge_tree.grid(row=0, column=0, sticky="nsew")
        scr.grid(row=0, column=1, sticky="ns", padx=(2, 0))

        # ── Botonera + Progreso ──────────────────────────────────────────
        bot = ctk.CTkFrame(scroll, fg_color="transparent")
        bot.grid(row=3, column=0, sticky="ew", padx=24, pady=(14, 20))
        bot.grid_columnconfigure(0, weight=1)

        GhostButton(bot, text="👁  Preview Metadata", height=BTN_H_LG,
                    command=self.forge_preview_metadata).grid(row=0, column=0, padx=(0, 8))

        self.btn_forge_reshuffle = GhostButton(bot, text="🔀  Regenerar Shuffle",
                    height=BTN_H_LG, state="disabled", command=self.forge_reshuffle)
        self.btn_forge_reshuffle.grid(row=0, column=1, padx=(0, 8))

        self._build_render_performance_control(bot, "Forge").grid(
            row=0, column=2, padx=(0, 8))

        self.btn_forge_process = PrimaryButton(bot, text="⚡  Procesar Ahora",
                    height=BTN_H_LG, state="disabled", command=self.forge_process)
        self.btn_forge_process.grid(row=0, column=3)

        prog_wrap = ctk.CTkFrame(bot, fg_color="transparent")
        prog_wrap.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        prog_wrap.grid_columnconfigure(0, weight=1)

        self.forge_pb = ctk.CTkProgressBar(prog_wrap, fg_color=BG_INPUT,
                                            progress_color=NEON_PURPLE, height=8)
        self.forge_pb.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.forge_pb.set(0)

        self.forge_pb_lbl = ctk.CTkLabel(prog_wrap, text="Listo.",
                                          font=ctk.CTkFont(size=11),
                                          text_color=TEXT_MUTED)
        self.forge_pb_lbl.grid(row=1, column=0, sticky="w")

        self._build_transform_log_panel(scroll).grid(
            row=4, column=0, sticky="nsew", padx=24, pady=(0, 20)
        )

        # Estado inicial "Default": ocultar toggles manuales y slider de Custom.
        self._forge_on_efectos_change("Default")
        self._forge_on_fuerza_change("Default")

    def _forge_on_efectos_change(self, level: str) -> None:
        self.forge_efectos_var.set(level)
        # Los 8 toggles manuales solo se muestran en Custom.
        if level == "Custom":
            self.fx_frame.grid()
        elif self.fx_frame.winfo_manager():
            self.fx_frame.grid_remove()

    def _forge_on_fuerza_change(self, level: str) -> None:
        self.forge_fuerza_var.set(level)
        if level == "Custom":
            self.forge_custom_panel.grid(row=self._forge_custom_row, column=0, columnspan=2,
                                         sticky="ew", padx=18, pady=(0, 6))
        elif self.forge_custom_panel.winfo_manager():
            self.forge_custom_panel.grid_remove()

    def forge_add_videos(self):
        paths = filedialog.askopenfilenames(
            title="Seleccionar Videos",
            filetypes=[("Video", "*.mp4 *.mov"), ("Todos los archivos", "*.*")]
        )
        for p in paths:
            if p not in self.forge_video_paths:
                self.forge_video_paths.append(p)
                self.forge_lst.insert(tk.END, os.path.basename(p))
        self.forge_lbl_count.configure(text=f"{len(self.forge_video_paths)} videos")

    def forge_remove_video(self):
        for idx in reversed(self.forge_lst.curselection()):
            self.forge_lst.delete(idx)
            self.forge_video_paths.pop(idx)
        self.forge_lbl_count.configure(text=f"{len(self.forge_video_paths)} videos")

    def forge_preview_metadata(self):
        n_videos = len(self.forge_video_paths)
        if n_videos == 0:
            return messagebox.showwarning("⚠️", "Agrega al menos un video primero.")
        try:
            copies = int(self.e_forge_copies.get())
            if copies < 1:
                raise ValueError
        except ValueError:
            return messagebox.showwarning("⚠️", "Copias por vídeo debe ser un número >= 1.")

        n_total = n_videos * copies
        selected_profile = getattr(getattr(self, "forge_profile_var", None), "get", lambda: "Legacy MP4")()
        color_summary = ""
        retry_items = None
        self.forge_iphone_assume_unknown_sdr = False
        if selected_profile != "Legacy MP4":
            from forge_iphone_profile import preflight_batch, probe_file
            profile_key = "iphone_hlg" if selected_profile == "iPhone HLG" else "iphone_sdr"
            try:
                probes = {path: probe_file(path) for path in self.forge_video_paths}
                preflight = preflight_batch(probes, profile_key)
            except Exception as error:
                return messagebox.showerror("Preflight iPhone", str(error))
            unknown_paths = [
                path for path in preflight["blocked"]
                if preflight["sources"].get(path) == "unknown"
            ]
            if unknown_paths:
                sample = "\n".join(
                    f"- {os.path.basename(path)}" for path in unknown_paths[:12]
                )
                if len(unknown_paths) > 12:
                    sample += f"\n- ... y {len(unknown_paths) - 12} más"
                assume = messagebox.askyesno(
                    "Fuentes sin color",
                    f"Hay {len(unknown_paths)} fuente(s) sin tags de color reconocibles.\n\n"
                    f"¿Confirmás asumir SDR BT.709 para esta tanda?\n\n{sample}\n\n"
                    "Esto se registrará por archivo y se aplicará sólo a este Forge.",
                )
                if assume:
                    preflight = preflight_batch(
                        probes, profile_key, assume_unknown_sdr=True)
                    self.forge_iphone_assume_unknown_sdr = True
            self.forge_iphone_preflight = preflight
            counts = preflight["counts"]
            color_summary = (f" · {selected_profile} MOV · SDR {counts['sdr']} / "
                             f"HLG {counts['hlg']} / desconocidos {counts['unknown']}")
            if preflight["assumptions"]:
                color_summary += f" · sin tags asumidos SDR {len(preflight['assumptions'])}"
            if preflight["blocked"]:
                details = "\n".join(f"{os.path.basename(path)}: {reason}"
                                    for path, reason in preflight["blocked"].items())
                return messagebox.showerror("Preflight iPhone: fuentes bloqueadas", details)
            status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "videos_finales", self.e_forge_tanda.get().strip(),
                                       "forge_batch_status.json")
            if os.path.isfile(status_path):
                try:
                    with open(status_path, encoding="utf-8") as status_file:
                        status = json.load(status_file)
                    if status.get("profile") != profile_key:
                        raise ValueError("La tanda existente usa otro perfil")
                    if status.get("state") not in ("complete", "incomplete", "processing"):
                        raise ValueError("Estado Forge desconocido")
                    if status.get("state") in ("incomplete", "processing"):
                        retry_items = status["pending"]
                        if any(item["source_path"] not in self.forge_video_paths
                               for item in retry_items):
                            raise ValueError("Incluye todas las fuentes pendientes")
                        n_total = len(retry_items)
                        color_summary += f" · reintento de {n_total} copia(s) pendiente(s)"
                except (OSError, ValueError, KeyError, TypeError) as error:
                    return messagebox.showerror("Reintento Forge", str(error))
        try:
            import metadata_pool
            self.forge_meta_assignments = (
                [item["meta"] for item in retry_items] if retry_items is not None else
                metadata_pool.generate_unique_metadata(self.db, n_total))
        except ValueError as e:
            return messagebox.showerror("Sin combinaciones disponibles", str(e))

        for item in self.forge_tree.get_children():
            self.forge_tree.delete(item)
        if retry_items is not None:
            preview_rows = [(item["output_name"], item["meta"]) for item in retry_items]
        else:
            preview_rows = [
                (f"{os.path.basename(path)}  (c{c:02d})",
                 self.forge_meta_assignments[index * copies + c - 1])
                for index, path in enumerate(self.forge_video_paths)
                for c in range(1, copies + 1)
            ]
        for row_idx, (label, meta) in enumerate(preview_rows):
            tag = "even" if row_idx % 2 == 0 else "odd"
            self.forge_tree.insert("", tk.END, tags=(tag,), values=(
                label, meta["iphone_model"], meta.get("city", ""),
                meta.get("carrier", ""), meta["ios_version"]
            ))
        self.btn_forge_process.configure(state="normal")
        self.btn_forge_reshuffle.configure(state="normal")
        self.forge_pb_lbl.configure(
            text=(f"✅ {n_total} asignaciones {'reservadas' if retry_items is not None else 'generadas'}"
                  f"{color_summary}. Revisá y presioná Procesar."),
            text_color=SUCCESS
        )

    def forge_reshuffle(self):
        self.forge_preview_metadata()

    def forge_process(self):
        performance = render_performance.get_render_performance()
        if not self.forge_video_paths:
            return messagebox.showwarning("⚠️", "No hay videos en la lista.")
        if not self.forge_meta_assignments:
            return messagebox.showwarning("⚠️", "Generá el preview primero.")

        tanda_name = self.e_forge_tanda.get().strip()

        if not tanda_name:
            return messagebox.showwarning("⚠️", "Ingresá un nombre para la tanda Forge.")
        try:
            copies = int(self.e_forge_copies.get())
            if copies < 1:
                raise ValueError
        except ValueError:
            return messagebox.showwarning("⚠️", "Copias por vídeo debe ser un número >= 1.")

        n_total = len(self.forge_video_paths) * copies
        is_trial_tanda = self.forge_trial_mode_var.get() == "Trials"

        # Leer checkboxes de micro-ediciones en el hilo principal (tk vars no
        # son seguras desde el worker).
        import metadata_pool
        selected_profile = getattr(getattr(self, "forge_profile_var", None), "get", lambda: "Legacy MP4")()
        output_profile = {"iPhone SDR": "iphone_sdr", "iPhone HLG": "iphone_hlg"}.get(selected_profile)
        pending_retry = None
        prior_status = None
        status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "videos_finales", tanda_name, "forge_batch_status.json")
        if output_profile and os.path.isfile(status_path):
            try:
                with open(status_path, encoding="utf-8") as status_file:
                    old_status = json.load(status_file)
                prior_status = old_status
                if old_status.get("profile") != output_profile:
                    raise ValueError("La tanda existente usa otro perfil")
                if old_status.get("state") not in ("complete", "incomplete", "processing"):
                    raise ValueError("Estado Forge desconocido")
                if old_status.get("state") in ("incomplete", "processing"):
                    pending_retry = old_status
                    selected = set(self.forge_video_paths)
                    if any(item["source_path"] not in selected for item in old_status["pending"]):
                        raise ValueError("Incluye todas las fuentes pendientes para reintentar la tanda")
            except (OSError, ValueError, KeyError, TypeError) as error:
                return messagebox.showerror("Reintento Forge", str(error))
        preflight = None
        if output_profile:
            from forge_iphone_profile import preflight_batch, probe_file, runtime_capabilities
            try:
                missing = {"libx265", "aac", "zscale"} - runtime_capabilities()
                if missing:
                    raise RuntimeError(f"FFmpeg no soporta: {', '.join(sorted(missing))}")
                preflight = preflight_batch(
                    {path: probe_file(path) for path in self.forge_video_paths},
                    output_profile,
                    assume_unknown_sdr=bool(
                        getattr(self, "forge_iphone_assume_unknown_sdr", False)
                    ),
                )
            except Exception as error:
                return messagebox.showerror("Preflight iPhone", str(error))
            if preflight["blocked"]:
                details = "\n".join(f"{os.path.basename(path)}: {reason}"
                                    for path, reason in preflight["blocked"].items())
                return messagebox.showerror("Preflight iPhone: fuentes bloqueadas", details)
        fx_vals = {key: var.get() for key, var in self.forge_fx_vars.items()}
        fx_enabled = metadata_pool.efectos_to_enabled(self.forge_efectos_var.get(), fx_vals)
        fuerza_level = self.forge_fuerza_var.get()
        if fuerza_level == "Custom":
            forge_strength = metadata_pool.fuerza_to_strength("Custom", self.forge_strength_slider.get())
            forge_overrides = metadata_pool.parse_custom_ranges(
                {p: (mn.get(), mx.get()) for p, (mn, mx) in self.forge_range_entries.items()})
            fx_enabled["mirror"] = bool(self.forge_custom_mirror_var.get())
        else:
            forge_strength = metadata_pool.fuerza_to_strength(fuerza_level)
            forge_overrides = None
        active_fx = [lbl for key, lbl in self.FORGE_FX_DEFS if fx_enabled[key]]
        fx_desc = ", ".join(active_fx) if active_fx else (
            "ninguna (HEVC igualmente)" if output_profile else "ninguna (solo metadata, sin re-encode)")
        profile_desc = f"\nPerfil: {selected_profile} ({'MOV' if output_profile else 'formato original'})"
        if pending_retry:
            profile_desc += f"\nReintento: {len(pending_retry['pending'])} copia(s) pendiente(s), mismo número y metadata"
        if preflight:
            counts = preflight["counts"]
            profile_desc += (f"\nFuentes: SDR {counts['sdr']} / HLG {counts['hlg']} / "
                             f"desconocidas {counts['unknown']}")
            if preflight["assumptions"]:
                profile_desc += (f"\nWaveSpeed sin tags asumidos SDR: "
                                 f"{len(preflight['assumptions'])}")

        if not messagebox.askyesno("Confirmar Forge", (
            f"¿Generar {len(self.forge_video_paths)} vídeos × {copies} copias = {n_total} archivos con metadata iPhone única?\n\n"
            f"Tanda: {tanda_name}{' (TRIALS)' if is_trial_tanda else ''}\n"
            f"Rendimiento: {performance.workers} videos en paralelo\n"
            f"Micro-ediciones: {fx_desc}{profile_desc}"
        )):
            return

        videos    = self.forge_video_paths[:]
        meta_list = self.forge_meta_assignments[:]
        base_dir  = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(base_dir, "videos_finales", tanda_name)
        db_ref    = self.db

        self.btn_forge_process.configure(state="disabled")
        self.btn_forge_reshuffle.configure(state="disabled")
        self.forge_pb.configure(mode="indeterminate")
        self.forge_pb.start()
        self.forge_pb_lbl.configure(
            text=f"Procesando con FFmpeg ({performance.workers} videos en paralelo)...",
            text_color=WARNING,
        )

        def task():
            import re
            import metadata_pool
            if output_profile:
                from forge_iphone_profile import (next_copy_number, render_validated_copy,
                                                  validate_existing_copy)
            os.makedirs(output_dir, exist_ok=True)
            copy_jobs = []
            meta_idx = 0
            reserved_max = {}
            if pending_retry:
                for item in pending_retry["pending"]:
                    vid_path = item["source_path"]
                    if metadata_pool.get_video_hash(vid_path) != item["video_hash"]:
                        raise ValueError(
                            f"La fuente pendiente cambió desde el intento anterior: {os.path.basename(vid_path)}")
                    filename = os.path.basename(vid_path)
                    out_name = item["output_name"]
                    out_path = os.path.join(output_dir, out_name)
                    meta = item["meta"]
                    vh = item["video_hash"]
                    match = re.search(r"__c(\d+)\.mov$", out_name, re.I)
                    if not match:
                        raise ValueError(f"Nombre de copia pendiente inválido: {out_name}")
                    fingerprint = {"video_hash": f"{vh}_{int(match.group(1))}", **meta}
                    copy_jobs.append((vid_path, out_path, filename, out_name, vh, meta, fingerprint))
            for vid_path in ([] if pending_retry else videos):
                filename = os.path.basename(vid_path)
                base, ext = os.path.splitext(filename)
                vid_id = forge_output_id_from_filename(filename)
                vh = metadata_pool.get_video_hash(vid_path)
                if output_profile:
                    ext = ".mov"
                    existing_max = next_copy_number(output_dir, vid_id) - 1
                else:
                    existing_max = 0
                    copy_pattern = re.compile(rf"^{re.escape(vid_id)}__c(\d+){re.escape(ext)}$")
                    for fname in os.listdir(output_dir):
                        m = copy_pattern.match(fname)
                        if m:
                            existing_max = max(existing_max, int(m.group(1)))
                reservation_key = (vid_id, ext)
                existing_max = max(existing_max, reserved_max.get(reservation_key, 0))
                for offset in range(1, copies + 1):
                    copy_num = existing_max + offset
                    meta = meta_list[meta_idx]
                    out_name = f"{vid_id}__c{copy_num:02d}{ext}"
                    out_path = os.path.join(output_dir, out_name)
                    fingerprint = {"video_hash": f"{vh}_{copy_num}", **meta}
                    copy_jobs.append((vid_path, out_path, filename, out_name, vh, meta, fingerprint))
                    meta_idx += 1
                reserved_max[reservation_key] = existing_max + copies

            def process_copy(copy_job):
                vid_path, out_path, filename, out_name, vh, meta, fingerprint = copy_job
                try:
                    if output_profile:
                        if pending_retry and os.path.isfile(out_path):
                            params = validate_existing_copy(
                                vid_path, out_path, meta, output_profile,
                                preflight["sources"][vid_path])
                            params["recovered_published_copy"] = True
                        else:
                            params = render_validated_copy(
                                vid_path, out_path, meta, output_profile,
                                preflight["sources"][vid_path], enabled=fx_enabled,
                                strength=forge_strength, overrides=forge_overrides,
                                threads=performance.ffmpeg_threads,
                            )
                        params.update({"output_profile": output_profile,
                                       "source_color": preflight["sources"][vid_path],
                                       "source_color_assumption": preflight["assumptions"].get(vid_path),
                                       "output_color": "hlg" if output_profile == "iphone_hlg" else "sdr",
                                       "output_codec": "hevc", "output_container": "mov"})
                    else:
                        params = metadata_pool.apply_variant_and_metadata(
                            vid_path, out_path, meta,
                            enabled=fx_enabled, strength=forge_strength,
                            overrides=forge_overrides,
                            ffmpeg_threads=performance.ffmpeg_threads,
                        )
                except Exception as error:
                    raise RuntimeError(f"Forge falló en '{filename}': {error}") from error
                return filename, out_name, vh, fingerprint, vid_path, out_path, meta, params

            if output_profile:
                processing_status = {
                    "state": "processing", "profile": output_profile,
                    "expected_count": (pending_retry.get("expected_count", len(copy_jobs))
                                       if pending_retry else
                                       len(copy_jobs) + len((prior_status or {}).get("validated", []))),
                    "validated": (prior_status or {}).get("validated", []),
                    "pending": [
                        {"source_path": job[0], "output_name": job[3],
                         "video_hash": job[4], "meta": job[5]}
                        for job in copy_jobs
                    ],
                }
                with open(status_path + ".tmp", "w", encoding="utf-8") as status_file:
                    json.dump(processing_status, status_file, ensure_ascii=False, indent=2)
                os.replace(status_path + ".tmp", status_path)

            with ThreadPoolExecutor(max_workers=performance.workers) as pool:
                futures = [pool.submit(process_copy, copy_job) for copy_job in copy_jobs]
                if output_profile:
                    completed = []
                    failures = []
                    for copy_job, future in zip(copy_jobs, futures):
                        try:
                            completed.append(future.result())
                        except Exception as error:
                            failures.append((copy_job[3], str(error)))
                else:
                    completed = [future.result() for future in futures]
                    failures = []

            process_kind = "forge_trial" if is_trial_tanda else "forge"
            for filename, out_name, vh, fingerprint, vid_path, out_path, meta, params in completed:
                db_ref.save_forge_video(tanda_name, filename, out_name, vh)
                _save_forge_transform_log(
                    db_ref,
                    process_kind=process_kind,
                    source_path=vid_path,
                    output_path=out_path,
                    tanda_name=tanda_name,
                    source_identity=fingerprint.get("video_hash", ""),
                    params=params,
                    meta=meta,
                )
            if completed:
                db_ref.save_metadata_fingerprints([
                    fingerprint for _filename, _out_name, _vh, fingerprint, *_rest in completed
                ])
                existing_tanda = db_ref.get_tanda_by_name(tanda_name) or {}
                db_ref.add_tanda(
                    tanda_name, tanda_name, tanda_name, existing_tanda.get("captions_file_path")
                )
                db_ref.set_tanda_trial(tanda_name, is_trial_tanda)

            if output_profile:
                failed_names = {name for name, _error in failures}
                pending_records = [
                    {"source_path": vid_path, "output_name": out_name,
                     "video_hash": vh, "meta": meta, "error": next(
                         error for name, error in failures if name == out_name)}
                    for vid_path, _out_path, _filename, out_name, vh, meta, _fingerprint in copy_jobs
                    if out_name in failed_names
                ]
                status = {
                    "state": "incomplete" if failures else "complete",
                    "profile": output_profile,
                    "expected_count": pending_retry.get("expected_count", len(copy_jobs))
                    if pending_retry else len(copy_jobs) + len((prior_status or {}).get("validated", [])),
                    "validated": (((prior_status or {}).get("validated", [])) +
                                  [item[1] for item in completed]),
                    "pending": pending_records,
                }
                temp_status_path = status_path + ".tmp"
                with open(temp_status_path, "w", encoding="utf-8") as status_file:
                    json.dump(status, status_file, ensure_ascii=False, indent=2)
                os.replace(temp_status_path, status_path)

            if failures:
                details = "\n".join(f"{name}: {error}" for name, error in failures)
                return (f"⚠️ Tanda incompleta: {len(completed)}/{len(copy_jobs)} copias validadas y registradas en este intento; "
                        f"{len(failures)} fallidas. No uses la tanda completa hasta reintentar.\n{details}")

            msg = (
                f"✅ Tanda completada: {len(copy_jobs)} archivos generados o reintentados.\n"
                f"📁 Guardados en: videos_finales/{tanda_name}/\n"
                f"🔮 Tanda '{tanda_name}' registrada en la DB."
            )
            return msg

        def done(success, result):
            self.btn_forge_process.configure(state="normal")
            self.btn_forge_reshuffle.configure(state="normal")
            self.forge_pb.stop()
            self.forge_pb.configure(mode="determinate")
            self.forge_pb.set(1 if success else 0)
            if success and isinstance(result, str) and result.startswith("⚠️ Tanda incompleta"):
                self.forge_pb_lbl.configure(text="⚠️ Tanda incompleta", text_color=WARNING)
                messagebox.showwarning("Forge incompleto", result)
            elif success:
                self.forge_pb_lbl.configure(text="✅ Completado", text_color=SUCCESS)
                messagebox.showinfo("✅ Forge completado", result)
                self.reload_dist_lists()
                self.refresh_dashboard()
            else:
                self.forge_pb_lbl.configure(text="❌ Error — revisá la consola", text_color=DANGER)
                messagebox.showerror("Error en Forge", result)

        WorkerThread(self, done, task).start()


# ══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════
    def _trial_refresh_account_rows(self):
        for widget in self.trial_account_scroll.winfo_children():
            widget.destroy()
        active_accounts = self.db.get_trials_active_accounts()
        trial_tandas = self.db.get_trial_tandas()
        self.trial_account_vars = {}
        self.trial_account_panel_frames = {}
        self.trial_expanded_accounts = set()
        self.trial_caption_editors = {}
        self.trial_thumbnail_images = []
        for account in active_accounts:
            username = account["username"]
            row = ctk.CTkFrame(self.trial_account_scroll, fg_color=BG_CARD)
            row.pack(fill="x", padx=4, pady=4)
            header = ctk.CTkFrame(row, fg_color="transparent")
            header.pack(fill="x", padx=8, pady=6)
            ctk.CTkLabel(
                header, text=f"@{username} [{account.get('account_type', '')}]",
                text_color=TEXT_BODY, width=230, anchor="w",
            ).pack(side="left", padx=8, pady=6)
            var = tk.StringVar(value="")
            combo = ctk.CTkComboBox(
                header, values=[""] + trial_tandas, variable=var,
                fg_color=BG_INPUT, border_color=BORDER, width=280,
                command=lambda _value, u=username: self._trial_on_account_tanda_changed(u),
            )
            combo.pack(side="left", padx=8, pady=6)
            GhostButton(
                header, text="Desplegar panel de trials",
                command=lambda u=username: self._trial_toggle_account_panel(u),
            ).pack(side="left", padx=8, pady=6)
            panel = ctk.CTkFrame(row, fg_color=BG_CARD2)
            self.trial_account_panel_frames[username] = panel
            self.trial_account_vars[username] = var
        self.trial_accounts_lbl.configure(text=f"{len(active_accounts)} cuentas con TRIALS ACTIVOS")

    def _trial_selected_assignments(self):
        return {
            username: variable.get().strip()
            for username, variable in self.trial_account_vars.items()
            if variable.get().strip()
        }

    def _trial_load_thumbnail(self, label, video_path):
        def task():
            cache = trial_preview_path(video_path)
            if not cache.exists():
                cache.parent.mkdir(parents=True, exist_ok=True)
                from video_editor import render_preview
                render_preview(str(video_path), [], str(cache), timestamp=0.1)
            return cache

        def done(success, result):
            if not success:
                label.configure(text="Sin preview")
                return
            try:
                from PIL import Image
                image = Image.open(result).convert("RGB")
                image.thumbnail((120, 68), Image.Resampling.LANCZOS)
                preview = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                self.trial_thumbnail_images.append(preview)
                label.configure(image=preview, text="")
            except Exception:
                label.configure(text="Sin preview")

        WorkerThread(self, done, task).start()

    def _trial_dist_run(self, preview_only):
        return self._trial_dist_run_per_account(preview_only)

    def _acct_on_caption_mode_change(self, _value=None):
        self._acct_update_individual_captions_button()

    def _acct_update_individual_captions_button(self):
        if not hasattr(self, "acct_individual_captions_btn"):
            return
        enabled = bool(self._acct_individual_caption_tandas())
        self.acct_individual_captions_btn.configure(state="normal" if enabled else "disabled")

    def _acct_normal_tanda_files(self, tanda=None):
        tanda = tanda or self.acct_dist_tanda.get().strip()
        folder = os.path.join(_BASE_DIR, "videos_finales", tanda)
        if not os.path.isdir(folder):
            return []
        return sorted(name for name in os.listdir(folder) if name.lower().endswith((".mp4", ".mov", ".avi")))

    def _acct_refresh_individual_captions(self):
        selected_tandas = self._acct_individual_caption_tandas()
        if not selected_tandas:
            return messagebox.showwarning("Captions individuales", "Marca al menos una tanda como Individual.")
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Captions individuales - {' + '.join(selected_tandas)}")
        self._fit_toplevel(dialog, 860, 680)
        dialog.configure(fg_color=BG_APP)
        scroll = ctk.CTkScrollableFrame(dialog, fg_color=BG_CARD2)
        scroll.pack(fill="both", expand=True, padx=16, pady=16)
        editors, previews = {}, []
        multi_tanda = len(selected_tandas) > 1
        for tanda in selected_tandas:
            captions = self.db.get_normal_source_captions(tanda)
            folder = os.path.join(_BASE_DIR, "videos_finales", tanda)
            for source_key, copies in group_trial_sources(self._acct_normal_tanda_files(tanda)):
                row = ctk.CTkFrame(scroll, fg_color=BG_CARD)
                row.pack(fill="x", padx=4, pady=4)
                preview_label = ctk.CTkLabel(row, text="Cargando preview", width=120, height=68)
                preview_label.pack(side="left", padx=8, pady=8)
                body = ctk.CTkFrame(row, fg_color="transparent")
                body.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=6)
                source_label = f"{tanda} / {source_key}" if multi_tanda else source_key
                ctk.CTkLabel(body, text=f"{source_label} ({len(copies)} copias)", text_color=TEXT_BODY).pack(anchor="w")
                editor = ctk.CTkTextbox(body, height=72, fg_color=BG_INPUT, border_color=BORDER, border_width=1)
                editor.pack(fill="x", pady=(2, 0))
                editor.insert("1.0", captions.get(source_key, ""))
                editors[(tanda, source_key)] = editor

                def load(label=preview_label, path=os.path.join(folder, copies[0])):
                    def task():
                        cache = trial_preview_path(path)
                        if not cache.exists():
                            cache.parent.mkdir(parents=True, exist_ok=True)
                            from video_editor import render_preview
                            render_preview(path, [], str(cache), timestamp=0.1)
                        return cache
                    def done(success, result):
                        if not success:
                            return label.configure(text="Sin preview")
                        try:
                            from PIL import Image
                            image = Image.open(result).convert("RGB")
                            image.thumbnail((120, 68), Image.Resampling.LANCZOS)
                            preview = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                            previews.append(preview)
                            label.configure(image=preview, text="")
                        except Exception:
                            label.configure(text="Sin preview")
                    WorkerThread(self, done, task).start()
                load()

        def save():
            missing = []
            for (tanda_name, source_key), editor in editors.items():
                text = editor.get("1.0", "end-1c").strip()
                if not text:
                    missing.append(f"{tanda_name}/{source_key}" if multi_tanda else source_key)
                self.db.set_normal_source_caption(tanda_name, source_key, text)
            if missing:
                return messagebox.showwarning("Captions individuales", "Falta caption: " + ", ".join(missing), parent=dialog)
            dialog.destroy()
            messagebox.showinfo("Captions individuales", "Captions guardados.")

        PrimaryButton(dialog, text="Guardar captions individuales", command=save).pack(pady=(0, 16))

    def _acct_missing_individual_captions(self, tanda):
        captions = self.db.get_normal_source_captions(tanda)
        return missing_trial_caption_sources(self._acct_normal_tanda_files(tanda), captions)


if __name__ == "__main__":
    app = InstagramAutoPro()
    app.mainloop()
