# R19 Platform adapters

Fecha: 2026-09-17

## Alcance validado

- `PlatformAdapter` declara plataforma, capabilities y handlers sin efectos
  laterales al importar.
- `execute_platform_action()` soporta fases separadas:
  `prepare`, `deliver`, `schedule`, `publish` y `verify`.
- Una fase no declarada se rechaza; un handler ausente o resultado vacio no se
  considera exito.
- `execute_publication_group()` mantiene resultados por destino y devuelve
  `confirmed`, `partial` o `failed` sin propagar automáticamente un fallo
  hermano.
- `detect_downstream_duplicates()` bloquea la combinación repetida de raíz,
  destino y carril, permitiendo usos en carriles distintos.
- No hay llamadas Meta ni uso de cookies/sesiones en este contrato.

## Limites

R19 no certifica permisos, rate limits, media requirements ni publicación real.
Esos datos deben verificarse por cuenta y plataforma antes de conectar un
adapter externo. Los handlers incluidos en tests son simulaciones locales.
