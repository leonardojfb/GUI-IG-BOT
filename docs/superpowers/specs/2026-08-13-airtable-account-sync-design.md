# Sincronización de cuentas Airtable → GUI — Diseño

## Objetivo

Hacer de una tabla de Airtable la fuente compartida de verdad para las cuentas. Cada instalación de la GUI podrá descargarla mediante un botón, reflejar sus altas, cambios y bajas en su propio `organizador.db`, y conservará localmente toda la operación de ese manager.

## Alcance y límites

- La dirección es exclusivamente **Airtable → GUI**. Ninguna edición local se envía a Airtable.
- La sincronización se inicia con el botón **Sincronizar Airtable** en Cuentas; no hay polling, servicio residente ni webhook.
- El ámbito son las filas de cuentas. Tandas, calendarios, videos, historial/fingerprints, estado de Telegram, preferencias y datos de ejecución permanecen locales por instalación.
- Una fila eliminada de Airtable elimina la cuenta correspondiente de `virtual_accounts` al confirmar la sincronización. No elimina carpetas ni historial operativo local.
- El `username` normalizado (sin `@`, sin espacios laterales, comparación sin distinguir mayúsculas) es la clave de conciliación. Cambiar un username equivale a eliminar la cuenta anterior y crear otra.

## Esquema de Airtable

Se configurará una tabla de cuentas que contiene estas columnas visibles para los VAs:

| Columna Airtable | Columna local | Regla |
|---|---|---|
| `Username` | `username` | Obligatorio y único; identifica la cuenta. |
| `2FA` | `two_factor` | Texto sensible; nunca se muestra en logs ni en el resumen de sincronización. |
| `VA` | `assigned_va` | Texto; si no hay valor, se usa `Sin Asignar`. |
| `Categoría` | `account_type` | Obligatorio; debe existir como categoría local. |
| `Trials desbloqueados` | `trials_active` | Checkbox/booleano. |
| `Día` | `account_day` | Texto de gestión; no cambia el calendario local. |
| `Red social` | `social_network` | Texto de gestión. |
| `VPN / Proxy` | `vpn_proxy` | Texto sensible; nunca se muestra en logs ni en el resumen. |
| `Link` | `account_link` | URL o texto. |

Los campos existentes administrados por la GUI que no están en la tabla (`ig_status`, `ig_label`, `followers`, `notes`, `limitations`, `videos_posted`, fechas, tandas e historial) no se sobrescriben durante la sincronización.

## Arquitectura

### Configuración local

Cada manager configurará sus propias credenciales y el identificador de base/tabla en un archivo local `airtable_config.json`, excluido de Git y de releases. El archivo contendrá únicamente:

```json
{
  "personal_access_token": "pat...",
  "base_id": "app...",
  "table_name": "Cuentas"
}
```

El token será un Personal Access Token de Airtable con permiso de lectura únicamente para esa base. No se incorporará al código, al SQLite, a registros ni a paquetes de actualización. La GUI mostrará una configuración inicial para guardar/validar los tres valores y un mensaje de error humano cuando falte alguno o Airtable rechace el acceso.

### Cliente y reconciliador

Un módulo aislado `airtable_sync.py` hará solicitudes paginadas a la API oficial de Airtable y convertirá sus registros a un modelo validado. Una capa de reconciliación comparará ese snapshot con `DatabaseManager.get_all_accounts()` y producirá un plan inmutable con tres listas: crear, actualizar y eliminar.

Después de que la GUI muestre el resumen y el manager confirme, una única transacción SQLite aplicará el plan. Si falla la descarga, el mapeo o la transacción, no se aplica un plan parcial y se conserva la base local intacta.

### Base local

`database.py` incorporará migraciones no destructivas para `two_factor`, `account_day`, `social_network`, `vpn_proxy` y `account_link`, además de métodos seguros para aplicar el plan de sincronización. La eliminación se limitará a la fila de `virtual_accounts`; las tablas históricas no se modificarán.

### Interfaz

El panel Cuentas incorporará:

- `Configurar Airtable`, para introducir o reemplazar la configuración local.
- `Sincronizar Airtable`, para descargar, validar y calcular el plan.
- Un diálogo de revisión con conteos y usernames de altas/cambios/bajas; las bajas requieren confirmación explícita.
- Un resultado claro: cuentas creadas, actualizadas, eliminadas o una razón accionable del fallo. La tabla se refresca solo después de una aplicación exitosa.

El botón no se mezcla con los flujos de Logística, Telegram o verificación de cuentas.

## Validación y errores

- `Username` y `Categoría` vacíos, usernames duplicados tras normalización, tipos de Airtable incompatibles o categorías inválidas detienen la sincronización antes de tocar SQLite.
- Una categoría nueva observada en Airtable se crea explícitamente como categoría local en la misma transacción para que la cuenta sea operable; no se altera ninguna categoría existente.
- La respuesta de Airtable se pagina hasta completar todos los registros.
- Errores de red, token inválido, base/tabla no encontrada, rate limit y SQLite bloqueado se traducen a mensajes en español que explican el siguiente paso.
- No se imprimen token, 2FA ni VPN/proxy en consola, logs, diálogo de revisión o tests.

## Pruebas requeridas

- Mapeo de cada columna Airtable, incluidos checkbox, celdas vacías y usernames normalizados.
- Paginación del cliente, errores HTTP y ausencia de secretos en excepciones.
- Planes de crear, actualizar, no-op y borrar; prueba de username renombrado como alta+baja.
- Validación previa que impide cualquier escritura si hay una fila inválida o duplicada.
- Aplicación transaccional que conserva campos locales no administrados por Airtable.
- Prueba de integración con SQLite temporal y prueba de UI para resumen/confirmación de bajas.

## Fuera de alcance

- Edición o envío de información desde la GUI hacia Airtable.
- Sincronizar VAs, tandas, calendarios, Telegram, horarios o historial.
- Automatización en segundo plano, webhooks o un servidor central.
- Eliminar archivos o carpetas locales cuando se borra una cuenta en Airtable.
