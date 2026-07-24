# FORGE — "Efectos" + "Fuerza" (dos ejes independientes)

**Fecha:** 2026-07-20
**Estado:** Diseño aprobado, pendiente plan de implementación
**App:** `Método IG VIDEOS v2.0/` — `metadata_pool.py` (variant engine) + `gui_premium_v7.py` (pantalla Forge)

## Objetivo

Dar al usuario dos controles independientes en FORGE para el variant engine:
- **Efectos** — CUÁLES / cuántos micro-efectos se aplican.
- **Fuerza** — CUÁNTA intensidad/aleatoriedad tienen los efectos aplicados.

Los dos ejes son ortogonales: se combinan libremente (ej. pocos efectos + mucha
fuerza, o muchos efectos + poca fuerza).

## Restricciones

- **Aditivo, cambios acotados.** Solo `metadata_pool.py` (backend del variant engine)
  y `gui_premium_v7.py` (UI de Forge). Sin dependencias nuevas.
- Reutiliza `generate_variant_params` y `apply_variant_and_metadata` existentes.
- **Cambio de comportamiento intencional (único):** hoy el default aplica los 8 efectos,
  con `mirror` (espejo horizontal) a ~50%. El nuevo default (`Efectos=Default`) son
  **7 efectos: todos menos `mirror`**. Es el único cambio de default; el resto de la
  intensidad por defecto (`Fuerza=Default`) es idéntica a hoy.
- El pipeline ffmpeg (filtros, `-c copy` fast-path, guard de dimensiones pares) no cambia.

## Modelo — dos `SegmentedControl`

### Eje 1 — Efectos: `[Default · Light · Medio · Alto · Custom]`
Cada nivel es un set de las 8 claves de `DEFAULT_VARIANT_EFFECTS`
(`crop, mirror, zoom, rotate, color, noise, speed, trim`):

| Nivel | Efectos on |
|---|---|
| **Default** (por defecto) | crop, zoom, rotate, color, noise, speed, trim (7 — **sin mirror**) |
| Light | color, trim (2, los más invisibles) |
| Medio | crop, color, noise, speed, trim (5) |
| Alto | los 8 (incluye mirror) |
| **Custom** | revela los 8 toggles on/off manuales (los `forge_fx_vars` actuales) |

### Eje 2 — Fuerza: `[Default · Light · Medio · Alto · Custom]`
Cada nivel es un factor `strength` (float) que escala la magnitud de los rangos y
(suavemente) las probabilidades:

| Nivel | strength |
|---|---|
| **Default** (por defecto) | 1.0 (= tuned actual) |
| Light | 0.5 |
| Medio | 1.0 |
| Alto | 2.4 |
| **Custom** | slider 0–100% → `0.3 + 0.022 * pct` (0%→0.3, 50%→1.4… ver plan; 100%→2.5) |

`Default` y `Medio` coinciden numéricamente (1.0): `Default` es la selección
recomendada por defecto; `Medio` es el punto medio explícito de la escala.

## Backend (`metadata_pool.py`)

`generate_variant_params(rng, enabled=None, strength=1.0)`:
- `enabled` (dict) — viene del eje **Efectos**: qué efectos están on (ya existe).
- `strength` (float, nuevo, default 1.0) — viene del eje **Fuerza**: escala cada rango
  desde su valor neutro por `strength`, y escala la probabilidad de disparo de los
  efectos probabilísticos por `min(1.0, base_p * strength)` (cap 1.0). Así `strength>1`
  hace que disparen más seguido (más aleatoriedad), y `strength=1.0` deja las
  probabilidades idénticas a hoy.

Escalado por efecto (neutro → cota escalada = neutro + (cota_actual − neutro) × strength):
- `crop_px`: 2..10 → round(2·s)..round(10·s) (≥0)
- `zoom_pct`: 1.0..1.05 → 1.0..(1.0 + 0.05·s)
- `rotate_deg`: ±1.5 → ±1.5·s
- `brightness`: ±0.03 → ±0.03·s
- `contrast`: 1.0±0.06 → 1.0 ± 0.06·s
- `saturation`: 1.0±0.10 → 1.0 ± 0.10·s
- `gamma`: 1.0±0.05 → 1.0 ± 0.05·s
- `noise`: 4..8 → round(4·s)..round(8·s), **con piso 4 cuando el efecto dispara**
  (niveles 2–3 los borra la compresión CRF 20 — comentario ya presente en el código)
- `speed`: 1.0±0.015 → 1.0 ± 0.015·s
- `trim_start_ms` / `trim_end_ms`: 0..150 → 0..round(150·s)

Probabilidades (mirror .5, zoom .7, rotate .6, noise .4, speed .5) → `min(1.0, p × strength)`.
Con `strength=1.0` quedan idénticas a hoy; `strength=2.4` empuja casi todo a disparar.

`apply_variant_and_metadata(input, output, meta, rng=None, enabled=None, strength=1.0)`
pasa `strength` a `generate_variant_params`.

## UI (`gui_premium_v7.py`, pantalla Forge)

En la card de Config, dos `SegmentedControl` del kit: **"Efectos"** y **"Fuerza"**,
ambos con `[Default, Light, Medio, Alto, Custom]`, default `"Default"`.
- `Efectos = Custom` → se muestran los 8 `ToggleRow` (`forge_fx_vars`); en otros niveles
  se ocultan y el preset define `enabled`.
- `Fuerza = Custom` → se muestra un `CTkSlider` 0–100% (+ label del %); en otros niveles
  se oculta y el preset define `strength`.

Vars nuevas: `self.forge_efectos_var` (StringVar "Default"), `self.forge_fuerza_var`
(StringVar "Default"), `self.forge_strength_slider`. Se conservan `self.forge_fx_vars`
(usados solo en `Efectos=Custom`).

Dos helpers puros (fáciles de testear):
- `efectos_to_enabled(level, fx_vars) -> dict[str,bool]`
- `fuerza_to_strength(level, slider_pct) -> float`

En `forge_process` / `forge_preview_metadata`: calcular `enabled` y `strength` desde los
dos ejes y pasarlos a `apply_variant_and_metadata(..., enabled=enabled, strength=strength)`.

## Tests

Backend (`tests/`, pytest):
- `strength=1.0` reproduce los rangos actuales exactamente (regresión de magnitud/probabilidad).
- `strength=0.5` reduce magnitudes ~mitad; `strength=2.4` las amplía; monótono Light<Medio<Alto.
- `noise` nunca baja de 4 cuando dispara.
- Un efecto en `enabled=False` nunca aplica, con cualquier `strength`.

Mapeos:
- `efectos_to_enabled("Default")` = 7 (sin mirror); `"Alto"`=8; `"Light"`=2; `"Medio"`=5;
  `"Custom"` = lectura de `fx_vars`.
- `fuerza_to_strength("Default") == fuerza_to_strength("Medio") == 1.0`; `"Light"=0.5`;
  `"Alto"=2.4`; `"Custom"` mapea el % del slider.

## Riesgos

- `Fuerza=Alto` (2.4×) puede empujar crop/zoom/rotate a degradación visible — es el
  trade-off buscado (más único vs. más degradado); el usuario lo elige a propósito.
- El guard de dimensiones pares (`libx264`/`yuv420p`) ya existe y cubre crop/zoom fuertes.
