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
