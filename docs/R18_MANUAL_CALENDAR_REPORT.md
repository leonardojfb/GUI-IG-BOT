# R18 Calendario manual/export

Fecha: 2026-09-17

## Alcance validado

- `export_manual_package()` crea un ZIP portable schema v1 con entradas de
  calendario, metadata de destino y archivos remapeados bajo `media/`.
- Cada archivo incluye SHA-256 y la exportacion es atomica.
- `verify_manual_package()` valida estructura y bytes antes de importar o
  entregar el paquete.
- `preview_manual_package_import()` devuelve alcance y conflictos sin crear
  archivos.
- `import_manual_package()` exige confirmación explícita, extrae en temporal y
  publica el destino sólo cuando termina; no sobrescribe destinos existentes.
- No publica, no llama Meta y no modifica el manifest activo.
- `export_manifest_v2_package()` integra el lector del manifest v2, conserva
  destino/lane/placement y bloquea v1 o entries incompatibles.
- El panel local puede importar bajo la raíz de la instalación y registra cada
  importación confirmada en `CALENDARIO_POSTEO/manual_import_audit.jsonl`, con
  hash del paquete, actor, destino y cantidad; la previsualización no escribe.

## Limites

Falta comprobar capacidades reales de cada plataforma y ofrecer un editor
visual más completo del manifest operativo; el remapeo explícito por destino y
la auditoría de importaciones ya están disponibles en el panel local.
