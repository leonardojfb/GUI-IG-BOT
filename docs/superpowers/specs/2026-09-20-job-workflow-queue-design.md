# Cola de jobs encadenados para workflows

Fecha: 2026-09-20
Checkout objetivo: `.worktrees/r00-reproducible-baseline`

## Objetivo

Permitir agregar cualquier operación compatible a un workflow mediante un
botón visible **“Agregar a workflow”**, ordenar los jobs, conectar la salida de
un job con la entrada del siguiente y ejecutar el flujo de forma persistente.

Caso principal:

`Forge tanda SPAM -> Logística tanda SPAM con cuentas SPAM -> Telegram send all`

La solución reutiliza `durable_jobs.py`, `job_runner.py` y el panel web
existente de Workflows/Ejecuciones. No crea una segunda máquina de estados.

## Modelo

`workflow_store` sigue guardando recetas y versiones inmutables. Se añadirá
una composición de pasos de workflow que guarda, por posición:

- tipo de job y configuración congelada;
- referencia al origen del job, cuando exista;
- contrato de entrada requerido;
- binding de entrada (`asset`, `step_output` o `previous_output`); y
- contrato de salida producido.

Al pulsar **“Agregar a workflow”** se congela la receta/configuración del job,
no se reutiliza su archivo final. Cada ejecución materializa un nuevo trabajo
durable y genera outputs físicos nuevos. Los nombres, IDs y lineage se
conservan como metadatos, pero no son la única identidad del output.

Contratos iniciales:

| Paso | Entrada | Salida |
| --- | --- | --- |
| `forge.tanda` | assets/videos y configuración Forge | `TandaOutput` con tanda, raíz y archivos |
| `logistica.tanda` | `TandaOutput` o tanda seleccionada | `ManifestOutput` con manifest y tareas |
| `telegram.send` | `ManifestOutput` o tareas listas | `TelegramOutput` con cola y resultados |

Los pasos futuros —Editor, Photo Forge y otros productores existentes— se
incorporan mediante el mismo contrato, sin cambiar el significado de los
contratos anteriores.

## Composición y ejecución

La vista de jobs mostrará el botón en cada job compatible. Al pulsarlo, el
operador elige un workflow existente o crea uno nuevo. El workflow mostrará
los pasos en orden, permitirá reordenarlos y ofrecerá únicamente bindings de
entrada compatibles. Si se agrega un job posterior, podrá seleccionar el
output de un paso anterior; la validación impedirá guardar una conexión
incompatible o circular.

Al ejecutar un workflow se crea una ejecución nueva y un job durable padre con
un step por operación. Cada step depende del anterior cuando el binding lo
requiere; el runner existente controla leases, checkpoints, reintentos y
bloqueo de dependientes. Un fallo bloquea los pasos descendientes, preserva
los outputs completados y permite reanudar desde el último step correcto.

La pantalla `Ejecuciones` mostrará workflow, ejecución, posición, estado,
input resuelto, output, intentos y error. Los estados de producción, cola de
Telegram y entrega no se confunden: un output listo no se considera enviado.

## Telegram

Cada workflow tendrá una opción explícita:

- `queue_only`: ejecuta hasta generar la cola Telegram y deja las tareas listas;
- `send_on_run`: después de Logística ejecuta el envío y registra el resultado
  por tarea.

El valor queda congelado en el snapshot de ejecución. El envío reutiliza el
ledger/idempotencia de Telegram; reanudar no debe duplicar mensajes. No se
añade publicación automática en Instagram/Facebook.

## API y UI

Se añadirán endpoints autenticados para:

- listar jobs con acciones disponibles;
- agregar/quitar/reordenar pasos de un workflow;
- vincular la entrada de un paso con la salida de otro;
- guardar la opción Telegram; y
- ejecutar, consultar y reanudar una ejecución.

El frontend renderizará el botón exacto **“Agregar a workflow”** en todos los
jobs compatibles, un editor de pasos ordenados y el selector explícito de
Telegram. Los errores de validación se mostrarán en la interfaz y no
reescribirán silenciosamente la configuración del job.

## Pruebas y límites

Se cubrirán con SQLite temporal y handlers controlados:

1. botón y endpoint agregan jobs en el orden pulsado;
2. el output de Forge llega como input de Logística;
3. el manifest de Logística llega a Telegram;
4. un ciclo o binding incompatible se rechaza;
5. una falla bloquea dependientes y permite reanudar;
6. `queue_only` no envía y `send_on_run` sí invoca el delivery handler;
7. un retry/restart no duplica outputs ni mensajes;
8. el panel web muestra estados y errores por step.

La entrega no se considerará prueba de publicación en Meta ni validación de
un envío real sin credenciales, media y autorización operativa. Los cambios
se limitarán al checkout seleccionado y no tocarán datos históricos durante
las pruebas.
