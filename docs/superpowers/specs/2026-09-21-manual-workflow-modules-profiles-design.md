# Configuracion manual de pasos y perfiles opcionales

## Objetivo

Permitir construir un workflow modular de Forge, Logistica y Telegram desde formularios manuales completos, sin plantillas ni perfiles precargados. Los perfiles se conservan como una ayuda opcional: el usuario puede guardar una configuracion y cargarla explicitamente, pero nunca se aplica una configuracion por defecto.

## Alcance

El editor modular tendra un flujo de **Agregar paso**. Cada paso comienza sin valores de negocio y requiere elegir explicitamente su modulo:

- **Forge**: elegir `Normal` o `Trials` y exponer las mismas opciones de la pestaña Forge tradicional: videos, tanda, copias, dias, efectos, fuerza, ajustes Custom, micro-ediciones y preview de metadata.
- **Logistica**: elegir `Por tandas` o `Por cuentas` y exponer los campos del modulo tradicional: tandas, destino, cuota, dias, Fill-up, cuentas, captions y opciones propias del modo.
- **Telegram**: exponer cuentas, fecha, horarios, modo express y manejo de topics como en la pestaña Telegram.

Cada paso se puede editar antes de agregarlo a la cola. La vinculacion al output anterior se elige de forma explicita cuando los contratos son compatibles.

## Perfiles opcionales

Cada modulo tendra acciones separadas:

- **Cargar perfil**: abre solo perfiles compatibles con el modulo y subtipo seleccionado.
- **Guardar como perfil**: guarda los valores actuales con un nombre elegido por el usuario.
- **Limpiar formulario**: devuelve todos los campos a estado vacio/manual, sin seleccionar ningun perfil.

Guardar un perfil no agrega un job. Cargarlo solo rellena el formulario; el usuario debe confirmar y agregar el paso. Los perfiles se identifican por modulo y subtipo para evitar cargar una receta de Trials en Forge Normal o una configuracion de cuentas en Logistica por tandas. Los perfiles existentes no se aplican automaticamente ni se convierten en defaults.

## Flujo de datos

1. El usuario crea un paso y selecciona modulo/subtipo.
2. El formulario captura los valores reales del modulo tradicional.
3. El usuario puede cargar, editar o guardar un perfil opcional.
4. Al confirmar, se valida la receta completa y se agrega un job inmutable a la cola.
5. Para un paso posterior, la interfaz ofrece `Usar output del paso anterior` solo si el contrato de entrada coincide.
6. Workflows muestra el orden, contrato de entrada, contrato de salida y binding de cada job.

La cadena objetivo queda expresada como:

`Forge (TandaOutput) -> Logistica (ManifestOutput) -> Telegram (TelegramOutput)`

## Persistencia y compatibilidad

Las recetas guardadas en la cola continuan siendo snapshots inmutables de los formularios. Los perfiles se almacenan separados de los workflows y no modifican una receta ya agregada. Las colas existentes deben seguir pudiendo leerse y editarse; los jobs historicos conservan su recipe y binding.

## Validacion y errores

- Un paso no se puede agregar sin modulo/subtipo y campos obligatorios completos.
- Forge valida videos, tanda, copias, dias y metadata antes de guardar.
- Logistica valida el modo y sus campos obligatorios.
- Telegram valida al menos una cuenta y fecha.
- Un perfil incompatible no aparece como opcion.
- Ningun error debe reemplazar silenciosamente texto introducido por el usuario.

## Criterios de aceptacion

1. Abrir Workflows muestra un formulario limpio, sin bloques, perfiles ni horarios ficticios.
2. Agregar un paso muestra la eleccion explicita de Forge, Logistica o Telegram.
3. Forge Normal y Forge Trials muestran y persisten opciones equivalentes a la pestaña Forge tradicional.
4. Logistica por tandas y por cuentas muestran y persisten sus opciones propias.
5. Telegram muestra y persiste sus opciones propias.
6. Un usuario puede guardar un perfil, limpiar el formulario y cargarlo despues de forma explicita.
7. Cargar un perfil no agrega automaticamente un job.
8. La cadena Forge -> Logistica -> Telegram conserva los bindings de output anterior y se ve completa en la cola.
9. Los tests cubren formulario limpio, perfiles opcionales, compatibilidad por modulo/subtipo, captura de recetas y bindings.

## Fuera de alcance de esta especificacion

La ejecucion real de los handlers de Forge y Logistica queda separada de la edicion y persistencia de recetas. Esta especificacion garantiza que los pasos se configuren, guarden y encadenen correctamente; el runner debe conectarse a esos handlers en una tarea posterior o paralela.
