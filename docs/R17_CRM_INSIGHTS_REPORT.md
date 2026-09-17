# R17 CRM ampliado

Fecha: 2026-09-17

## Alcance validado

- `build_identity()` devuelve una identidad tipada de cuenta social con
  plataforma, account ID, usuario normalizado y VA.
- `summarize_metrics()` calcula posts, likes, comments, shares, engagement y
  tasa reproducible sin inventar datos ausentes.
- `export_metrics_csv()` escribe de forma atomica y excluye claves de cookies,
  sesiones, tokens, passwords y secretos.
- `score_virality()` aplica umbrales explícitos a la tasa calculada y
  `build_infrastructure_event()` guarda referencias hash de dispositivo/red,
  nunca los valores crudos.
- `crm_metric_snapshots` persiste snapshots por `account_id` y `observed_at`,
  rechaza duplicados del mismo instante y filtra claves sensibles antes de
  escribir JSON.
- El modulo es local y read-only; no llama APIs ni modifica cuentas.

## Limites

Faltan conectores de métricas reales con account/org context y una UI de serie
temporal. Las entradas deben llegar saneadas antes de habilitar acciones.
