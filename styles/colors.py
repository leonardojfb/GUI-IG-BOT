"""
Design System — Instagram Automation Pro V7
Inspirado en patrones de SaaS dashboards modernos (natural light + dark).
Todos los valores son tokens centralizados; nunca hardcodear colores fuera de este módulo.
"""

# ── Fondos ── (light, dark) ────────────────────────────────────────────────
BG_APP     = ("#f5f4f0", "#16181d")   # Fondo raíz de la ventana
BG_SIDEBAR = ("#edece6", "#1b1e25")   # Panel de navegación lateral
BG_CARD    = ("#ffffff", "#22262e")   # Cards primarias
BG_CARD2   = ("#f0efe9", "#2a2f38")   # Cards secundarias / hover
BG_INPUT   = ("#f3f2ec", "#262b33")   # Campos de entrada
BORDER     = ("#e3e1d8", "#333944")   # Bordes y separadores

# ── Acentos ── (light, dark) ────────────────────────────────────────────────
NEON_CYAN   = ("#2f8f7d", "#4db6a2")  # Acento primario (teal-sage), CTA, nav activo
ACCENT_WEAK = ("#dcefe9", "#223a37")  # Fondo del nav activo
NEON_PURPLE = ("#5b7fb0", "#7f9fcf")  # Acento secundario (slate-blue apagado)
IG_PINK     = ("#c9564e", "#e07a6f")  # Acciones destructivas (rosa apagado)
IG_ORANGE   = ("#c2872f", "#e0a94e")  # Ámbar apagado

# ── Semánticos ── (light, dark) ─────────────────────────────────────────────
SUCCESS = ("#3f9d6d", "#54b184")
WARNING = ("#c2872f", "#e0a94e")
DANGER  = ("#c9564e", "#e07a6f")
INFO    = ("#4a7fb0", "#6398c9")

# ── Tipografía ── (light, dark) ─────────────────────────────────────────────
TEXT_H1    = ("#2a2925", "#e9eaec")   # Títulos
TEXT_BODY  = ("#55534c", "#bdc2ca")   # Cuerpo
TEXT_MUTED = ("#8b887f", "#7d838d")   # Secundario / placeholder

# ── Aliases semánticos (nombres claros para código nuevo) ────────────────────
GROUND      = BG_APP
RAIL        = BG_SIDEBAR
SURFACE     = BG_CARD
SURFACE2    = BG_CARD2
LINE        = BORDER
ACCENT      = NEON_CYAN

# ── Fuentes ──────────────────────────────────────────────────────────────────
FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_H2     = ("Segoe UI", 15, "bold")
FONT_H3     = ("Segoe UI", 12, "bold")
FONT_BODY   = ("Segoe UI", 12)
FONT_SMALL  = ("Segoe UI", 10)
FONT_MONO   = ("Consolas", 10)  # Para logs y output técnico


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

# ── Tamaños de componentes ───────────────────────────────────────────────────
SIDEBAR_W   = 210    # Ancho del sidebar en píxeles
STATUS_H    = 28     # Alto de la status bar
CARD_RADIUS = 10     # Radio de esquinas de las cards
BTN_RADIUS  = 8      # Radio de esquinas de los botones
BTN_H       = 38     # Alto estándar de botones
BTN_H_LG   = 46     # Alto de botones de acción principal
