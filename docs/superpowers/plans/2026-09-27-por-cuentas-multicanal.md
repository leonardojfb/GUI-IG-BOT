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
  los campos vacíos conservan el preset. La GUI permite elegir un subconjunto
  de variantes por índices/rangos y previsualiza la primera variante elegida.
  La comparación visual V1-Vn permite seleccionar variantes por pareja
  imagen/identidad; las parejas sin selección propia heredan el ajuste global.
  La receta de cada ejecución registra índices efectivos por identidad, fuente
  y hash, y el generador conserva carpetas físicas separadas por identidad.
  La Biblioteca registra imágenes/videos por hash y ruta, permite elegir
  imágenes en Photo Forge, crear familias/colecciones y asignar roles sin mover
  medios; los finales preservan relaciones de origen por ruta de cuenta. La
  migración es aditiva. La integración de Forge de video, captions y linaje de
  calendario/envío en Vault sigue pendiente.
  Las tandas conservan recetas por ejecución y un resumen agregado al añadir
  más perfiles/subconjuntos sin borrar las salidas anteriores; el historial
  separa rutas solicitadas, nuevas y reutilizadas. Los totales que manifiestos
  antiguos no registraron, y el perfil/índice que falte en entradas legacy,
  se muestran como desconocidos.
  Sigue pendiente perspectiva, perfiles
  de metadata configurables, captions, cola de jobs persistente,
  selección posterior por salida y repetición
  de receta como objeto separado de una ejecución. No presentar Photo Forge
  como implementación completa del prototipo mientras esos puntos sigan pendientes.
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
- Regresion detectada y corregida al validar el distribuidor legacy: quedaba
  un calculo muerto de destino bajo `CALENDARIO_POSTEO` que referenciaba
  `cal_root` sin definir, aunque la escritura ya era solo al manifiesto. Se
  eliminaron esas rutas no utilizadas; Por Cuentas legacy vuelve a calendarizar
  sin copiar archivos, conservando sus nombres de entrega. Verificacion:
  `tests/test_calendar_manifest.py`, `tests/test_por_cuentas_lanes.py` y
  `tests/test_logistica_por_cuentas_e2e.py`: 15 passed. La prueba de UI crea
  una DB/manifiesto temporal y comprueba orden Reel 10:00, Story 12:00 y
  Marketplace 13:00, filtro de identidad, enlace de Story y preview de imagen.
  Compilacion de modulos y `git diff --check` correctos.
- Telegram fallaba al entregar Reels legacy sin fecha: el escaner exponia el
  dia como `Dia_1`, pero el resolvedor esperaba un entero. Ahora acepta tanto
  el dia numerico del manifiesto como el formato de carpeta `Dia_N`. La prueba
  unitaria cubre ambos valores. Se actualizaron stubs Telegram obsoletos para
  timeout, topics por tipo, Airtable fail-closed y metadata de slot; el test de
  escaneo ahora exige conservar Stories/Posts/Marketplace para su entrega
  manual. Un E2E temporal crea una cuenta SQLite y un manifiesto con Reel,
  Story y Marketplace, simula solo el borde Telegram y verifica el orden
  10:00/12:00/13:00, el enlace Story, metadatos de Marketplace y estado
  `sent_telegram`, sin red ni publicación real. Resultado conjunto de
  calendario, Photo Forge, Por Cuentas y Telegram: 71 passed, 1 skipped (un
  caso GUI no obtuvo display); `py_compile` y `git diff --check` correctos.
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
- Photo Forge tiene ahora una prueba de integracion en la GUI con DB, medios y
  manifiestos temporales: selecciona dos identidades, genera finales distintos
  por cuenta del perfil Post 4:5, verifica hashes y receta, conserva intacta la
  fuente, registra cuatro relaciones de linaje y abre Logistica con la carpeta
  y cuentas correctas. Luego calendariza un final propio para cada cuenta en
  Instagram Post y confirma que no crea `CALENDARIO_POSTEO`. Se conserva además
  el smoke anterior de seis salidas, preview, transparencia, compatibilidad e
  idempotencia. `docs/GUIA_LOGISTICA_MULTICANAL.md` documenta el uso; siguen
  pendientes perspectiva y la receta como objeto persistente independiente de
  cada ejecucion.
- Pendiente antes de release: validar el launcher realmente instalado y hacer
  un envio controlado a Telegram. El upgrade en staging y la GUI empaquetada
  estan verificados, pero no sustituyen esas dos pruebas; tampoco se ha
  publicado la release.
- Actualizador: como la release agrega modulos locales, publicar primero una
  release bootstrap solo con `updater.py` y `version.json`; publicar el codigo
  de la funcion en una version posterior para que instalaciones antiguas
  acepten `publication_schedule.py`, `por_cuentas_lanes.py` y `photo_forge.py`.
  El checkout compartido actualmente anuncia `1.0.48`; por tanto, al llegar
  a release, usar `1.0.49` para el bootstrap y `1.0.50` para la funcionalidad.
  No rebajar ni reemplazar los datos locales del launcher durante este puente.
  El updater ahora rechaza manifiestos que pidan archivos no permitidos o que
  falten en el ZIP, evitando subir `version.json` con una instalación parcial;
  `console_encoding.py` también está en su allowlist porque forma parte del
  paquete de release. Smoke temporal: el updater 1.0.48 omitía módulos nuevos
  y subía versión; tras el bootstrap, el updater actualizado instaló la fase
  funcional completa y preservó `organizador.db`.
  `build_release.ps1 -BootstrapUpdater` tampoco necesita localizar ni copiar
  FFmpeg: el bootstrap solo empaqueta `updater.py` y `version.json`.
  Staging validado sin publicar: bootstrap `1.0.49` con exactamente esos dos
  archivos; paquete funcional `1.0.50` con 37 archivos, lista del manifiesto y
  SHA-256 coincidentes, módulos nuevos presentes y base/manifiestos/media de
  usuario excluidos. Integración temporal: apliqué ambos ZIP en orden sobre
  una instalación `1.0.48` con el updater anterior; la DB centinela se preservó
  y aparecieron los módulos nuevos. Arranqué además la GUI directamente desde
  esa copia actualizada y verifiqué Logística Por Cuentas, Biblioteca y Photo
  Forge, junto con el valor centinela de SQLite. No es una instalación del
  launcher real ni una release publicada.
- Continuación 2026-09-28: la rama aislada estaba basada en `1.0.45`; integré
  los commits de release `1.0.46`-`1.0.48` para conservar el límite Forge iPhone
  17+, los reintentos por hash tras mover las fuentes y la distribución de
  salidas validadas de tandas parciales. Resolví el único conflicto de GUI
  manteniendo la resolución por hash y el aviso legible de tandas parciales.
  La suite combinada de calendario, carriles, publicación manual, Photo Forge,
  Forge iPhone y Telegram pasó: 133 passed, 1 skipped por falta de display;
  allowlist y updater: 15 passed. Compilación y `git diff --check` correctos.
  Actualicé staging desde esta base: bootstrap `1.0.49` (2 archivos) y
  funcional `1.0.50` (37 archivos); SHA-256 funcional
  `e65aa942d4f40e2c5ee7ffeeb79a55ede7e10b7d956ac903a31ffb5d5d0581c5`.
  Los módulos nuevos están incluidos y no hay DB local, manifiesto de
  calendario ni medios en el ZIP. Repetí la integración temporal en una
  instalación sintética: el updater 1.0.48 aplicó el bootstrap, el updater
  resultante aplicó 1.0.50, y DB, manifiesto y medio centinela permanecieron
  byte por byte intactos; los tres módulos nuevos aparecieron instalados.
  No se publicó ni se probó contra el launcher instalado real; el envío real a
  Telegram sigue pendiente y no se ejecutó.
