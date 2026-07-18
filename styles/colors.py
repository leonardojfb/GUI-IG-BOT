"""
Design System — Instagram Automation Pro V7
Inspirado en patrones de SaaS dashboards modernos (dark mode first).
Todos los valores son tokens centralizados; nunca hardcodear colores fuera de este módulo.
"""

# ── Fondos ──────────────────────────────────────────────────────────────────
BG_APP     = "#0a0a12"   # Fondo raíz de la ventana
BG_SIDEBAR = "#0f0f1a"   # Panel de navegación lateral
BG_CARD    = "#13131f"   # Cards primarias
BG_CARD2   = "#1a1a2e"   # Cards secundarias / hover states
BG_INPUT   = "#1e1e30"   # Campos de entrada
BORDER     = "#2a2a40"   # Bordes y separadores

# ── Acentos de marca ─────────────────────────────────────────────────────────
NEON_CYAN   = "#00f5d4"  # CTA primario, highlights activos
NEON_PURPLE = "#7c3aed"  # Indicadores secundarios
IG_PINK     = "#e1306c"  # Identidad Instagram / acciones destructivas
IG_ORANGE   = "#f77737"  # Gradiente Instagram alternativo

# ── Semánticos ───────────────────────────────────────────────────────────────
SUCCESS = "#10b981"   # Operación exitosa
WARNING = "#f59e0b"   # Advertencia
DANGER  = "#ef4444"   # Error / eliminar
INFO    = "#3b82f6"   # Información / neutral

# ── Tipografía ───────────────────────────────────────────────────────────────
TEXT_H1    = "#f1f5f9"   # Títulos principales
TEXT_BODY  = "#cbd5e1"   # Cuerpo de texto
TEXT_MUTED = "#64748b"   # Textos secundarios / placeholders

# ── Fuentes ──────────────────────────────────────────────────────────────────
FONT_TITLE  = ("Arial", 22, "bold")
FONT_H2     = ("Arial", 15, "bold")
FONT_H3     = ("Arial", 12, "bold")
FONT_BODY   = ("Arial", 12)
FONT_SMALL  = ("Arial", 10)
FONT_MONO   = ("Consolas", 10)  # Para logs y output técnico

# ── Tamaños de componentes ───────────────────────────────────────────────────
SIDEBAR_W   = 210    # Ancho del sidebar en píxeles
STATUS_H    = 28     # Alto de la status bar
CARD_RADIUS = 10     # Radio de esquinas de las cards
BTN_RADIUS  = 8      # Radio de esquinas de los botones
BTN_H       = 38     # Alto estándar de botones
BTN_H_LG   = 46     # Alto de botones de acción principal
