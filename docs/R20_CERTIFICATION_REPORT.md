# R20 Certificacion final

Fecha: 2026-09-17

## Alcance validado

- `certify_checkpoints()` exige evidencia local para R11, R12, R13, R14, R15,
  R16, R17, R18, R19 y la suite global.
- El resultado se etiqueta `certified_local`, no como certificacion de
  producción.
- El reporte declara de forma obligatoria que media de producción y publicación
  real no fueron ejecutadas.
- `make_gate_evidence()` permite registrar comando, cantidad de pruebas y
  skips; los booleanos previos siguen aceptándose solo como evidencia legacy.
- La evidencia estructurada exige al menos una prueba pasada y un número de
  skips no negativo; `passed=0` ya no puede certificar un gate.
- Suite global ejecutada desde el worktree aislado: `540 passed, 0 skipped,
  7 subtests passed`.
- Release/updater incluyen el gate de forma aditiva y bootstrap permanece
  estable.

## Limites

La certificacion final del producto requiere todavía recorrer LEG-01..56,
probar saltos por cohortes del updater, realizar un ciclo piloto controlado y
validar servicios externos con cuentas y medios reales.
