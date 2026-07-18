# GUÍA PARA GESTOR DE CONTENIDO — MÉTODO IG VIDEOS
*Documento técnico-operativo para agentes que administran el contenido del sistema*

---

## 1. QUÉ HACE ESTE SISTEMA

Este bot automatiza el ciclo completo de publicación de videos en Instagram a través de múltiples cuentas virtuales. El flujo va desde clips de video crudos hasta la entrega organizada a asistentes virtuales (VAs) vía Telegram, listos para publicar.

El sistema tiene 4 etapas:

```
CLIPS CRUDOS → RENDERIZADO → DISTRIBUCIÓN → ENVÍO A TELEGRAM
  (inputs/)    (videos.py)  (Organizador.py) (organizadortg.py)
```

---

## 2. ESTRUCTURA DE CARPETAS QUE DEBES MANTENER

```
Método IG VIDEOS/
│
├── inputs/                    ← ACÁ SUBES EL CONTENIDO CRUDO
│   ├── [carpeta_P1]/          ← Clips de apertura / hooks / UGC
│   └── [carpeta_P2]/          ← Clips de cierre / contenido / produto
│
├── videos_finales/            ← RENDERIZADOS (no tocar manualmente)
│   └── [nombre_tanda]/
│       └── CATEGORIA__P1id__P2id.mp4
│
├── CALENDARIO_POSTEO/         ← DISTRIBUCIÓN POR DÍA (no tocar manualmente)
│   ├── Dia_1/
│   │   ├── cuenta1/
│   │   │   └── video.mp4
│   │   └── cuenta2/
│   │       └── video.mp4
│   └── Dia_2/
│       └── ...
│
├── captions.txt               ← CAPTIONS / TEXTOS DE LOS POSTS
└── organizador.db             ← Base de datos del sistema (no tocar)
```

---

## 3. CONCEPTOS CLAVE

### Tanda
Una **tanda** es la unidad de contenido. Es la combinación de:
- **P1** (Parte 1): carpeta con clips de apertura, hooks, o UGC
- **P2** (Parte 2): carpeta con clips de contenido, producto, o cierre

El sistema genera automáticamente **todas las combinaciones posibles** (producto cartesiano):
- Si tienes 10 clips en P1 y 10 clips en P2 → genera 100 videos únicos
- Si tienes 20 P1 y 15 P2 → genera 300 videos únicos

### Categorías de cuenta
Cada cuenta tiene un tipo que define qué contenido recibe:
- **SUICIDE**: Cuentas de alto engagement (burner). Reciben un tipo de mezcla.
- **PROMO**: Cuentas de promoción. Reciben otro tipo de mezcla.
- Se pueden agregar categorías nuevas desde la GUI.

### Anti-Choque (Anti-Collision)
El sistema garantiza que:
1. **Ninguna cuenta ve el mismo clip P1 dos veces el mismo día** (regla dura)
2. **Ninguna cuenta ve la misma combinación P1+P2 nunca** (regla dura)
3. Los clips P1 se rotan entre cuentas para evitar solapamiento en el mismo horario (regla blanda)

Esto es crítico para que Instagram no detecte contenido duplicado entre cuentas.

### Fill-Up
Cuando el stock de videos se agota antes de completar los días planificados, el sistema genera combinaciones adicionales automáticamente. Esto evita que el calendario quede incompleto.

### VAs (Asistentes Virtuales)
Cada VA tiene su propio grupo de Telegram. El sistema crea un **topic** (hilo) por cada cuenta que administra ese VA. Los videos se envían al topic correcto con metadatos de horario.

---

## 4. QUÉ NECESITAS PREPARAR COMO GESTOR DE CONTENIDO

### 4.1 Clips de video (Obligatorio)

**P1 — Clips de apertura/hook:**
- Duración recomendada: 3–10 segundos
- Formato: `.mp4` o `.mov`
- Resolución: cualquiera (el sistema escala a 1080×1920 automáticamente)
- Nombrar los archivos con un ID descriptivo: `hook_baile_01.mp4`, `ugc_testimonio_03.mp4`
- Colocar en: `inputs/[nombre_carpeta_p1]/`

**P2 — Clips de contenido/producto:**
- Duración recomendada: 10–60 segundos
- Mismo formato y naming
- Colocar en: `inputs/[nombre_carpeta_p2]/`

**Regla de escalabilidad:** El número de videos únicos que genera el sistema es `cant_P1 × cant_P2`. Para cubrir 30 días con 46 cuentas se necesitan ~1380 videos únicos. Con 30 clips P1 y 50 clips P2 tienes 1500 combinaciones.

### 4.2 Archivo de captions (`captions.txt`)

El archivo debe tener el siguiente formato exacto:

```
[1 - Enero]:
Tu texto del caption aquí. Puede ser largo.
#hashtag1 #hashtag2 #hashtag3 #hashtag4

[2 - Enero]:
Otro caption diferente.
#otrohashtag #mashashtags
```

**Notas importantes:**
- Cada bloque empieza con `[número - texto]:` en su propia línea
- Los hashtags al final de cada bloque se mezclan aleatoriamente al publicar (anti-spam)
- El sistema elige un caption al azar por cada video
- Cuantos más captions distintos tengas, mejor (mínimo 10, ideal 30+)

### 4.3 Configuración en la GUI (una sola vez por tanda)

En la interfaz gráfica del bot, el operador debe registrar:
1. **Nueva Tanda**: nombre, carpeta P1, carpeta P2, ruta del `captions.txt`
2. **Cuentas**: username de Instagram, categoría (SUICIDE/PROMO), VA asignado
3. **VA**: nombre del asistente y ID de su grupo de Telegram

---

## 5. CICLO OPERATIVO SEMANAL

### Lunes — Preparación de contenido
- [ ] Conseguir/editar clips P1 y P2 para la semana
- [ ] Subir a las carpetas `inputs/` correspondientes
- [ ] Actualizar `captions.txt` con textos nuevos si los anteriores se agotaron

### Martes — Renderizado
- [ ] En la GUI: ir a pestaña de Tandas → seleccionar tanda → "Renderizar"
- [ ] El sistema genera todas las combinaciones P1×P2 automáticamente
- [ ] Verificar que aparecen videos en `videos_finales/[nombre_tanda]/`
- [ ] Tiempo estimado: 1–4 horas dependiendo de cantidad y GPU disponible

### Miércoles — Distribución
- [ ] En la GUI: ir a pestaña de Organización → seleccionar tanda y categoría
- [ ] Configurar cuántos días organizar y la cuota diaria por cuenta
- [ ] Ejecutar distribución
- [ ] Verificar que se crearon las carpetas `CALENDARIO_POSTEO/Dia_X/`

### Jueves–Viernes — Envío a Telegram
- [ ] En la GUI: pestaña Telegram → seleccionar fecha de inicio → "Ejecutar"
- [ ] El bot envía los videos organizados al grupo Telegram de cada VA
- [ ] Cada VA recibe sus cuentas en topics separados con horarios sugeridos

### Fin de semana — Publicación
- [ ] Los VAs publican manualmente desde sus topics de Telegram según los horarios indicados
- [ ] El bot indica: categoría, día, hora sugerida y formato (Reel)

---

## 6. HORARIOS SUGERIDOS DE PUBLICACIÓN

El sistema asigna automáticamente estos horarios según el día de la semana (horario US/LA):

| Día | Slot 1 | Slot 2 | Slot 3 | Slot 4 |
|-----|--------|--------|--------|--------|
| Lunes | 8:00 AM | 1:00 PM | 7:00 PM | 9:00 AM |
| Martes | 8:00 AM | 12:00 PM | 7:00 PM | 9:00 AM |
| Miércoles | 9:00 AM | 1:00 PM | 9:00 PM | 10:00 AM |
| Jueves | 8:00 AM | 1:00 PM | 7:00 PM | 9:30 AM |
| Viernes | 9:00 AM | 1:00 PM | 8:00 PM | 10:00 AM |
| Sábado | 11:00 AM | 3:00 PM | 8:00 PM | 12:00 PM |
| Domingo | 12:00 PM | 4:00 PM | 9:00 PM | 1:00 PM |

---

## 7. MODELO ESCALABLE

### Nivel 1 — Operación mínima (1 VA, 5–10 cuentas)
- 1 tanda activa
- 10 clips P1 + 10 clips P2 = 100 combinaciones ≈ 2 días de stock
- 1 VA con su grupo de Telegram
- Meta: 2–4 posts/día por cuenta

### Nivel 2 — Operación media (2–3 VAs, 10–30 cuentas)
- 2–3 tandas activas (se pueden combinar en distribución)
- 30 clips P1 + 30 clips P2 = 900 combinaciones ≈ 10 días de stock
- Cada VA administra 5–15 cuentas en su grupo
- Meta: 3–4 posts/día por cuenta

### Nivel 3 — Operación escalada (3+ VAs, 30+ cuentas)
- 3+ tandas activas con contenido fresco semanal
- 50+ clips P1 + 50+ clips P2 = 2500+ combinaciones ≈ 30 días de stock
- VAs por categoría (un VA para PROMO, otro para SUICIDE)
- Cuota diaria: 46 videos/día totales distribuidos entre todas las cuentas
- Fill-up habilitado para rellenar días sin bajar la frecuencia de publicación

### Regla de oro para escalar
> **Stock mínimo = (número de cuentas) × (posts/día por cuenta) × (días de cobertura deseados)**
>
> Ejemplo: 20 cuentas × 3 posts/día × 14 días = **840 videos únicos mínimos**
> Para eso necesitas: √840 ≈ 29 clips P1 y 29 clips P2

---

## 8. CÓMO NOMBRAR TUS CLIPS (CONVENCIÓN)

Para que los reportes de distribución sean legibles, usa nombres descriptivos:

**P1 (hooks/aperturas):**
```
hook_caminar_01.mp4
ugc_testimonio_feliz_02.mp4
transicion_zoom_03.mp4
```

**P2 (contenido/productos):**
```
producto_principal_01.mp4
oferta_precio_02.mp4
cta_compra_ahora_03.mp4
```

**Videos renderizados** (generados automáticamente, no los crees tú):
```
SUICIDE__hook_caminar_01__producto_principal_01.mp4
```

---

## 9. SEÑALES DE ALERTA — QUÉ MONITOREAR

| Señal | Causa probable | Acción |
|-------|---------------|--------|
| "No hay videos en CALENDARIO_POSTEO" | No se ejecutó la distribución | Ejecutar Organización desde la GUI |
| "⚠️ Sin video válido para cuenta X" | Stock agotado y fill-up insuficiente | Agregar más clips a inputs/ y re-renderizar |
| "❌ Topic no encontrado" | El grupo de Telegram fue recreado | Actualizar el ID del grupo del VA en la GUI |
| Fill-up activo desde el Día 1 | Stock muy bajo desde el inicio | Necesitas más clips P1 o P2 |
| Mismo clip aparece en dos cuentas | Bug de anti-choque (raro) | Revisar que los filenames no tengan espacios raros |

---

## 10. ARCHIVOS QUE EL GESTOR NUNCA DEBE MODIFICAR MANUALMENTE

- `organizador.db` — Base de datos del sistema
- `telegram_state_v11.json` — Estado de los topics de Telegram
- `fingerprint_history.json` — Historial de videos enviados
- Carpeta `CALENDARIO_POSTEO/` completa — Dejarla al sistema
- Carpeta `videos_finales/` — Dejarla al sistema

**Sí puedes/debes modificar:**
- `inputs/` — Agregar clips nuevos
- `captions.txt` — Actualizar textos y hashtags
- `styles/` — Si existe, configuración visual de la GUI

---

## 11. CHECKLIST PARA INCORPORAR CONTENIDO NUEVO

```
ANTES DE SUBIR CLIPS:
  [ ] Clips en formato .mp4 o .mov
  [ ] Resolución mínima 720p (el sistema sube a 1080p si puede)
  [ ] Sin espacios extraños en los nombres de archivo
  [ ] P1 y P2 en carpetas separadas dentro de inputs/

ANTES DE RENDERIZAR:
  [ ] Tanda registrada en la GUI con las carpetas correctas
  [ ] captions.txt actualizado con al menos 10 captions
  [ ] FFmpeg instalado en el sistema

ANTES DE DISTRIBUIR:
  [ ] Renderizado completado (videos en videos_finales/)
  [ ] Cuentas registradas en la GUI con su categoría y VA
  [ ] Cuota diaria y días configurados

ANTES DE ENVIAR A TELEGRAM:
  [ ] VAs tienen su grupo de Telegram configurado
  [ ] CALENDARIO_POSTEO tiene las carpetas Dia_X
  [ ] Fecha de inicio seleccionada correctamente
```
