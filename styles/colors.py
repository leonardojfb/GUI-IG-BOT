"""
Design System — Instagram Automation Pro V7
Inspirado en patrones de SaaS dashboards modernos (natural light + dark).
Todos los valores son tokens centralizados; nunca hardcodear colores fuera de este módulo.
"""

# ── Fondos ── (light, dark) ─────────────────────────────────────────────
BG_APP     = ("#faf9f6", "#0c0c0e")   # Fondo raíz (near-black cálido en dark)
BG_SIDEBAR = ("#f3f1ea", "#0e0e10")   # Panel lateral
BG_CARD    = ("#ffffff", "#141416")   # Cards primarias
BG_CARD2   = ("#f0eee7", "#1a1a1d")   # Cards secundarias / hover
BG_INPUT   = ("#f3f1ea", "#141416")   # Campos de entrada
BORDER     = ("#e7e3d9", "#242428")   # Bordes y separadores

# ── Acentos ── (light, dark) — peach/almond, acento único OOPSIE ─────────
NEON_CYAN   = ("#c98a3f", "#e9c7a3")  # ACENTO PRIMARIO (peach). Nombre legacy.
ACCENT_WEAK = ("#f3e6d3", "#2a2118")  # Fondo del nav activo (peach tenue)
NEON_PURPLE = ("#7a6a52", "#c9b48f")  # Acento secundario apagado (legacy)
IG_PINK     = ("#c9564e", "#e5675f")  # Destructivas
IG_ORANGE   = ("#c2872f", "#e0a94e")  # Ámbar

# ── Semánticos ──
SUCCESS  = ("#3f9d6d", "#3fb768")
WARNING  = ("#c2872f", "#e0a94e")
DANGER   = ("#c9564e", "#e5675f")
INFO     = ("#2f88c2", "#29a9ea")
TELEGRAM = ("#2f88c2", "#29a9ea")     # Botón de soporte Telegram

# ── Marcas de plataforma (el icono conserva color de marca) ──
BRAND_REDDIT = ("#ff4500", "#ff4500")
BRAND_X      = ("#1d1d1f", "#e7e9ea")
BRAND_IG     = ("#e1306c", "#e1306c")

# ── Tipografía ── (light, dark) ──
TEXT_H1    = ("#1b1a17", "#f5f5f5")
TEXT_BODY  = ("#55534c", "#a0a0a6")
TEXT_MUTED = ("#8b887f", "#6c6c72")

# ── Texto/hover sobre acento peach ──
ACCENT_TEXT     = ("#1c1710", "#1c1710")
TEXT_ON_DANGER  = ("#ffffff", "#ffffff")  # Texto sobre botón destructivo (rojo), invariante a tema
SWITCH_KNOB     = ("#ffffff", "#ffffff")  # Perilla del CTkSwitch, blanca en ambos temas
ACCENT_HOVER    = ("#b87d38", "#dcb489")

# ── Aliases semánticos ──
GROUND   = BG_APP
RAIL     = BG_SIDEBAR
SURFACE  = BG_CARD
SURFACE2 = BG_CARD2
LINE     = BORDER
ACCENT   = NEON_CYAN
ACCENT_2 = NEON_PURPLE

# ── Fuentes ──
FONT_TITLE  = ("Segoe UI", 28, "bold")   # Título de página grande
FONT_KICKER = ("Segoe UI", 11, "bold")   # Eyebrow uppercase
FONT_DESC   = ("Segoe UI", 14)           # Descripción bajo el título
FONT_H2     = ("Segoe UI", 15, "bold")
FONT_H3     = ("Segoe UI", 12, "bold")
FONT_BODY   = ("Segoe UI", 12)
FONT_SMALL  = ("Segoe UI", 10)
FONT_MONO   = ("Consolas", 10)


def resolve(value, mode):
    """Return the single color for the given CTk appearance mode.

    `value` may be a (light, dark) tuple/list or a plain color string. `mode`
    is a CTk appearance-mode string like "Light"/"Dark"/"System" (case-
    insensitive). Non-"dark" modes resolve to the light color. Plain strings
    pass through unchanged.
    """
    if isinstance(value, (tuple, list)):
        return value[1] if str(mode).lower() == "dark" else value[0]
    return value

def darken(value, factor=0.75):
    """Return a slightly darker version of a color. Accepts a hex string or a
    (light, dark) tuple/list and returns the same shape (so it is safe to pass
    a themed token straight into a CustomTkinter `hover_color`)."""
    if isinstance(value, (tuple, list)):
        return tuple(darken(c, factor) for c in value)
    r = int(value[1:3], 16)
    g = int(value[3:5], 16)
    b = int(value[5:7], 16)
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"

# ── Tamaños de componentes ──
SIDEBAR_W    = 240
STATUS_H     = 28
CARD_RADIUS  = 16
BTN_RADIUS   = 10
INPUT_RADIUS = 10
BTN_H        = 40
BTN_H_LG     = 46
