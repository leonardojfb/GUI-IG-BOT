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
- `organizadortg._send_video_to_topic()` registra el envío confirmado cuando
  recibe DB/asset/idempotency context, pero conserva la llamada legacy cuando
  un test o wrapper sustituye el handler.
- El escaneo legacy acepta imágenes (`jpg`, `jpeg`, `png`, `webp`) y
  documentos (`pdf`, `zip`) además de los videos históricos.
- `organizadortg._send_media_to_topic()` conecta esos archivos al worker
  existente con el mismo topic, caption, botón y ledger; los videos mantienen
  su ruta de compresión específica.
- `migrate_legacy_history()` importa filas históricas ya confirmadas sólo si
  contienen `message_id`, sin abrir red ni reenviar medios; omite filas
  incompletas y es idempotente por la identidad del ledger.

## Limites

Topics canónicos todavía requieren un gate operativo. La migración local de
historial quedó validada, pero falta ejecutar el importador contra un archivo
histórico real previamente revisado. Falta un smoke contra un bot/grupo
controlado; los tests no demuestran publicación externa. No se reutilizan
cookies ni sesiones de Instagram.
