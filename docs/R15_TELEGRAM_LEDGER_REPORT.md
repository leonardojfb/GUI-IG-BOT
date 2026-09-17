# R15 Telegram multiformato

Fecha: 2026-09-17

## Alcance validado

- `media_method()` usa `sendPhoto`, `sendVideo` o `sendDocument` según la
  extensión nativa.
- `deliver_media()` exige una idempotency key y registra solo respuestas
  confirmadas con `message_id`.
- El ledger conserva `asset_ref`, bot, chat, topic, ruta, método, caption y
  timestamp; un mismo envío confirmado no se repite.
- Fallos o respuestas sin `message_id` no generan una fila exitosa.
- El sender se inyecta para mantener pruebas sin red y permitir integrar el
  transporte actual gradualmente.

## Limites

El envío real, topics canónicos y migración de historiales requieren integrar
este ledger con el worker Telegram existente en el siguiente checkpoint. No se
reutilizan cookies ni sesiones de Instagram.
