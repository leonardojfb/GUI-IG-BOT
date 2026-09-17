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
- `build_telegram_bot_api_sender()` ofrece el transporte Bot API real con
  multipart nativo y `message_thread_id`; el token solo vive en memoria del
  sender y no se persiste en el ledger.

## Limites

La integración final con el worker Telegram existente, topics canónicos y
migración de historiales todavía requiere un gate operativo. No se reutilizan
cookies ni sesiones de Instagram.
