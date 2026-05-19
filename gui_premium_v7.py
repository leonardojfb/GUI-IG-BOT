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
import random
import time
import threading
from datetime import datetime, timedelta

import json
import shutil
import requests

from database import DatabaseManager

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ACCT_HIST_FILE = os.path.join(_BASE_DIR, "dist_accounts_history.json")
from styles.colors import (
    BG_APP, BG_SIDEBAR, BG_CARD, BG_CARD2, BG_INPUT, BORDER,
    NEON_CYAN, NEON_PURPLE, IG_PINK, SUCCESS, WARNING, DANGER, INFO,
    TEXT_H1, TEXT_BODY, TEXT_MUTED,
    FONT_TITLE, FONT_H2, FONT_H3, FONT_BODY, FONT_SMALL, FONT_MONO,
    SIDEBAR_W, STATUS_H, CARD_RADIUS, BTN_RADIUS, BTN_H, BTN_H_LG,
)

# ── Configuración global de CustomTkinter ──────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

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

MAX_PER_SESSION = 10
DELAY_MIN = 300    # 5 min
DELAY_MAX = 600    # 10 min

TIMEZONE_OPTIONS = [
    "America/Argentina/Buenos_Aires",
    "America/New_York",
    "America/Chicago",
    "America/Los_Angeles",
    "Europe/Madrid",
    "Europe/London",
]

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
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        ctk.CTkLabel(
            h, text="📡  Estado de Cuentas",
            font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT_H1
        ).pack(side="left")
        ctk.CTkLabel(
            h, text=f"Modo sigiloso · máx {MAX_PER_SESSION} cuentas/sesión · delay 5-10 min",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED
        ).pack(side="left", padx=(14, 0), anchor="s")

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

        ctk.CTkButton(
            card, text="💾 Guardar", fg_color=NEON_CYAN, text_color=BG_APP,
            corner_radius=BTN_RADIUS, height=BTN_H, width=110,
            font=ctk.CTkFont(size=12, weight="bold"), command=self._save_cfg
        ).grid(row=0, column=2, rowspan=2, padx=20, pady=16)

    def _build_controls(self):
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.grid(row=2, column=0, sticky="ew", padx=24, pady=10)
        ctrl.grid_columnconfigure(5, weight=1)

        self.btn_check = ctk.CTkButton(
            ctrl, text=f"▶  Verificar  (máx {MAX_PER_SESSION})",
            fg_color=SUCCESS, text_color="#000000",
            corner_radius=BTN_RADIUS, height=BTN_H,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.start_check
        )
        self.btn_check.grid(row=0, column=0, padx=(0, 8))

        self.btn_stop = ctk.CTkButton(
            ctrl, text="⏹  Detener",
            fg_color=DANGER, text_color=TEXT_H1,
            corner_radius=BTN_RADIUS, height=BTN_H,
            font=ctk.CTkFont(size=12, weight="bold"),
            state="disabled", command=self.stop_check
        )
        self.btn_stop.grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            ctrl, text="🔄 Reiniciar",
            fg_color=BG_CARD2, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER,
            corner_radius=BTN_RADIUS, height=BTN_H,
            font=ctk.CTkFont(size=12), command=self._reset_all_status
        ).grid(row=0, column=2, padx=(0, 8))

        ctk.CTkButton(
            ctrl, text="↺ Recargar lista",
            fg_color=BG_CARD2, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER,
            corner_radius=BTN_RADIUS, height=BTN_H,
            font=ctk.CTkFont(size=12), command=self.load_accounts
        ).grid(row=0, column=3, padx=(0, 20))

        self.lbl_progress = ctk.CTkLabel(ctrl, text="", text_color=TEXT_MUTED,
                                          font=ctk.CTkFont(size=11))
        self.lbl_progress.grid(row=0, column=4, padx=(0, 12))

        self.pb = ctk.CTkProgressBar(ctrl, fg_color=BG_INPUT, progress_color=NEON_CYAN, height=8)
        self.pb.grid(row=0, column=5, sticky="ew")
        self.pb.set(0)

    def _build_table_header(self):
        hdr = ctk.CTkFrame(self, fg_color=BG_CARD2, corner_radius=0, height=32)
        hdr.grid(row=3, column=0, sticky="ew", padx=24, pady=(4, 0))
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)

        cols = [
            ("Estado HTTP", 90,  "center"),
            ("Usuario",     0,   "w"),
            ("Etiqueta",    160, "center"),
            ("VA Asignado", 180, "w"),
            ("Tipo",        110, "center"),
        ]
        for i, (text, w, anchor) in enumerate(cols):
            if w == 0:
                hdr.grid_columnconfigure(i, weight=1)
            lbl = ctk.CTkLabel(
                hdr, text=text, text_color=NEON_CYAN,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor=anchor, width=w if w else 0
            )
            padx = (20, 8) if i == 0 else (8, 8)
            lbl.grid(row=0, column=i, padx=padx, pady=4, sticky="ew" if w == 0 else "")

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
        row.grid_columnconfigure(1, weight=1)

        circle_color = (
            SUCCESS   if status == "alive"
            else DANGER   if status == "dead"
            else "#64748b"
        )
        circle = ctk.CTkLabel(
            row, text="⬤", text_color=circle_color,
            font=ctk.CTkFont(size=18), width=90, anchor="center"
        )
        circle.grid(row=0, column=0, padx=(20, 8), pady=8)

        ctk.CTkLabel(
            row, text=f"@{username}", text_color=TEXT_BODY,
            font=ctk.CTkFont(size=12), anchor="w"
        ).grid(row=0, column=1, padx=8, pady=8, sticky="ew")

        combo = ctk.CTkComboBox(
            row, values=LABEL_OPTIONS,
            fg_color=BG_INPUT, border_color=BORDER,
            button_color=NEON_PURPLE, dropdown_fg_color=BG_CARD2,
            width=150, state="readonly",
            command=lambda val, u=username: self._on_label_change(u, val)
        )
        combo.set(label_val)
        combo.grid(row=0, column=2, padx=8, pady=6)

        # Indicador de color según etiqueta
        label_dot = ctk.CTkLabel(
            row, text="⬤",
            text_color=LABEL_COLORS.get(label_val, "#64748b"),
            font=ctk.CTkFont(size=10), width=16
        )
        label_dot.grid(row=0, column=2, padx=(8, 0), pady=8, sticky="e")

        ctk.CTkLabel(
            row, text=va, text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11), width=180, anchor="w"
        ).grid(row=0, column=3, padx=(8, 8), pady=8, sticky="w")

        ctk.CTkLabel(
            row, text=acc_type, text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11), width=110, anchor="center"
        ).grid(row=0, column=4, padx=(8, 20), pady=8)

        self._rows[username] = {"circle": circle, "combo": combo, "dot": label_dot}

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



# ══════════════════════════════════════════════════════════════════════════════
# APLICACIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
class InstagramAutoPro(ctk.CTk):

    # ── Init ──────────────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()
        self.title("⚡ Instagram Automation Pro  —  V7")
        self.geometry("1400x860")
        self.minsize(1100, 700)
        self.configure(fg_color=BG_APP)

        self.db = DatabaseManager()
        self._active_nav = None

        # Estado de rutas (Tandas)
        self.p1_dir = ""
        self.p2_dir = ""
        self.cap_file = ""
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

    def _setup_treeview_style(self):
        """Aplica tema oscuro premium al ttk.Treeview estándar."""
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Premium.Treeview",
                        background=BG_CARD2, foreground=TEXT_BODY,
                        fieldbackground=BG_CARD2, rowheight=28,
                        font=FONT_BODY, borderwidth=0)
        style.configure("Premium.Treeview.Heading",
                        background=BG_CARD, foreground=NEON_CYAN,
                        font=FONT_H3, borderwidth=0, relief="flat")
        style.map("Premium.Treeview",
                  background=[("selected", NEON_PURPLE)],
                  foreground=[("selected", TEXT_H1)])

    # ── Sidebar ───────────────────────────────────────────────────────────
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self, width=SIDEBAR_W, corner_radius=0,
            fg_color=BG_SIDEBAR, border_width=1, border_color=BORDER
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)
        self.sidebar.grid_propagate(False)

        # — Logo —
        logo_wrap = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_wrap.grid(row=0, column=0, padx=18, pady=(22, 8), sticky="ew")
        ctk.CTkLabel(logo_wrap, text="⚡ IG AUTO",
                     font=ctk.CTkFont(family="Arial", size=21, weight="bold"),
                     text_color=NEON_CYAN).pack(anchor="w")
        ctk.CTkLabel(logo_wrap, text="PRO  ·  v7.0",
                     font=ctk.CTkFont(family="Arial", size=10),
                     text_color=TEXT_MUTED).pack(anchor="w")

        # — Separador —
        ctk.CTkFrame(self.sidebar, height=1, fg_color=BORDER).grid(
            row=1, column=0, sticky="ew", padx=16, pady=(4, 8))

        # — Botones de navegación —
        nav_items = [
            ("📊   Dashboard",  "Dashboard"),
            ("⚙️   Admin",      "Equipo"),
            ("🎬   Tandas",     "Tandas"),
            ("🚀   Logística",  "Logistica"),
            ("📲   Telegram",   "Telegram"),
            ("📡   Cuentas",    "Cuentas"),
            ("🤖   AI Advisor",  "AIAdvisor"),
            ("🔮   Forge",       "Forge"),
        ]
        self._nav_btns = {}
        for i, (label, key) in enumerate(nav_items):
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                height=42, corner_radius=BTN_RADIUS,
                font=ctk.CTkFont(family="Arial", size=13),
                fg_color="transparent", text_color=TEXT_BODY,
                hover_color=BG_CARD2, border_width=0,
                command=lambda k=key: self.show_frame(k)
            )
            btn.grid(row=i + 2, column=0, padx=10, pady=2, sticky="ew")
            self._nav_btns[key] = btn

        # — Status del bot (parte inferior sidebar) —
        ctk.CTkFrame(self.sidebar, height=1, fg_color=BORDER).grid(
            row=10, column=0, sticky="ew", padx=16, pady=(8, 4))
        self.lbl_bot_status = ctk.CTkLabel(
            self.sidebar, text="⬤  Bot inactivo",
            font=ctk.CTkFont(size=11), text_color=TEXT_MUTED)
        self.lbl_bot_status.grid(row=11, column=0, padx=18, pady=(0, 18), sticky="sw")

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

        for name in ["Dashboard", "Equipo", "Tandas", "Logistica", "Telegram", "Cuentas", "AIAdvisor", "Forge"]:
            f = ctk.CTkFrame(container, fg_color=BG_APP, corner_radius=0)
            f.grid(row=0, column=0, sticky="nsew")
            self._frames[name] = f

        # Construir contenido de cada frame
        self._build_dashboard_frame()
        self._build_team_frame()
        self._build_mix_frame()
        self._build_dist_frame()
        self._build_tg_frame()
        self._build_cuentas_frame()
        self._build_ai_frame()
        self._build_forge_frame()

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
            self._nav_btns[self._active_nav].configure(
                fg_color="transparent", text_color=TEXT_BODY)
        if name in self._nav_btns:
            self._nav_btns[name].configure(
                fg_color=BG_CARD2, text_color=NEON_CYAN)
        self._active_nav = name
        self._frames[name].tkraise()
        if name == "Cuentas" and hasattr(self, "_cuentas_panel"):
            self._cuentas_panel.refresh()
        if name == "Tandas" and hasattr(self, "_tandas_list_scroll"):
            self._refresh_tandas_list()

    # ── Reloj ─────────────────────────────────────────────────────────────
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
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure(0, weight=1)

        # ── Header ──────────────────────────────────────────────────────
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        header.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(header, text="📊  Dashboard",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TEXT_H1).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Vista en tiempo real de todas las cuentas",
                     font=ctk.CTkFont(size=12), text_color=TEXT_MUTED
                     ).grid(row=1, column=0, sticky="w")

        # ── KPI Cards ───────────────────────────────────────────────────
        kpi_row = ctk.CTkFrame(f, fg_color="transparent")
        kpi_row.grid(row=0, column=0, sticky="ew", padx=24, pady=(60, 0))

        self.kpi_cuentas = self._make_kpi_card(kpi_row, "📱", "Cuentas", "0", NEON_CYAN, 0)
        self.kpi_videos  = self._make_kpi_card(kpi_row, "🎬", "Videos Enviados", "0", NEON_PURPLE, 1)
        self.kpi_vas     = self._make_kpi_card(kpi_row, "👥", "VAs Activos", "0", SUCCESS, 2)

        # ── Área Central (Tabla) ─────────────────────────────────────────
        center_row = ctk.CTkFrame(f, fg_color="transparent")
        center_row.grid(row=1, column=0, sticky="nsew", padx=24, pady=(14, 0))
        center_row.grid_rowconfigure(0, weight=1)
        center_row.grid_columnconfigure(0, weight=1)

        # ── Tabla ───────────────────────────────────────────────────────
        table_frame = ctk.CTkFrame(center_row, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        table_frame.grid(row=0, column=0, sticky="nsew")
        table_frame.grid_rowconfigure(1, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Sub-header de tabla con buscador
        th = ctk.CTkFrame(table_frame, fg_color="transparent")
        th.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        th.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(th, text="Cuentas registradas",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT_BODY).grid(row=0, column=0, sticky="w")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_tree())
        srch = ctk.CTkEntry(th, textvariable=self.search_var, width=200,
                            placeholder_text="🔍 Buscar cuenta...",
                            fg_color=BG_INPUT, border_color=BORDER)
        srch.grid(row=0, column=2, sticky="e")

        # Treeview
        cols = ("VA", "Telegram ID", "Cuenta IG", "Categoría", "Videos", "Fecha")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                  style="Premium.Treeview", height=16)
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
        self.tree.tag_configure("odd",  background=BG_CARD2)
        self.tree.tag_configure("even", background=BG_CARD)

        # ── Botones de acción ────────────────────────────────────────────
        btn_bar = ctk.CTkFrame(f, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="ew", padx=24, pady=(10, 16))

        btn_cfg = [
            ("📁  Cambiar Categoría", IG_PINK,    self.change_account_category),
            ("👤  Reasignar VA",      INFO,        self.reassign_va),
            ("🗑️  Eliminar",          DANGER,      self.delete_account),
            ("🔄  Actualizar",        NEON_CYAN,   self.refresh_dashboard),
        ]
        for label, color, cmd in btn_cfg:
            ctk.CTkButton(btn_bar, text=label, fg_color=color,
                          hover_color=self._darken(color),
                          text_color=BG_APP if color == NEON_CYAN else TEXT_H1,
                          height=BTN_H, corner_radius=BTN_RADIUS,
                          font=ctk.CTkFont(size=12, weight="bold"),
                          command=cmd).pack(side="left", padx=(0, 8))

        self.refresh_dashboard()

    # ── KPI Card helper ───────────────────────────────────────────────────────
    def _make_kpi_card(self, parent, icon, label, value, accent, col):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=CARD_RADIUS,
                            border_width=1, border_color=BORDER)
        card.grid(row=0, column=col, padx=(0, 12), sticky="ew")
        parent.grid_columnconfigure(col, weight=1)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=18, pady=14)

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

    def _darken(self, hex_color: str) -> str:
        """Devuelve una versión ligeramente más oscura del color."""
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        factor = 0.75
        return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"

    # ── Lógica Dashboard ─────────────────────────────────────────────────────
    def refresh_dashboard(self):
        """Recarga la tabla y actualiza KPIs."""
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

        # KPIs
        self.kpi_cuentas.configure(text=str(len(accounts)))
        self.kpi_videos.configure(text=str(total_videos))
        self.kpi_vas.configure(text=str(len(self.db.get_vas())))

        # Sincronizar combos en otras pestañas
        self._admin_refresh()
        if hasattr(self, "c_tandas"):
            self.reload_dist_lists()

        # Auto-refresh en 30 segundos
        self.after(30000, self.refresh_dashboard)

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

    def get_selected_account(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("⚠️", "Selecciona una cuenta en la tabla.")
            return None
        return self.tree.item(sel[0])["values"][2].lstrip("@")

    def change_account_category(self):
        username = self.get_selected_account()
        if not username:
            return
        dialog = SelectionDialog(self, "Cambiar Categoría",
                                 f"Nueva categoría para @{username}",
                                 self.db.get_categories())
        self.wait_window(dialog)
        if dialog.result:
            cat = dialog.result.upper()
            self.db.add_category(cat)
            self.db.update_account(username, account_type=cat)
            self.refresh_dashboard()
            messagebox.showinfo("✅", "Categoría actualizada.")

    def reassign_va(self):
        username = self.get_selected_account()
        if not username:
            return
        dialog = SelectionDialog(self, "Reasignar VA",
                                 f"Asignar VA para @{username}",
                                 self.db.get_vas())
        self.wait_window(dialog)
        if dialog.result:
            self.db.add_va(dialog.result)
            self.db.update_account(username, assigned_va=dialog.result)
            self.refresh_dashboard()
            messagebox.showinfo("✅", "VA actualizado.")

    def delete_account(self):
        username = self.get_selected_account()
        if username and messagebox.askyesno(
                "Confirmar", f"¿Eliminar la cuenta @{username}?"):
            self.db.delete_account(username)
            self.refresh_dashboard()

    def _sort_tree(self, tv, col, reverse):
        items = [(tv.set(k, col), k) for k in tv.get_children("")]
        items.sort(key=lambda x: (0, float(x[0])) if x[0].isdigit() else (1, x[0].lower()),
                   reverse=reverse)
        for idx, (_, k) in enumerate(items):
            tv.move(k, "", idx)
            tv.item(k, tags=("even" if idx % 2 == 0 else "odd",))
        tv.heading(col, command=lambda: self._sort_tree(tv, col, not reverse))

    def _build_team_frame(self):
        """Panel Admin — VAs / Cuentas / Categorías en 3 columnas."""
        f = self._frames["Equipo"]
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure((0, 1, 2), weight=1)

        # ── Header ──────────────────────────────────────────────────────
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=24, pady=(20, 10))
        ctk.CTkLabel(header, text="⚙️  Admin — VAs · Cuentas · Categorías",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TEXT_H1).grid(row=0, column=0, sticky="w")

        # ── Columna 0: VAs ───────────────────────────────────────────────
        col0 = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        col0.grid(row=1, column=0, sticky="nsew", padx=(24, 8), pady=(0, 24))
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
        ctk.CTkButton(va_form, text="➕ Guardar VA", fg_color=SUCCESS,
                      hover_color=self._darken(SUCCESS), text_color=BG_APP,
                      corner_radius=BTN_RADIUS, height=BTN_H,
                      font=ctk.CTkFont(weight="bold"),
                      command=self.add_va_ui).grid(row=4, column=0, sticky="ew")

        # ── Columna 1: Cuentas ───────────────────────────────────────────
        col1 = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        col1.grid(row=1, column=1, sticky="nsew", padx=8, pady=(0, 24))
        col1.grid_rowconfigure(1, weight=1)
        col1.grid_columnconfigure(0, weight=1)

        self._acc_header_lbl = ctk.CTkLabel(
            col1, text="📱  Cuentas (0)",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=NEON_PURPLE)
        self._acc_header_lbl.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        self._acc_scroll = ctk.CTkScrollableFrame(col1, fg_color="transparent")
        self._acc_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self._acc_scroll.grid_columnconfigure(0, weight=1)

        bulk_form = ctk.CTkFrame(col1, fg_color="transparent")
        bulk_form.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 16))
        bulk_form.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(bulk_form, text="Agregar cuentas (una por línea):",
                     text_color=TEXT_MUTED, font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        self.txt_accounts = ctk.CTkTextbox(bulk_form, fg_color=BG_INPUT, border_color=BORDER,
                                            border_width=1, height=70)
        self.txt_accounts.grid(row=1, column=0, sticky="ew", pady=(2, 6))

        ba_ctrl = ctk.CTkFrame(bulk_form, fg_color="transparent")
        ba_ctrl.grid(row=2, column=0, sticky="ew")
        ba_ctrl.grid_columnconfigure((1, 3), weight=1)
        ctk.CTkLabel(ba_ctrl, text="Cat:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0, 4))
        self.c_bulk_cat = ctk.CTkComboBox(ba_ctrl, values=[], fg_color=BG_INPUT, border_color=BORDER)
        self.c_bulk_cat.grid(row=0, column=1, padx=(0, 8), sticky="ew")
        ctk.CTkLabel(ba_ctrl, text="VA:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=(0, 4))
        self.c_bulk_va = ctk.CTkComboBox(ba_ctrl, values=[], fg_color=BG_INPUT, border_color=BORDER)
        self.c_bulk_va.grid(row=0, column=3, sticky="ew")

        ctk.CTkButton(bulk_form, text="🚀 Cargar cuentas", fg_color=IG_PINK,
                      hover_color=self._darken(IG_PINK), text_color=TEXT_H1,
                      corner_radius=BTN_RADIUS, height=BTN_H,
                      font=ctk.CTkFont(weight="bold"),
                      command=self.add_bulk_accounts).grid(row=3, column=0, sticky="ew", pady=(6, 0))

        # ── Columna 2: Categorías ────────────────────────────────────────
        col2 = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        col2.grid(row=1, column=2, sticky="nsew", padx=(8, 24), pady=(0, 24))
        col2.grid_rowconfigure(1, weight=1)
        col2.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(col2, text="🏷️  Categorías",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=WARNING).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        self._cat_scroll = ctk.CTkScrollableFrame(col2, fg_color="transparent")
        self._cat_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self._cat_scroll.grid_columnconfigure(0, weight=1)

        cat_form = ctk.CTkFrame(col2, fg_color="transparent")
        cat_form.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 16))
        cat_form.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cat_form, text="Nombre:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        self.e_cat_new = ctk.CTkEntry(cat_form, fg_color=BG_INPUT, border_color=BORDER)
        self.e_cat_new.grid(row=1, column=0, sticky="ew", pady=(2, 8))
        ctk.CTkButton(cat_form, text="➕ Agregar", fg_color=WARNING,
                      hover_color=self._darken(WARNING), text_color=BG_APP,
                      corner_radius=BTN_RADIUS, height=BTN_H,
                      font=ctk.CTkFont(weight="bold"),
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

            # Dropdown de timezone
            tz_var = tk.StringVar(value=tz)
            tz_menu = ctk.CTkOptionMenu(
                r, values=TIMEZONE_OPTIONS, variable=tz_var, width=180,
                fg_color=BG_CARD2, button_color=BG_CARD2, text_color=TEXT_BODY,
                command=lambda new_tz, n=name: self._admin_save_va_tz(n, new_tz),
            )
            tz_menu.grid(row=0, column=2, padx=(4, 4))

            ctk.CTkButton(r, text="TG", width=36, height=26, corner_radius=4,
                          fg_color=BG_CARD2, text_color=TEXT_MUTED,
                          hover_color=BORDER,
                          command=lambda n=name, t=tg: self._admin_edit_va_tg(n, t)
                          ).grid(row=0, column=3, padx=(2, 2))
            ctk.CTkButton(r, text="×", width=28, height=26, corner_radius=4,
                          fg_color=DANGER, text_color=TEXT_H1,
                          hover_color=self._darken(DANGER),
                          command=lambda n=name: self._admin_delete_va(n)
                          ).grid(row=0, column=4, padx=(2, 0))

    def _admin_load_accounts(self):
        for w in self._acc_scroll.winfo_children():
            w.destroy()
        accounts  = self.db.get_all_accounts()
        vas_list  = ["Sin Asignar"] + self.db.get_vas()
        cats_list = self.db.get_categories() or ["GENERAL"]
        self._acc_header_lbl.configure(text=f"📱  Cuentas ({len(accounts)})")
        for acc in accounts:
            username = acc["username"]
            acc_type = acc.get("account_type", "GENERAL")
            assigned = acc.get("assigned_va") or "Sin Asignar"
            r = ctk.CTkFrame(self._acc_scroll, fg_color="transparent")
            r.pack(fill="x", pady=2, padx=4)
            r.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(r, text=f"@{username}", text_color=TEXT_BODY,
                         font=ctk.CTkFont(size=11), anchor="w").grid(row=0, column=0, sticky="w")
            c_type = ctk.CTkOptionMenu(
                r, values=cats_list, width=110, height=26,
                fg_color=BG_INPUT, button_color=BG_CARD2, button_hover_color=BORDER,
                text_color=TEXT_BODY, font=ctk.CTkFont(size=11),
                command=lambda v, u=username: self.db.update_account(u, account_type=v)
            )
            c_type.set(acc_type if acc_type in cats_list else cats_list[0])
            c_type.grid(row=0, column=1, padx=(4, 2))
            c_va = ctk.CTkOptionMenu(
                r, values=vas_list, width=110, height=26,
                fg_color=BG_INPUT, button_color=BG_CARD2, button_hover_color=BORDER,
                text_color=TEXT_BODY, font=ctk.CTkFont(size=11),
                command=lambda v, u=username: self.db.update_account(u, assigned_va=v)
            )
            c_va.set(assigned if assigned in vas_list else vas_list[0])
            c_va.grid(row=0, column=2, padx=(2, 2))
            ctk.CTkButton(r, text="×", width=28, height=26, corner_radius=4,
                          fg_color=DANGER, text_color=TEXT_H1,
                          hover_color=self._darken(DANGER),
                          command=lambda u=username: self._admin_delete_account(u)
                          ).grid(row=0, column=3, padx=(2, 0))

    def _admin_load_cats(self):
        for w in self._cat_scroll.winfo_children():
            w.destroy()
        for cat in self.db.get_categories():
            r = ctk.CTkFrame(self._cat_scroll, fg_color="transparent")
            r.pack(fill="x", pady=2, padx=4)
            r.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(r, text=cat, text_color=TEXT_BODY,
                         font=ctk.CTkFont(size=12), anchor="w").grid(row=0, column=0, sticky="w")
            ctk.CTkButton(r, text="×", width=28, height=26, corner_radius=4,
                          fg_color=DANGER, text_color=TEXT_H1,
                          hover_color=self._darken(DANGER),
                          command=lambda c=cat: self._admin_delete_cat(c)
                          ).grid(row=0, column=1, padx=(4, 0))

    def _admin_refresh(self):
        if hasattr(self, "_va_scroll"):
            self._admin_load_vas()
        if hasattr(self, "_acc_scroll"):
            self._admin_load_accounts()
        if hasattr(self, "_cat_scroll"):
            self._admin_load_cats()
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

    def _admin_save_va_tz(self, va_name: str, timezone: str):
        """Guarda el timezone seleccionado en el dropdown de una VA."""
        self.db.set_va_timezone(va_name, timezone)

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

    def _build_mix_frame(self):
        """TAREA 4 — Creador de Tandas."""
        f = self._frames["Tandas"]
        f.grid_rowconfigure(2, weight=1)
        f.grid_columnconfigure((0, 1), weight=1)

        # ── Header ──────────────────────────────────────────────────────
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 10))
        ctk.CTkLabel(header, text="🎬  Creador de Tandas",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TEXT_H1).grid(row=0, column=0, sticky="w")

        # ── Configuración Tanda ─────────────────────────────────────────
        top_card = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        top_card.grid(row=1, column=0, columnspan=2, sticky="ew", padx=24, pady=10)
        
        ctk.CTkLabel(top_card, text="Nombre/ID de la Tanda:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(weight="bold")).pack(side="left", padx=20, pady=20)
        self.e_tanda_name = ctk.CTkEntry(top_card, fg_color=BG_INPUT, border_color=BORDER, width=300)
        self.e_tanda_name.pack(side="left", padx=10, pady=20)

        # ── P1 y P2 (Paneles scrollables) ───────────────────────────────
        self.f_p1 = ctk.CTkScrollableFrame(f, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        self.f_p1.grid(row=2, column=0, sticky="nsew", padx=(24, 12), pady=10)
        
        ctk.CTkButton(self.f_p1, text="📂 Buscar Carpeta P1 (Inicio)", fg_color=NEON_PURPLE,
                      hover_color=self._darken(NEON_PURPLE), font=ctk.CTkFont(weight="bold"),
                      command=lambda: self.pick_folder(1)).pack(pady=10, padx=10, fill="x")
        self.lbl_p1_count = ctk.CTkLabel(self.f_p1, text="0 videos", text_color=TEXT_MUTED)
        self.lbl_p1_count.pack()
        
        self.f_p2 = ctk.CTkScrollableFrame(f, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        self.f_p2.grid(row=2, column=1, sticky="nsew", padx=(12, 24), pady=10)
        
        ctk.CTkButton(self.f_p2, text="📂 Buscar Carpeta P2 (Cierre)", fg_color=NEON_CYAN,
                      text_color=BG_APP, hover_color=self._darken(NEON_CYAN), font=ctk.CTkFont(weight="bold"),
                      command=lambda: self.pick_folder(2)).pack(pady=10, padx=10, fill="x")
        self.lbl_p2_count = ctk.CTkLabel(self.f_p2, text="0 videos", text_color=TEXT_MUTED)
        self.lbl_p2_count.pack()

        # ── Controles Inferiores ────────────────────────────────────────
        bot_card = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        bot_card.grid(row=3, column=0, columnspan=2, sticky="ew", padx=24, pady=(10, 24))
        
        ctk.CTkButton(bot_card, text="📄 Archivo Captions (.txt)", fg_color=WARNING, text_color=BG_APP,
                      hover_color=self._darken(WARNING), font=ctk.CTkFont(weight="bold"),
                      command=self.pick_captions).pack(side="left", padx=20, pady=20)
        
        self.lbl_cap = ctk.CTkLabel(bot_card, text="Ningún archivo seleccionado", text_color=TEXT_MUTED)
        self.lbl_cap.pack(side="left", padx=10)
        
        self.btn_render = ctk.CTkButton(bot_card, text="⚙️ INICIAR RENDER", fg_color=SUCCESS,
                                        text_color=BG_APP, hover_color=self._darken(SUCCESS),
                                        font=ctk.CTkFont(size=14, weight="bold"), height=BTN_H_LG,
                                        command=self.process_tanda)
        self.btn_render.pack(side="right", padx=20, pady=20)

        # ── Lista de Tandas registradas ─────────────────────────────────
        tandas_card = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        tandas_card.grid(row=4, column=0, columnspan=2, sticky="ew", padx=24, pady=(0, 24))
        tandas_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tandas_card, text="📋  Tandas registradas",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 6))

        self._tandas_list_scroll = ctk.CTkScrollableFrame(
            tandas_card, fg_color="transparent", height=140)
        self._tandas_list_scroll.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 12))
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

    def pick_captions(self):
        path = filedialog.askopenfilename(filetypes=[("Archivos de Texto", "*.txt")])
        if path:
            self.cap_file = path
            self.lbl_cap.configure(text=os.path.basename(path), text_color=NEON_CYAN)

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
            ctk.CTkButton(
                r, text="×", width=28, height=26, corner_radius=4,
                fg_color=DANGER, text_color=TEXT_H1,
                hover_color=self._darken(DANGER),
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
        if not name or not self.p1_dir or not self.p2_dir or not self.cap_file:
            return messagebox.showwarning("⚠️", "Asegúrate de llenar el nombre, seleccionar P1, P2 y Captions.")

        self.db.add_tanda(name, self.p1_dir, self.p2_dir, self.cap_file)
        self._refresh_tandas_list()
        self.reload_dist_lists()

        def task():
            import videos
            return videos.render_tanda(name)
            
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
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="🚀  Logística y Distribución",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TEXT_H1).grid(row=0, column=0, sticky="w")

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

        self._build_dist_tandas_tab(t1)
        self._build_dist_cuentas_tab(t2)

        # Cargar datos iniciales
        self.reload_dist_lists()

    def _build_dist_tandas_tab(self, parent):
        """Contenido del tab Por Tandas (lógica original)."""
        parent.grid_columnconfigure((1, 3), weight=1)

        # Fila 0: Tandas y Categorías
        ctk.CTkLabel(parent, text="Tanda principal:", text_color=TEXT_MUTED).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="e")
        self.c_tandas = ctk.CTkComboBox(parent, values=[], fg_color=BG_INPUT, border_color=BORDER)
        self.c_tandas.grid(row=0, column=1, padx=10, pady=(20, 10), sticky="ew")

        ctk.CTkLabel(parent, text="2da tanda (opcional):", text_color=TEXT_MUTED).grid(row=0, column=2, padx=20, pady=(20, 10), sticky="e")
        self.c_tandas_2 = ctk.CTkComboBox(parent, values=[""], fg_color=BG_INPUT, border_color=BORDER)
        self.c_tandas_2.grid(row=0, column=3, padx=10, pady=(20, 10), sticky="ew")

        ctk.CTkLabel(parent, text="Categoría Destino:", text_color=TEXT_MUTED).grid(row=1, column=0, padx=20, pady=10, sticky="e")
        self.c_dest = ctk.CTkComboBox(parent, values=[], fg_color=BG_INPUT, border_color=BORDER)
        self.c_dest.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # Fila 2: Cuota y Días
        ctk.CTkLabel(parent, text="Videos/día por cuenta:", text_color=TEXT_MUTED).grid(row=2, column=0, padx=20, pady=10, sticky="e")
        self.e_quota = ctk.CTkEntry(parent, fg_color=BG_INPUT, border_color=BORDER, width=80)
        self.e_quota.insert(0, "4")
        self.e_quota.grid(row=2, column=1, padx=10, pady=10, sticky="w")

        ctk.CTkLabel(parent, text="Días (o 'MAX'):", text_color=TEXT_MUTED).grid(row=2, column=2, padx=20, pady=10, sticky="e")
        self.e_days = ctk.CTkEntry(parent, fg_color=BG_INPUT, border_color=BORDER, width=80)
        self.e_days.insert(0, "MAX")
        self.e_days.grid(row=2, column=3, padx=10, pady=10, sticky="w")

        # Fila 3: Fill-up
        self.fillup_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(parent, text="Habilitar 'Fill-up' (Rellenar con historial si faltan)",
                        variable=self.fillup_var, text_color=NEON_CYAN).grid(row=3, column=0, columnspan=4, padx=20, pady=(10, 20), sticky="w")

        # Botonera
        btn_box = ctk.CTkFrame(parent, fg_color="transparent")
        btn_box.grid(row=4, column=0, columnspan=4, pady=30)

        ctk.CTkButton(btn_box, text="👁️ VISTA PREVIA", fg_color=NEON_CYAN, text_color=BG_APP,
                      hover_color=self._darken(NEON_CYAN), height=BTN_H_LG,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self.preview_distribution).pack(side="left", padx=10)

        ctk.CTkButton(btn_box, text="🚀 DISTRIBUIR REAL AHORA", fg_color=IG_PINK, text_color=TEXT_H1,
                      hover_color=self._darken(IG_PINK), height=BTN_H_LG,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self.start_distribution).pack(side="left", padx=10)

    PERIOD_DAYS = {
        "1 semana": 7,
        "2 semanas": 14,
        "3 semanas": 21,
        "1 mes": 30,
    }

    def _build_dist_cuentas_tab(self, parent):
        """Tab: bloques secuenciales — cada cuenta recibe un bloque distinto del pool."""
        parent.grid_rowconfigure(4, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # ── Diagrama visual ──────────────────────────────────────────────
        diag = ctk.CTkFrame(parent, fg_color=BG_CARD2, corner_radius=CARD_RADIUS)
        diag.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        ctk.CTkLabel(diag, text="📊  Flujo de Distribución por Cuentas",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=NEON_CYAN).pack(anchor="w", padx=16, pady=(10, 2))
        diag_txt = ctk.CTkTextbox(diag, height=85, font=FONT_MONO,
                                  fg_color="transparent", text_color=NEON_CYAN)
        diag_txt.pack(fill="x", padx=16, pady=(0, 10))
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
        cfg = ctk.CTkFrame(parent, fg_color=BG_CARD2, corner_radius=CARD_RADIUS)
        cfg.grid(row=1, column=0, sticky="ew", padx=16, pady=6)
        cfg.grid_columnconfigure((1, 3, 5), weight=1)

        # Fila 0: Tanda fuente
        ctk.CTkLabel(cfg, text="Tanda fuente:", text_color=TEXT_MUTED).grid(
            row=0, column=0, padx=(16, 8), pady=(16, 8), sticky="e")
        self.acct_dist_tanda = ctk.CTkComboBox(cfg, values=[], fg_color=BG_INPUT,
                                                border_color=BORDER)
        self.acct_dist_tanda.grid(row=0, column=1, columnspan=5, padx=(0, 16), pady=(16, 8), sticky="ew")

        # Fila 1: Videos al día + Período + total calculado
        ctk.CTkLabel(cfg, text="Videos al día:", text_color=TEXT_MUTED).grid(
            row=1, column=0, padx=(16, 8), pady=(4, 16), sticky="e")
        self.acct_dist_vpd = ctk.CTkEntry(cfg, fg_color=BG_INPUT, border_color=BORDER, width=60)
        self.acct_dist_vpd.insert(0, "3")
        self.acct_dist_vpd.grid(row=1, column=1, padx=(0, 16), pady=(4, 16), sticky="w")
        self.acct_dist_vpd.bind("<KeyRelease>", lambda e: self._acct_dist_update_total())

        ctk.CTkLabel(cfg, text="Período:", text_color=TEXT_MUTED).grid(
            row=1, column=2, padx=(8, 8), pady=(4, 16), sticky="e")
        self.acct_dist_period = ctk.CTkComboBox(
            cfg, values=list(self.PERIOD_DAYS.keys()),
            fg_color=BG_INPUT, border_color=BORDER,
            command=lambda _: self._acct_dist_update_total())
        self.acct_dist_period.set("1 semana")
        self.acct_dist_period.grid(row=1, column=3, padx=(0, 16), pady=(4, 16), sticky="ew")

        self.acct_dist_total_lbl = ctk.CTkLabel(
            cfg, text="= 21 videos/cuenta",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=NEON_CYAN)
        self.acct_dist_total_lbl.grid(row=1, column=4, columnspan=2, padx=(0, 16), pady=(4, 16), sticky="w")
        self._acct_dist_update_total()

        # ── Cuentas ──────────────────────────────────────────────────────
        acc = ctk.CTkFrame(parent, fg_color=BG_CARD2, corner_radius=CARD_RADIUS)
        acc.grid(row=2, column=0, sticky="ew", padx=16, pady=6)
        acc.grid_columnconfigure(0, weight=1)

        acc_hdr = ctk.CTkFrame(acc, fg_color="transparent")
        acc_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        ctk.CTkLabel(acc_hdr, text="👥  Cuentas destino",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT_H1).pack(side="left")
        ctk.CTkButton(acc_hdr, text="Limpiar", fg_color=BG_CARD, text_color=TEXT_MUTED,
                      height=BTN_H, width=70, corner_radius=BTN_RADIUS,
                      command=self._acct_dist_clear).pack(side="right", padx=4)
        ctk.CTkButton(acc_hdr, text="+ Suicide", fg_color=IG_PINK, text_color=TEXT_H1,
                      height=BTN_H, width=80, corner_radius=BTN_RADIUS,
                      command=lambda: self._acct_dist_load_file("suicide")).pack(side="right", padx=4)
        ctk.CTkButton(acc_hdr, text="+ Promo", fg_color=NEON_CYAN, text_color=BG_APP,
                      height=BTN_H, width=80, corner_radius=BTN_RADIUS,
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
        ctk.CTkButton(cat_row, text="+ Cargar categoría", fg_color=BG_CARD,
                      text_color=NEON_CYAN, height=BTN_H, corner_radius=BTN_RADIUS,
                      border_width=1, border_color=NEON_CYAN,
                      command=self._acct_dist_load_category).pack(side="left")

        self.acct_dist_list = ctk.CTkTextbox(acc, height=90, fg_color=BG_INPUT,
                                              text_color=TEXT_BODY, font=FONT_MONO)
        self.acct_dist_list.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 4))

        add_row = ctk.CTkFrame(acc, fg_color="transparent")
        add_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.acct_dist_entry = ctk.CTkEntry(add_row, fg_color=BG_INPUT, border_color=BORDER,
                                             placeholder_text="@cuenta_nueva", width=200)
        self.acct_dist_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(add_row, text="➕ Agregar", fg_color=SUCCESS, text_color=BG_APP,
                      height=BTN_H, corner_radius=BTN_RADIUS,
                      command=self._acct_dist_add).pack(side="left", padx=(0, 4))
        ctk.CTkButton(add_row, text="➖ Última", fg_color=DANGER, text_color=TEXT_H1,
                      height=BTN_H, corner_radius=BTN_RADIUS,
                      command=self._acct_dist_remove_last).pack(side="left")

        # ── Botones principales ──────────────────────────────────────────
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.grid(row=3, column=0, pady=16)
        ctk.CTkButton(btn_row, text="👁️ PREVISUALIZAR",
                      fg_color=NEON_CYAN, text_color=BG_APP,
                      hover_color=self._darken(NEON_CYAN), height=BTN_H_LG,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=lambda: self._acct_dist_run(preview_only=True)).pack(side="left", padx=10)
        ctk.CTkButton(btn_row, text="🚀 EJECUTAR POR CUENTAS",
                      fg_color=IG_PINK, text_color=TEXT_H1,
                      hover_color=self._darken(IG_PINK), height=BTN_H_LG,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=lambda: self._acct_dist_run(preview_only=False)).pack(side="left", padx=10)

        # ── Resultados ───────────────────────────────────────────────────
        self.acct_dist_result = ctk.CTkTextbox(parent, fg_color=BG_CARD2,
                                                text_color=NEON_CYAN, font=FONT_MONO)
        self.acct_dist_result.grid(row=4, column=0, sticky="nsew", padx=16, pady=(0, 16))

    # ── Lógica Logística ─────────────────────────────────────────────────────
    def reload_dist_lists(self, event=None):
        try:
            tandas_raw = self.db.get_all_tandas()
            tandas = [t["tanda_name"] if isinstance(t, dict) else t.get("tanda_name") for t in tandas_raw]
            tandas = [t for t in tandas if t]

            if hasattr(self, "c_tandas"):
                self.c_tandas.configure(values=tandas)
                if not self.c_tandas.get() and tandas: self.c_tandas.set(tandas[0])

            if hasattr(self, "c_tandas_2"):
                self.c_tandas_2.configure(values=[""] + tandas)

            if hasattr(self, "acct_dist_tanda"):
                self.acct_dist_tanda.configure(values=tandas)
                if not self.acct_dist_tanda.get() and tandas:
                    self.acct_dist_tanda.set(tandas[0])

            cats = self.db.get_categories()
            if hasattr(self, "c_dest"):
                self.c_dest.configure(values=cats)
                if not self.c_dest.get() and cats: self.c_dest.set(cats[0])
            if hasattr(self, "acct_dist_cat"):
                self.acct_dist_cat.configure(values=cats)
                if not self.acct_dist_cat.get() and cats: self.acct_dist_cat.set(cats[0])
            if hasattr(self, "c_forge_cat"):
                self._forge_reload_cats()
        except Exception as e:
            print(f"⚠️ Error al refrescar listas dist: {e}")

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
                win.geometry("950x700")
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
        days = self.PERIOD_DAYS.get(self.acct_dist_period.get(), 7)
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

    def _acct_dist_run(self, preview_only: bool = True):
        tanda = self.acct_dist_tanda.get()
        accounts = self._acct_dist_accounts()
        if not tanda:
            messagebox.showwarning("⚠️", "Selecciona una tanda fuente")
            return
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
        days = self.PERIOD_DAYS.get(period_str, 7)
        n = vpd * days

        folder = os.path.join(_BASE_DIR, "videos_finales", tanda)

        # Advertir si la ejecución va a sobreescribir Dia_* existentes
        if not preview_only:
            cal_root = os.path.join(_BASE_DIR, "CALENDARIO_POSTEO")
            if os.path.exists(cal_root):
                existing = [d for d in os.listdir(cal_root)
                            if d.lower().startswith("dia_") and
                            os.path.isdir(os.path.join(cal_root, d))]
                if existing:
                    if not messagebox.askyesno(
                        "⚠️ Sobreescribir",
                        f"Se borrarán las carpetas Dia_* existentes de las cuentas seleccionadas "
                        f"y se crearán nuevas.\n¿Continuar?"
                    ):
                        return

        def task():
            if not os.path.exists(folder):
                raise FileNotFoundError(f"Carpeta no encontrada: {folder}")

            # Pool completo de videos — sin filtro por historial
            vids = sorted(f for f in os.listdir(folder)
                          if f.lower().endswith((".mp4", ".mov", ".avi")))
            if not vids:
                raise ValueError("No se encontraron videos en la carpeta")

            n_actual = min(n, len(vids) // max(len(accounts), 1))
            if n_actual == 0:
                raise ValueError(f"No hay suficientes videos ({len(vids)}) para {len(accounts)} cuenta(s) con {n} por cuenta")

            # Bloques secuenciales: primeros n_actual → cuenta 1, siguientes → cuenta 2, etc.
            plan: dict[str, list[str]] = {}
            for idx, acc in enumerate(accounts):
                start = idx * n_actual
                end = start + n_actual
                block = vids[start:end]
                if len(block) < n_actual:
                    break  # No hay videos suficientes para esta cuenta
                shuffled = block[:]
                random.shuffle(shuffled)
                plan[acc] = shuffled

            lines = []
            label = "👁️  PREVISUALIZACIÓN" if preview_only else "🚀  EJECUTANDO"
            lines += [label, "=" * 60,
                      f"📦  Tanda      : {tanda}",
                      f"📦  Pool total  : {len(vids)} videos en carpeta",
                      f"📅  Período     : {period_str}  ({days} días × {vpd} videos/día = {n} solicitados)",
                      f"📦  Por cuenta  : {n_actual} videos (bloque único, orden aleatorio)",
                      f"👥  Cuentas    : {len(plan)}", ""]

            for acc, order in plan.items():
                lines.append(f"📱  {acc}  →  {len(order)} videos")
                for i, vid in enumerate(order, 1):
                    lines.append(f"    {i:02d}. {vid}")
                lines.append("")

            if not preview_only:
                cal_root = os.path.join(_BASE_DIR, "CALENDARIO_POSTEO")

                # Limpiar carpetas Dia_* existentes solo para las cuentas del plan
                if os.path.exists(cal_root):
                    for day_folder in os.listdir(cal_root):
                        if not day_folder.lower().startswith("dia_"):
                            continue
                        day_path = os.path.join(cal_root, day_folder)
                        for acc in accounts:
                            acc_path = os.path.join(day_path, acc)
                            if os.path.isdir(acc_path):
                                shutil.rmtree(acc_path)
                        # Eliminar el día si quedó vacío
                        try:
                            if not any(True for _ in os.scandir(day_path)):
                                shutil.rmtree(day_path)
                        except OSError:
                            pass

                # Crear estructura Dia_X/<cuenta>/video.mp4
                total_copiados = 0
                for acc, order in plan.items():
                    for day_num in range(1, days + 1):
                        day_path = os.path.join(cal_root, f"Dia_{day_num}", acc)
                        os.makedirs(day_path, exist_ok=True)
                        start_idx = (day_num - 1) * vpd
                        for vid_name in order[start_idx : start_idx + vpd]:
                            src = os.path.join(folder, vid_name)
                            dst = os.path.join(day_path, vid_name)
                            shutil.copy2(src, dst)
                            total_copiados += 1

                lines += ["=" * 60,
                          f"✅  Estructura creada en : {cal_root}",
                          f"📁  Días generados       : Dia_1 → Dia_{days}",
                          f"📋  Cuentas              : {len(plan)}",
                          f"🎞️  Archivos copiados    : {total_copiados}"]

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

    def _build_tg_frame(self):
        """TAREA 6 — Bot Telegram."""
        f = self._frames["Telegram"]
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure((0, 1), weight=1)

        # ── Header ──────────────────────────────────────────────────────
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="📲  Telegram Bot Control",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TEXT_H1).grid(row=0, column=0, sticky="w")

        # ── Panel Izquierdo: Cuentas y Controles ────────────────────────
        ctrl_card = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        ctrl_card.grid(row=1, column=0, sticky="nsew", padx=(24, 12), pady=10)
        ctrl_card.grid_rowconfigure(4, weight=1)
        ctrl_card.grid_columnconfigure(0, weight=1)

        # Fila 0: título + botón cargar
        hdr_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        hdr_row.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 5))
        hdr_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr_row, text="Cuentas Programadas", text_color=NEON_CYAN,
                     font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w")
        self.btn_load_tg = ctk.CTkButton(hdr_row, text="🔄 Cargar", fg_color=BG_CARD2, text_color=TEXT_BODY,
                                         border_width=1, border_color=BORDER, hover_color=BORDER,
                                         command=self.load_organized_accounts)
        self.btn_load_tg.grid(row=0, column=1, sticky="e")

        # Fila 1: filtro + seleccionar todos/ninguno
        filter_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        filter_row.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 4))
        filter_row.grid_columnconfigure(0, weight=1)
        self._tg_only_with_videos = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(filter_row, text="Solo con videos", variable=self._tg_only_with_videos,
                        text_color=TEXT_MUTED, checkbox_width=16, checkbox_height=16,
                        command=self.load_organized_accounts).grid(row=0, column=0, sticky="w")
        sel_frame = ctk.CTkFrame(filter_row, fg_color="transparent")
        sel_frame.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(sel_frame, text="✓ Todos", width=72, fg_color=BG_CARD2, text_color=TEXT_MUTED,
                      border_width=1, border_color=BORDER, hover_color=BORDER,
                      command=lambda: self.list_tg.select_set(0, "end")).pack(side="left", padx=(0, 4))
        ctk.CTkButton(sel_frame, text="✗ Ninguno", width=78, fg_color=BG_CARD2, text_color=TEXT_MUTED,
                      border_width=1, border_color=BORDER, hover_color=BORDER,
                      command=lambda: self.list_tg.selection_clear(0, "end")).pack(side="left")

        # Fila 2: toggle "Configurar Horarios"
        self._schedule_panel_expanded = False
        sched_header = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        sched_header.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 0))
        sched_header.grid_columnconfigure(0, weight=1)
        self.btn_toggle_sched = ctk.CTkButton(
            sched_header, text="▶ Configurar Horarios", anchor="w",
            fg_color=BG_CARD2, text_color=TEXT_BODY, hover_color=BORDER,
            command=self._toggle_schedule_panel,
        )
        self.btn_toggle_sched.grid(row=0, column=0, sticky="ew")

        # Fila 3: panel de horarios (oculto inicialmente)
        self.sched_panel = ctk.CTkScrollableFrame(ctrl_card, fg_color=BG_INPUT, height=160)
        # NO se ejecuta .grid() aquí — se invoca en _toggle_schedule_panel al expandir

        # Fila 4: listbox con selección múltiple
        self.list_tg = tk.Listbox(ctrl_card, bg=BG_INPUT, fg=TEXT_BODY, selectbackground=NEON_PURPLE,
                                  selectmode=tk.EXTENDED,
                                  borderwidth=0, highlightthickness=1, highlightbackground=BORDER, font=FONT_BODY)
        self.list_tg.grid(row=4, column=0, sticky="nsew", padx=20, pady=(0, 10))

        # Controles inferiores
        bot_ctrl = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        bot_ctrl.grid(row=5, column=0, sticky="ew", padx=20, pady=(10, 20))
        
        ctk.CTkLabel(bot_ctrl, text="Fecha Inicio (YYYY-MM-DD):", text_color=TEXT_MUTED).pack(side="left")
        self.e_date_tg = ctk.CTkEntry(bot_ctrl, fg_color=BG_INPUT, border_color=BORDER, width=120)
        self.e_date_tg.pack(side="left", padx=10)
        self.e_date_tg.insert(0, datetime.now().strftime("%Y-%m-%d"))

        btn_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        btn_row.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 20))
        
        self.btn_start_tg = ctk.CTkButton(btn_row, text="▶ INICIAR", fg_color=SUCCESS, text_color=BG_APP,
                                          hover_color=self._darken(SUCCESS), font=ctk.CTkFont(weight="bold"),
                                          command=self.start_tg_bot)
        self.btn_start_tg.pack(side="left", expand=True, padx=(0, 5))
        
        self.btn_pause_tg = ctk.CTkButton(btn_row, text="⏸ PAUSAR", fg_color=WARNING, text_color=BG_APP,
                                          hover_color=self._darken(WARNING), font=ctk.CTkFont(weight="bold"),
                                          state="disabled", command=self.pause_tg_bot)
        self.btn_pause_tg.pack(side="left", expand=True, padx=5)
        
        self.btn_stop_tg = ctk.CTkButton(btn_row, text="⏹ DETENER", fg_color=DANGER, text_color=TEXT_H1,
                                         hover_color=self._darken(DANGER), font=ctk.CTkFont(weight="bold"),
                                         state="disabled", command=self.stop_tg_bot)
        self.btn_stop_tg.pack(side="left", expand=True, padx=(5, 0))

        # ── Panel Derecho: Live Log ─────────────────────────────────────
        log_card = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        log_card.grid(row=1, column=1, sticky="nsew", padx=(12, 24), pady=10)
        log_card.grid_rowconfigure(1, weight=1)
        log_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(log_card, text="Registro de Actividad", text_color=NEON_PURPLE,
                     font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))
        
        self.tg_log = ctk.CTkTextbox(log_card, fg_color=BG_INPUT, text_color=TEXT_BODY, font=FONT_MONO,
                                     border_width=1, border_color=BORDER)
        self.tg_log.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        
        self.tg_log.tag_config("INFO", foreground=INFO)
        self.tg_log.tag_config("SUCCESS", foreground=SUCCESS)
        self.tg_log.tag_config("WARNING", foreground=WARNING)
        self.tg_log.tag_config("ERROR", foreground=DANGER)
        
        self.pb_tg = ctk.CTkProgressBar(log_card, fg_color=BG_INPUT, progress_color=NEON_CYAN)
        self.pb_tg.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
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
        win.geometry("520x420")
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
    def load_organized_accounts(self):
        try:
            date_str = self.e_date_tg.get().strip()
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return messagebox.showwarning("⚠️", "Formato de fecha inválido. Usa YYYY-MM-DD.")

        only_with_videos = self._tg_only_with_videos.get() if self._tg_only_with_videos else False
        accounts = self.db.get_all_accounts()
        cal_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CALENDARIO_POSTEO")

        enriched = []
        for acc in accounts:
            total = 0
            if os.path.isdir(cal_root):
                for day_folder in os.listdir(cal_root):
                    if not day_folder.lower().startswith("dia_"):
                        continue
                    acc_folder = os.path.join(cal_root, day_folder, acc["username"])
                    if os.path.isdir(acc_folder):
                        total += sum(
                            1 for f in os.listdir(acc_folder)
                            if f.lower().endswith((".mp4", ".mov"))
                        )
            if only_with_videos and total == 0:
                continue
            enriched.append({
                "username": acc["username"],
                "assigned_va": acc.get("assigned_va", "Sin Asignar"),
                "total_videos": total,
                "account_type": acc.get("account_type", ""),
            })

        self._tg_accounts = enriched
        self.list_tg.delete(0, "end")
        for acc in enriched:
            tag = acc.get("account_type", "").upper() or "—"
            self.list_tg.insert("end", f"@{acc['username']}  [{tag}]  ({acc['assigned_va']})  {acc['total_videos']} videos")
        self.list_tg.select_set(0, "end")  # seleccionar todas por defecto

        self.bot_log(f"Cargadas {len(enriched)} cuentas para {date_str}{'  (solo con videos)' if only_with_videos else ''}.", "INFO")

    def bot_log(self, message: str, level="INFO"):
        """Escribe en la consola del bot (thread-safe)."""
        def update():
            self.tg_log.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n", level)
            self.tg_log.see("end")
        self.after(0, update)

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

        selected_indices = list(self.list_tg.curselection())
        if not selected_indices:
            return messagebox.showwarning("⚠️", "Selecciona al menos una cuenta en la lista antes de iniciar.")

        selected_accounts = [
            self._tg_accounts[i]['username']
            for i in selected_indices
            if i < len(self._tg_accounts)
        ]
        if not selected_accounts:
            return messagebox.showwarning("⚠️", "No se pudieron resolver las cuentas seleccionadas. Recarga la lista.")

        self.bot_log(f"Cuentas seleccionadas ({len(selected_accounts)}): {', '.join('@' + u for u in selected_accounts)}", "INFO")

        import organizadortg as telegram_bot
        self.tg_controller = telegram_bot.TelegramBotController(date_str, selected_accounts)
        
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
            if "error" in msg.lower() or "falló" in msg.lower(): lvl = "ERROR"
            elif "éxito" in msg.lower() or "enviado" in msg.lower(): lvl = "SUCCESS"
            elif "esperando" in msg.lower(): lvl = "WARNING"
            self.bot_log(msg, lvl)
            
        import builtins
        self._original_print = builtins.print
        builtins.print = custom_print
        
        def worker():
            self.tg_controller.start()
            
        def done(success, _):
            builtins.print = self._original_print
            self.btn_start_tg.configure(state="normal")
            self.btn_pause_tg.configure(state="disabled")
            self.btn_stop_tg.configure(state="disabled")
            self.set_bot_status(False)
            self.pb_tg.set(1)
            
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
        f.grid_rowconfigure(0, weight=1)
        f.grid_columnconfigure(0, weight=1)

        self._cuentas_panel = AccountStatusPanel(f, self.db)
        self._cuentas_panel.grid(row=0, column=0, sticky="nsew")

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
    # FORGE DE METADATA
    # ══════════════════════════════════════════════════════════════════════
    def _build_forge_frame(self):
        self.forge_video_paths = []
        self.forge_meta_assignments = []

        f = self._frames["Forge"]
        f.grid_rowconfigure(2, weight=1)
        f.grid_columnconfigure(0, weight=1)

        # ── Header ──────────────────────────────────────────────────────
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="🔮  Forge de Metadata",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TEXT_H1).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Inyecta fingerprints iPhone únicos · 63,000 combinaciones disponibles",
                     font=ctk.CTkFont(size=12), text_color=TEXT_MUTED
                     ).grid(row=1, column=0, sticky="w")

        # ── Top: dos tarjetas (Videos | Config) ─────────────────────────
        top = ctk.CTkFrame(f, fg_color="transparent")
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
            card_vids, bg=BG_INPUT, fg=TEXT_BODY,
            selectbackground=NEON_PURPLE, selectmode=tk.EXTENDED,
            borderwidth=0, highlightthickness=1, highlightbackground=BORDER,
            font=FONT_BODY, height=9
        )
        self.forge_lst.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 6))

        btn_v = ctk.CTkFrame(card_vids, fg_color="transparent")
        btn_v.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 16))
        ctk.CTkButton(btn_v, text="＋  Agregar Videos", fg_color=NEON_CYAN,
                      text_color=BG_APP, hover_color=self._darken(NEON_CYAN),
                      corner_radius=BTN_RADIUS, height=BTN_H,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=self.forge_add_videos).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_v, text="−  Quitar", fg_color=DANGER,
                      text_color=TEXT_H1, hover_color=self._darken(DANGER),
                      corner_radius=BTN_RADIUS, height=BTN_H,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=self.forge_remove_video).pack(side="left")

        # — Tarjeta Paso 2: Config —
        card_cfg = ctk.CTkFrame(top, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
        card_cfg.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        card_cfg.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card_cfg, text="2.  Configuración",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=NEON_PURPLE).grid(row=0, column=0, columnspan=2,
                                                  sticky="w", padx=18, pady=(16, 8))

        cfg_rows = [
            ("Nombre de tanda:",   "e_forge_tanda",   None),
            ("Categoría destino:", "c_forge_cat",      "combo"),
            ("Videos/cuenta/día:", "e_forge_quota",    "4"),
            ("Días a distribuir:", "e_forge_days",     "MAX"),
        ]
        for row_i, (lbl, attr, default) in enumerate(cfg_rows, start=1):
            ctk.CTkLabel(card_cfg, text=lbl, text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=11), anchor="e"
                         ).grid(row=row_i, column=0, padx=(18, 8), pady=7, sticky="e")
            if default == "combo":
                widget = ctk.CTkComboBox(card_cfg, values=[], fg_color=BG_INPUT,
                                         border_color=BORDER,
                                         button_color=NEON_CYAN,
                                         dropdown_fg_color=BG_CARD2)
                widget.grid(row=row_i, column=1, padx=(0, 18), pady=7, sticky="ew")
                setattr(self, attr, widget)
                self.c_forge_cat = widget
                self._forge_reload_cats()
            else:
                widget = ctk.CTkEntry(card_cfg, fg_color=BG_INPUT,
                                      border_color=BORDER)
                if default:
                    widget.insert(0, default)
                widget.grid(row=row_i, column=1, padx=(0, 18), pady=7, sticky="ew")
                setattr(self, attr, widget)

        self.forge_dist_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(card_cfg, text="Distribuir automáticamente al procesar",
                        variable=self.forge_dist_var,
                        text_color=NEON_CYAN,
                        checkbox_width=18, checkbox_height=18
                        ).grid(row=5, column=0, columnspan=2,
                               sticky="w", padx=18, pady=(6, 16))

        # ── Tabla Preview ────────────────────────────────────────────────
        preview_card = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=CARD_RADIUS)
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
                                       style="Premium.Treeview", height=7)
        col_w = {"Video": 200, "Modelo iPhone": 190, "Ciudad": 140, "Carrier": 170, "iOS": 70}
        for col in cols:
            self.forge_tree.heading(col, text=col)
            self.forge_tree.column(col, width=col_w[col], anchor="center")
        scr = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.forge_tree.yview)
        self.forge_tree.configure(yscrollcommand=scr.set)
        self.forge_tree.grid(row=0, column=0, sticky="nsew")
        scr.grid(row=0, column=1, sticky="ns", padx=(2, 0))

        # ── Botonera + Progreso ──────────────────────────────────────────
        bot = ctk.CTkFrame(f, fg_color="transparent")
        bot.grid(row=3, column=0, sticky="ew", padx=24, pady=(14, 20))
        bot.grid_columnconfigure(3, weight=1)

        ctk.CTkButton(bot, text="👁️  Preview Metadata",
                      fg_color=INFO, text_color=TEXT_H1,
                      hover_color=self._darken(INFO),
                      corner_radius=BTN_RADIUS, height=BTN_H_LG,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self.forge_preview_metadata
                      ).grid(row=0, column=0, padx=(0, 8))

        self.btn_forge_reshuffle = ctk.CTkButton(
            bot, text="🔀  Regenerar Shuffle",
            fg_color=WARNING, text_color=BG_APP,
            hover_color=self._darken(WARNING),
            corner_radius=BTN_RADIUS, height=BTN_H_LG,
            font=ctk.CTkFont(size=13, weight="bold"),
            state="disabled", command=self.forge_reshuffle
        )
        self.btn_forge_reshuffle.grid(row=0, column=1, padx=(0, 8))

        self.btn_forge_process = ctk.CTkButton(
            bot, text="⚡  Procesar Ahora",
            fg_color=IG_PINK, text_color=TEXT_H1,
            hover_color=self._darken(IG_PINK),
            corner_radius=BTN_RADIUS, height=BTN_H_LG,
            font=ctk.CTkFont(size=13, weight="bold"),
            state="disabled", command=self.forge_process
        )
        self.btn_forge_process.grid(row=0, column=2, padx=(0, 20))

        prog_wrap = ctk.CTkFrame(bot, fg_color="transparent")
        prog_wrap.grid(row=0, column=3, sticky="ew")
        prog_wrap.grid_columnconfigure(0, weight=1)

        self.forge_pb = ctk.CTkProgressBar(prog_wrap, fg_color=BG_INPUT,
                                            progress_color=NEON_PURPLE, height=8)
        self.forge_pb.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.forge_pb.set(0)

        self.forge_pb_lbl = ctk.CTkLabel(prog_wrap, text="Listo.",
                                          font=ctk.CTkFont(size=11),
                                          text_color=TEXT_MUTED)
        self.forge_pb_lbl.grid(row=1, column=0, sticky="w")

        f.grid_rowconfigure(3, weight=0)

    def _forge_reload_cats(self):
        cats = self.db.get_categories()
        if hasattr(self, "c_forge_cat"):
            self.c_forge_cat.configure(values=cats)
            if cats and not self.c_forge_cat.get():
                self.c_forge_cat.set(cats[0])

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
        n = len(self.forge_video_paths)
        if n == 0:
            return messagebox.showwarning("⚠️", "Agrega al menos un video primero.")
        try:
            import metadata_pool
            self.forge_meta_assignments = metadata_pool.generate_unique_metadata(self.db, n)
        except ValueError as e:
            return messagebox.showerror("Sin combinaciones disponibles", str(e))

        for item in self.forge_tree.get_children():
            self.forge_tree.delete(item)
        for i, path in enumerate(self.forge_video_paths):
            m = self.forge_meta_assignments[i]
            tag = "even" if i % 2 == 0 else "odd"
            self.forge_tree.insert("", tk.END, tags=(tag,), values=(
                os.path.basename(path), m["iphone_model"], m["city"],
                m["carrier"], m["ios_version"]
            ))
        self.btn_forge_process.configure(state="normal")
        self.btn_forge_reshuffle.configure(state="normal")
        self.forge_pb_lbl.configure(
            text=f"✅ {n} asignaciones generadas. Revisá y presioná Procesar.",
            text_color=SUCCESS
        )

    def forge_reshuffle(self):
        self.forge_preview_metadata()

    def forge_process(self):
        if not self.forge_video_paths:
            return messagebox.showwarning("⚠️", "No hay videos en la lista.")
        if not self.forge_meta_assignments:
            return messagebox.showwarning("⚠️", "Generá el preview primero.")

        tanda_name = self.e_forge_tanda.get().strip()
        category   = self.c_forge_cat.get()
        auto_dist  = self.forge_dist_var.get()

        if not tanda_name:
            return messagebox.showwarning("⚠️", "Ingresá un nombre para la tanda Forge.")
        if not category:
            return messagebox.showwarning("⚠️", "Seleccioná una categoría destino.")
        try:
            quota = int(self.e_forge_quota.get())
        except ValueError:
            return messagebox.showwarning("⚠️", "Cuota diaria inválida.")

        days_input = self.e_forge_days.get().strip() or "MAX"

        if not messagebox.askyesno("Confirmar Forge", (
            f"¿Procesar {len(self.forge_video_paths)} videos con metadata iPhone única?\n\n"
            f"Tanda: {tanda_name}\n"
            f"Categoría: {category}\n"
            f"Distribuir automáticamente: {'Sí' if auto_dist else 'No'}"
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
        self.forge_pb_lbl.configure(text="Procesando con FFmpeg...", text_color=WARNING)

        def task():
            import metadata_pool
            os.makedirs(output_dir, exist_ok=True)
            fingerprints = []
            for i, (vid_path, meta) in enumerate(zip(videos, meta_list)):
                filename = os.path.basename(vid_path)
                base, ext = os.path.splitext(filename)
                p1 = base.replace("__", "_")  # evita romper el parser de P1/P2
                out_name = f"{tanda_name}__{p1}__v{i:04d}{ext}"
                out_path = os.path.join(output_dir, out_name)
                metadata_pool.apply_metadata_to_video(vid_path, out_path, meta)
                fingerprints.append({
                    "video_hash": metadata_pool.get_video_hash(vid_path),
                    **meta,
                })
            db_ref.save_metadata_fingerprints(fingerprints)
            db_ref.add_tanda(tanda_name, tanda_name, tanda_name, "")

            msg = (
                f"✅ {len(videos)} videos procesados con metadata iPhone.\n"
                f"📁 Guardados en: videos_finales/{tanda_name}/\n"
                f"🔮 Tanda '{tanda_name}' registrada en la DB."
            )
            if auto_dist:
                import Organizador
                dist_result = Organizador.distribute_tanda(
                    tanda_name, category, quota, False, days_input
                )
                msg += f"\n\n{dist_result}"
            return msg

        def done(success, result):
            self.btn_forge_process.configure(state="normal")
            self.btn_forge_reshuffle.configure(state="normal")
            self.forge_pb.stop()
            self.forge_pb.configure(mode="determinate")
            self.forge_pb.set(1 if success else 0)
            if success:
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
if __name__ == "__main__":
    app = InstagramAutoPro()
    app.mainloop()
