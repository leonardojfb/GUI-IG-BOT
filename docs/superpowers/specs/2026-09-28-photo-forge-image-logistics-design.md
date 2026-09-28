# Photo Forge e Imagenes en Logistica

## Objetivo

Separar completamente la generacion de finales de imagen de su distribucion.
Photo Forge crea tandas neutrales de archivos distintos. La nueva pestaña
`Logistica > Imagenes` asigna esas tandas a categorias de cuentas, construye
publicaciones manuales para Instagram y Facebook, las calendariza junto con los
Reels existentes y las entrega ordenadas a Telegram.

No se automatiza la publicacion en Meta y no se copian archivos a
`CALENDARIO_POSTEO`.

## Limites de responsabilidad

### Photo Forge

Photo Forge solo transforma imagenes y registra su linaje. No conoce cuentas,
categorias, plataformas, destinos, captions, enlaces, fechas, frecuencias ni
horarios.

Su pantalla contiene:

- nombre de tanda;
- carpeta base de salida;
- imagenes fuente;
- perfil de salida;
- intensidad, efectos y espejo horizontal;
- `Finales por foto`.

Se eliminan de esta pantalla:

- `Identidades destino`;
- `Variantes elegidas`;
- comparacion por imagen e identidad;
- cualquier salto automatico que rellene cuentas en Logistica.

### Logistica

Logistica decide que se publica, en que plataforma, para que categoria de
cuentas y cuando. Las pestañas existentes `Por Tandas`, `Por Cuentas` y
`Trials` conservan su estructura y comportamiento. Se elimina de `Por Cuentas`
el bloque generico de carriles y se agrega una cuarta pestaña independiente:
`Imagenes`.

### Calendario y Telegram

El calendario combina publicaciones de video e imagen en una agenda unica.
Telegram consume esa agenda, la ordena por cuenta, fecha y hora local, y la
entrega para publicacion manual.

## Tanda neutral de Photo Forge

Por cada imagen fuente, Photo Forge genera la cantidad solicitada de finales
fisicamente distintos. Por ejemplo, cinco fuentes con diez finales por foto
producen cincuenta archivos.

La salida es una carpeta plana. Los nombres incluyen una identidad logica de
fuente y un indice de copia, sin nombre ni ID de cuenta. El manifiesto
`photo_forge_manifest.json` registra como minimo:

- version de esquema;
- ID y nombre de tanda;
- estado `validated`, `incomplete` o `failed`;
- ruta y SHA-256 de cada fuente;
- receta y perfil de transformacion;
- indice de copia;
- ruta y SHA-256 de cada final;
- dimensiones y formato validados;
- fecha de generacion.

Las tandas validas aparecen automaticamente en `Logistica > Imagenes` mediante
sus manifiestos bajo `imagenes_finales`. Una tanda incompleta puede mostrarse
con su capacidad real, pero no puede calendarizarse si no alcanza la capacidad
del plan completo.

Los manifiestos antiguos ligados a identidades se conservan y pueden mostrarse
como legado. No se renombran, mueven ni eliminan sus archivos.

## Logistica > Imagenes

### Seleccion inicial

La pantalla permite seleccionar:

- tanda Photo Forge;
- categoria de cuentas;
- cuentas cargadas desde esa categoria;
- fecha inicial y zona horaria aplicable.

El inventario muestra una fila por fuente logica, con miniatura, cantidad total,
reservada y disponible. La asignacion utiliza el manifiesto, no nombres de
subcarpetas por cuenta.

### Construccion de publicaciones

El operador selecciona una o varias fuentes logicas y crea bloques de
publicacion:

- Story Instagram;
- Post Instagram;
- Carrusel Instagram;
- Photo Reel Instagram;
- Story Facebook;
- Post de pagina Facebook;
- album de Facebook;
- Marketplace Facebook.

Una fuente puede seleccionarse para un destino individual. Varias fuentes
pueden agruparse como carrusel o album y reordenarse manualmente. Stories,
Posts y Carruseles pueden marcar Instagram, Facebook o ambas plataformas.
Cuando se marcan ambas, se crean publicaciones independientes y se reservan
finales diferentes para cada plataforma. Marketplace solo permite Facebook y
Photo Reel solo permite Instagram; la interfaz no ofrece combinaciones
incompatibles.

Cada archivo final se utiliza una sola vez. Al reservarse para una cuenta,
plataforma y publicacion deja de estar disponible para cualquier otra.

### Campos permanentes y condicionales

Todos los bloques conservan:

- plataforma y destino;
- fecha inicial;
- cantidad diaria;
- regla `cada N dias`;
- horas locales;
- periodo o cantidad total;
- caption o texto principal cuando aplique.

Campos condicionales:

- Story: texto de anuncio y enlace resuelto por identidad;
- Post: caption;
- Carrusel o album: caption y orden de imagenes;
- Marketplace: titulo, precio, condicion y descripcion;
- Photo Reel: caption.

La frecuencia nunca se configura en Photo Forge.

## Capacidad y asignacion

Cada cuenta de la categoria recibe el set completo usando finales distintos.
Para una categoria de diez cuentas:

- una Story basada en una fuente requiere diez finales de esa fuente;
- un Post basado en una fuente requiere diez finales;
- un carrusel de tres fuentes requiere treinta finales;
- el mismo bloque para Instagram y Facebook duplica esa capacidad.

La previsualizacion calcula demanda y disponibilidad por fuente antes de
reservar. Los sobrantes permanecen libres. Si falta capacidad, la operacion se
bloquea y muestra la fuente, la cantidad necesaria, la disponible y el deficit.
No se crea un calendario parcial.

La asignacion debe ser determinista y exhaustiva. No se usa busqueda aleatoria
acotada para reservar finales.

## Agenda compartida

`calendar_manifest.json` sigue siendo la fuente de verdad de Logistica. Las
entradas historicas de un solo archivo siguen siendo validas. El esquema nuevo
agrega de forma compatible una unidad de publicacion con:

- ID estable de publicacion;
- cuenta y categoria;
- plataforma y destino;
- fecha, hora y zona horaria;
- uno o varios elementos multimedia ordenados;
- caption y metadatos condicionales;
- ID de tanda y plan;
- estado manual de la publicacion.

Cada elemento multimedia conserva la ruta absoluta del final en su lugar de
produccion y su nombre de entrega para Telegram. No se copia ni mueve.

Una imagen individual produce una unidad con un elemento. Un carrusel produce
una unidad con varios elementos ordenados. Instagram y Facebook generan
unidades separadas incluso cuando parten del mismo bloque logistico.

La combinacion con Reels se ordena por cuenta, fecha local, hora local y
secuencia estable. Una Story de las 12:00 queda entre Reels de las 10:00 y
13:00. Un choque exacto de cuenta, fecha y hora bloquea la confirmacion; el
sistema no cambia horarios silenciosamente.

La escritura del calendario es atomica. Un error de validacion o escritura no
deja reservas ni entradas parciales.

## Vista de calendario

El calendario muestra una fila por unidad de publicacion con:

- fecha y hora;
- cuenta;
- plataforma y destino;
- miniatura;
- cantidad de elementos;
- caption resumido;
- estado.

El detalle permite recorrer las imagenes de un carrusel en su orden real y ver
enlaces de Story o metadatos de Marketplace.

## Telegram

El modo predeterminado sigue siendo un topic por identidad y dia. El operador
puede elegir topics separados por tipo.

Telegram entrega toda la agenda en orden cronologico:

- imagen individual mediante envio de foto;
- Reel mediante el flujo de video existente;
- carrusel o album mediante un grupo multimedia ordenado;
- despues del album, un unico mensaje de control con el resumen y el boton
  `Marcar como publicado`.

El caption del album se coloca en su primer elemento. El boton de control marca
la unidad completa y todos sus elementos, no cada imagen por separado. Stories
incluyen el enlace propio resuelto para la identidad correspondiente.

No se envia contenido real a Telegram durante pruebas automatizadas.

## Compatibilidad de actualizacion

La actualizacion conserva sin sobrescribir:

- `organizador.db`;
- `calendar_manifest.json`;
- configuraciones y credenciales;
- historiales locales;
- tandas, videos e imagenes existentes;
- manifiestos Forge y Photo Forge.

Los cambios de esquema son aditivos. Lectores historicos de entradas simples no
dependen de los nuevos campos multimedia. La instalacion y el actualizador no
incluyen datos runtime del desarrollador.

## Manejo de errores

- Tanda sin manifiesto valido: no seleccionable para ejecutar.
- Archivo faltante, corrupto o con hash distinto: se bloquea la unidad afectada.
- Capacidad insuficiente: no se reserva ni calendariza nada.
- Choque exacto de horario: se muestra en previsualizacion y bloquea confirmacion.
- Cambio entre preview y confirmacion: se recalcula bajo bloqueo y se exige nueva
  previsualizacion.
- Error al escribir: el manifiesto anterior permanece intacto.
- Error de Telegram: la publicacion conserva estado pendiente o fallido y puede
  reintentarse sin duplicar las confirmadas.

## Validacion

La implementacion no se considera terminada hasta cubrir:

1. Photo Forge neutral sin identidades y con carpeta plana.
2. Aparicion automatica de la tanda en `Logistica > Imagenes`.
3. Capacidad exacta para multiples cuentas y plataformas.
4. Un final fisico unico por cuenta, plataforma y publicacion.
5. Stories, Posts, Marketplace, Photo Reel y carruseles.
6. Agrupacion y orden manual de carruseles.
7. IG y FB reservando archivos distintos.
8. Intercalado con Reels historicos y nuevos.
9. Choques exactos bloqueados sin mutaciones parciales.
10. Calendario con miniaturas y detalle multimedia.
11. Telegram individual y album mediante un emisor falso.
12. Estado publicado aplicado a una unidad completa.
13. Upgrade desde una instalacion anterior conservando DB, calendario y medios.
14. Ausencia de nuevas copias en `CALENDARIO_POSTEO`.
15. Recorrido manual de GUI con una tanda real de prueba.

## Fuera de alcance

- Publicacion automatica mediante APIs de Meta.
- Docker.
- Edicion de imagenes dentro de Logistica.
- Reutilizacion de un mismo archivo final.
- Reescritura de las tres logisticas existentes.
