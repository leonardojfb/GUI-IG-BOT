# Por Cuentas Multicanal

## Objetivo

Extender Logistica Por Cuentas para calendarizar y entregar manualmente Reels,
Stories, Posts y Marketplace de Instagram/Facebook en una agenda unica por
cuenta, sin copiar archivos a `CALENDARIO_POSTEO` y sin publicar en Meta.

## Invariantes

- El archivo final permanece en su ruta de produccion. `source_path` es la
  fuente de verdad para Telegram y `telegram_filename` solo define su nombre
  de entrega.
- Forge/Photo Forge producen los finales por cuenta cuando corresponda;
  Logistica solo reserva, organiza y entrega rutas existentes.
- Una ejecucion nueva nunca mueve ni elimina publicaciones ya calendarizadas.
- La agenda se ordena por cuenta, fecha local, hora local y secuencia.
- Un choque exacto de cuenta + fecha + hora se bloquea en preview; no se mueve
  contenido silenciosamente.
- Reels Normal/Trial existentes mantienen sus contratos de captions, topics y
  entrega hasta que el nuevo carril equivalente este validado.
- No se agregan Docker, OAuth Meta ni publicacion automatica.

## Fases

### 1. Contrato de agenda y planificador puro

Agregar campos opcionales y compatibles al manifest: fecha/hora local, zona,
tipo de medio, carril y plan. Crear un planificador puro que combine entradas
existentes con solicitudes nuevas, las ordene y reporte choques exactos.

Validacion: pruebas de insercion 10:00/12:00/13:00, preservacion de entradas,
zona horaria, choque exacto y compatibilidad con entradas historicas day/slot.

### 2. Motor Por Cuentas sin copias

Separar la seleccion de archivos del planificador actual de Reels. Por Cuentas
generara entradas del manifest desde rutas finales seleccionadas y conservara
los archivos existentes. La ejecucion sera primero preview y confirmacion.

Validacion: plan de dos cuentas, varias tandas, preservacion de calendario
ajeno, y que no se cree ni copie `CALENDARIO_POSTEO`.

### 3. Carriles y pantalla de Logistica

Agregar una seccion Carriles a Por Cuentas: destino, fuente, tipo de medio,
cuenta, cantidad diaria, cada N dias, horas, fecha inicial, prioridad y
captions/enlace de Story. Mostrar un calendario consolidado antes de confirmar.

Validacion: Reels/Stories/Posts/Marketplace intercalados para una cuenta y
calendarios independientes para dos cuentas.

### 4. Imagenes

Crear el productor de imagenes finales sin tocar originales. Sus salidas se
registran con identidad durable y se seleccionan desde Carriles. No depende de
P1/P2 ni de la ruta del calendario.

Validacion: una foto final por cuenta, deteccion de repeticion dentro de un
carril y uso permitido en carriles distintos cuando la regla lo permita.

### 5. Entrega Telegram multimedio

Extender el lector del manifest para todos los destinos manuales. Entregar
video, foto o documento segun `media_kind`, en un topic por cuenta y ordenado
por fecha/hora. Entregado y Publicado permanecen como estados distintos.

Validacion: fake Telegram para orden mixto, caption, enlace Story, archivo
correcto y no-publicacion Meta.

### 6. Migracion y release

Migracion aditiva, prueba con una copia de manifest real, release code-only y
prueba manual en la GUI instalada. La actualizacion no incluye DB, manifests
ni media.

## Estado de Implementacion

Rama de trabajo: `feature/por-cuentas-multicanal`.

- Implementado: planificador y deteccion de choques por identidad/fecha/hora;
  insercion atomica al manifiesto; carriles manuales Instagram/Facebook desde
  Logistica > Por Cuentas; defaults locales editables; links por identidad;
  pantalla Calendario con filtros, detalles y preview de imagen.
- Cuentas permite configurar un dominio base de Story y un link propio por
  identidad; la resolucion queda en SQLite local y no se agrega a los campos
  sincronizados con Airtable.
- Implementado parcialmente: Photo Forge genera 1-20 variantes deterministas
  por imagen e identidad, con perfiles Original, Story 9:16, Post 4:5, cuadrado,
  portada 16:9 y Photo Reel imagen. Logística filtra el perfil al tomar finales
  Photo Forge; su default es por destino y queda configurable. El carril manual
  Instagram Photo Reel valida que sus entradas procedan del perfil Photo Reel
  y las entrega a Telegram como imagen. Los presets de intensidad cambian encuadre,
  luz, contraste, color, gamma, nitidez, rotacion y grano; el perfil limita
  resolucion y calidad JPEG/WebP queda registrada. El original no se modifica;
  los renders eliminan EXIF y conservan ICC si es compatible. El preview renderiza el primer
  resultado. Receta, parámetros, fuente y hashes se guardan como campos
  aditivos del manifiesto v1 para conservar lectores anteriores; Logistica
  admite manifiestos v1/v2 y valida SHA-256 por identidad. Al terminar,
  Logistica abre con la carpeta de salida y las identidades elegidas.
- Implementado parcialmente de LEG-53: rangos manuales mínimos/máximos para 11
  parámetros, usados por igual en preview y render y guardados en cada receta;
  los campos vacíos conservan el preset. Sigue pendiente perspectiva, perfiles
  de metadata configurables, conexión con Vault/captions, cola de jobs persistente,
  preview/selección individual de variantes y repetición de receta como objeto
  separado de una ejecución. No presentar Photo Forge como implementación
  completa del prototipo mientras esos puntos sigan pendientes.
- Si la raiz de carril contiene `photo_forge_manifest.json`, Logistica toma
  solo las salidas registradas para cada identidad y verifica `output_sha256`
  antes de calendarizar. Se conserva el orden del manifiesto; faltantes,
  cambios de bytes y rutas fuera de la carpeta de identidad se bloquean. Las
  rutas se resuelven por nombre dentro de la raiz actual para admitir lotes
  movidos sin confiar en sus rutas absolutas antiguas.
- Implementado: entrega de imagen/video por Telegram, topics por identidad o
  separados por destino, entrega ordenada y estados `planned`, `sent_telegram`
  y `published`. La confirmacion `published` se reconcilia con Airtable.
- Los jobs con `lane_id` siempre envian su mensaje de contexto aunque este
  activo **Envío express**; fecha, destino y metadatos Marketplace no se omiten.
- Los Reels legacy sin fecha explícita resuelven su hora local usando la fecha
  programada; Telegram reutiliza esa resolución para mostrar la hora y no
  recalcula el offset DST con la fecha actual.
- Las solicitudes Telegram tienen timeout distinto para API JSON y carga de
  medios; una conexión colgada no deja el worker indefinidamente en espera.
  Los errores de red del sender ocultan el token del bot antes de registrarlos.
- Logistica Por Cuentas muestra un aviso en la previsualizacion si incluye
  salidas validadas de tandas Forge parciales; tandas con inventario invalido
  o estados no distribuibles siguen bloqueadas.
- Los carriles de video aplican el mismo gate de inventario por cuenta antes
  de calendarizar: solo aceptan finales presentes y validados, con warning y
  conteo de pendientes para tandas `incomplete`. La ruta aceptada debe ser un
  archivo directo de la raiz de identidad que aparece en el inventario Forge;
  un homonimo dentro de una subcarpeta no sustituye a la copia validada.
- Telegram omite en ejecuciones posteriores las filas ya confirmadas como
  `sent_telegram` o `published`, sin ocultarlas del calendario ni del conteo
  historico de publicaciones.
- Para carriles nuevos, el hash de publicado incluye identidad y destino
  tambien para videos: bytes iguales en cuentas/canales distintos no marcan
  globalmente las otras publicaciones. Reels historicos conservan el hash
  global anterior para no romper su compatibilidad con Airtable. La
  sincronizacion manual desde Calendario usa el mismo contrato.
- En el topic mode predeterminado, todas las publicaciones de carriles nuevos
  de una identidad (incluido Instagram Trial) comparten su topic cronologico;
  las tandas Trial legacy conservan su topic separado.
- Las publicaciones de Story llevan un boton para copiar su URL individual
  cuando no supera el limite documentado por Telegram; el enlace completo
  tambien se conserva visible en los metadatos enviados al topic.
- Los carriles rechazan finales que ya esten en el manifiesto o repetidos
  dentro de la tanda candidata, aunque la nueva fecha/destino no choque.
- Verificacion reciente de Photo Forge: `py_compile`, smoke de imports y
  ejecucion funcional temporal con seis salidas para dos identidades, hashes
  distintos, original intacto, preview igual a variante 1, transparencia,
  lectura legacy e idempotencia. No se ejecutaron tests automatizados. El
  formulario modificado aún no tuvo revisión visual; no hubo envío real a
  Telegram. `docs/GUIA_LOGISTICA_MULTICANAL.md` documenta el flujo de usuario
  y las limitaciones actuales.
- Pendiente antes de release: ejecutar las validaciones del plan, revisar el
  flujo en la GUI instalada y hacer un envio controlado a Telegram.
- Actualizador: como la release agrega modulos locales, publicar primero una
  release bootstrap solo con `updater.py` y `version.json`; publicar el codigo
  de la funcion en una version posterior para que instalaciones antiguas
  acepten `publication_schedule.py`, `por_cuentas_lanes.py` y `photo_forge.py`.
  El checkout compartido actualmente anuncia `1.0.48`; por tanto, al llegar
  a release, usar `1.0.49` para el bootstrap y `1.0.50` para la funcionalidad.
  No rebajar ni reemplazar los datos locales del launcher durante este puente.
