# R17 CRM ampliado

Fecha: 2026-09-17

## Alcance validado

- `build_identity()` devuelve una identidad tipada de cuenta social con
  plataforma, account ID, usuario normalizado y VA.
- `summarize_metrics()` calcula posts, likes, comments, shares, engagement y
  tasa reproducible sin inventar datos ausentes.
- `export_metrics_csv()` escribe de forma atomica y excluye claves de cookies,
  sesiones, tokens, passwords y secretos.
- El modulo es local y read-only; no llama APIs ni modifica cuentas.

## Limites

Faltan conectores de metricas reales, historial tipado de dispositivo/red y
reglas de viralidad con evidencia temporal. Esas entradas deben llegar saneadas
y con account/org context antes de habilitar acciones.
