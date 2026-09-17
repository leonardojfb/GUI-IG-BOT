# R18 Calendario manual/export

Fecha: 2026-09-17

## Alcance validado

- `export_manual_package()` crea un ZIP portable schema v1 con entradas de
  calendario, metadata de destino y archivos remapeados bajo `media/`.
- Cada archivo incluye SHA-256 y la exportacion es atomica.
- `verify_manual_package()` valida estructura y bytes antes de importar o
  entregar el paquete.
- No publica, no llama Meta y no modifica el manifest activo.

## Limites

Falta conectar el paquete a manifest v2, comprobar capacidades reales de cada
plataforma y ofrecer el remapeo desde una UI con confirmacion explicita.
