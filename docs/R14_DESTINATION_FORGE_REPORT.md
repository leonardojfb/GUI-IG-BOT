# R14 Forge por destinos

Fecha: 2026-09-17

## Alcance validado

- `preview_destination_forge()` expande cada video por cuenta, contenedor,
  perfil y cantidad de copias.
- La cuenta se normaliza case-insensitive y el lane se congela como
  `contenedor:perfil` para evitar colisiones entre destinos incompatibles.
- `reserve_destination_preview()` delega en la reserva atomica R08, con TTL,
  deteccion de conflicto y comprobacion de cobertura del preview.
- El modulo no renderiza ni publica: la reserva es un gate previo al job R10.
- Release/updater incluyen el contrato sin modificar bootstrap.

## Limites

El siguiente paso debe crear jobs `forge.copy` por assignment y liberar o
confirmar reservas segun cada resultado. La pantalla de destinos y la
reconciliacion post-render quedan pendientes.
