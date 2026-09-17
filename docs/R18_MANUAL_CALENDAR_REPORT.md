# R18 Calendario manual/export

Fecha: 2026-09-17

## Alcance validado

- `export_manual_package()` crea un ZIP portable schema v1 con entradas de
  calendario, metadata de destino y archivos remapeados bajo `media/`.
- Cada archivo incluye SHA-256 y la exportacion es atomica.
- `verify_manual_package()` valida estructura y bytes antes de importar o
  entregar el paquete.
- No publica, no llama Meta y no modifica el manifest activo.
- `export_manifest_v2_package()` integra el lector del manifest v2, conserva
  destino/lane/placement y bloquea v1 o entries incompatibles.

## Limites

Falta comprobar capacidades reales de cada plataforma y ofrecer el remapeo
desde una UI con confirmacion explicita.
