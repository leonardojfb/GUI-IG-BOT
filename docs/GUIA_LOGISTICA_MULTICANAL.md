# Guia de Logistica Multicanal

Esta guia describe el flujo manual de Instagram y Facebook en la GUI Legacy.
La aplicacion organiza archivos y los entrega a Telegram; no publica en Meta.
Los finales se mantienen en su carpeta de origen y no se copian a
`CALENDARIO_POSTEO`.

## 1. Preparar identidades

1. Abre **Cuentas** y confirma que cada identidad tenga asignada su VA y zona
   horaria. La zona de la VA determina la hora local del calendario.
2. Para Stories, guarda un **Dominio base Story** o configura **Link Story**
   por identidad. Un enlace propio reemplaza el dominio base solo para esa
   identidad.
3. Los enlaces se guardan localmente. No se sincronizan con Airtable.

## 2. Preparar finales

La **Biblioteca** aparece bajo Contenido en la navegación. Importa imágenes o
videos para indexarlos por SHA-256 y encontrarlos por nombre, hash o ruta. La
importación no mueve ni copia los archivos. Los resultados de Photo Forge se
añaden como derivados con relaciones a su origen; conserva un registro propio
por ruta/cuenta aunque dos finales tengan los mismos bytes.

Para video, usa los finales validados de Forge en `videos_finales/<tanda>`.
Para fotos, abre **Photo Forge** y agrega imágenes desde disco o usa **Desde
Biblioteca** para elegir imágenes previamente registradas:

1. Define nombre de tanda y carpeta de salida.
2. Agrega las imágenes en el orden deseado; el primer archivo se previsualiza.
   **Comparar variantes** permite elegir por imagen e identidad. Solo una pareja
   editada queda personalizada; las demás heredan la selección global.
3. Elige un **Placement**: Original, Story 9:16, Post 4:5, Post cuadrado,
   Portada 16:9 o Photo Reel (imagen). Photo Reel sigue siendo imagen y no se
   convierte a video.
4. Elige cuántas variantes generar por imagen (1 a 20), opcionalmente limita
   la generación con una lista como `1,3-5`, y selecciona la intensidad
   **Sutil**, **Estándar** o **Fuerte**. El preview usa la primera variante
   elegida. La receta aplica parámetros
   deterministas de encuadre, escala de salida, luz, contraste, color, gamma,
   nitidez, rotación y grano; los formatos con pérdida usan calidad registrada
   en la receta.
5. **Ajustar efectos** permite definir mínimos y máximos independientes para
   luminosidad, contraste, color, nitidez, gamma, rotación, encuadre, grano y
   calidad JPEG/WebP. Dejar ambos campos vacíos conserva el rango del preset;
   los límites se validan antes de renderizar. Preview y generación usan los
   mismos rangos, guardados en la receta de cada resultado.
6. **Espejo horizontal** es opcional. El preview muestra el placement y la
   primera variante elegida; vuelve a pulsar **Previsualizar** después de
   cambiar el número/selección de variantes o sus rangos.
7. Selecciona las identidades destino y confirma **Generar finales por cuenta**.
   Cada variante se genera físicamente bajo su identidad; las fotos originales
   no se modifican ni se copian al calendario.
8. La tanda guarda perfil, intensidad, parámetros efectivos, procedencia y
   SHA-256 de cada resultado en `photo_forge_manifest.json`. Para los carriles
   de imagen, Logística valida esos hashes y mantiene el orden del manifiesto.
   El carril **Instagram Photo Reel** sólo admite el perfil Photo Reel de este
   manifiesto; los carriles Reel Normal/Trial y Facebook Reel aceptan sólo
   videos validados por Forge.
   Si agregas variantes con otra selección o perfil a la misma tanda, el
   manifiesto retiene cada ejecución (`recipe_runs`) y un resumen de
   todos los finales; `recipe` indica solo la última ejecución. Cada registro
   distingue rutas solicitadas, creadas en esa ejecución y reutilizadas.

Photo Forge abre **Logistica** con la carpeta de salida y las identidades
seleccionadas. Revisa esa seleccion antes de calendarizar.

Las imágenes transformadas eliminan EXIF y conservan el perfil ICC cuando es
compatible con el modo de color de salida; una salida Original sin
transformaciones conserva exactamente los bytes fuente. Photo Forge acepta
imágenes fijas JPG, PNG, WebP y TIFF; no procesa GIF ni imágenes animadas.

## 3. Crear un carril

En **Logistica > Por Cuentas > Agregar carril al calendario**:

- **Destino**: Instagram Reel/Photo Reel/Trial/Story/Post o Facebook
  Story/Post/Reel/Marketplace. Instagram Photo Reel requiere imágenes Photo
  Forge del perfil Photo Reel; no es una conversión ni un Reel de video.
- **Carpeta de finales por cuenta**: carpeta que contiene una subcarpeta por
  identidad. Photo Forge completa este campo al terminar.
- **Perfil Photo Forge**: por defecto se resuelve según el destino (Story 9:16,
  Post 4:5, Marketplace cuadrado o Photo Reel imagen); puedes elegir otro perfil
  explícitamente. Las tandas históricas sin perfil se consideran Original.
- **Fecha inicial**, **Dias**, **cada N dias** y **Horas**: generan los turnos.
  Usa horas distintas para varias publicaciones del mismo dia.
- **Caption / aviso de Story**: texto comun del carril. En Story tambien es el
  texto del anuncio asociado al enlace individual de cada identidad.
- **Marketplace**: completa titulo y precio; puedes añadir condicion y
  descripcion como metadatos para consultar al publicar manualmente.

Ejemplos para una ventana de 7 dias:

- 3 Reels diarios: destino Reel, dias `7`, cada `1`, horas `09:00,13:00,19:00`;
  hacen falta 21 finales por identidad.
- 1 o 2 Stories diarias: una hora o dos horas separadas por coma. Cada
  identidad debe tener su enlace configurado.
- 1 Post cada 3 dias: dias `7`, cada `3`, una hora; se crean turnos en los dias
  1, 4 y 7, por lo que hacen falta 3 finales por identidad.

Pulsa **Previsualizar carril**. La vista incluye las entradas existentes de
esas identidades dentro del rango y marca los turnos nuevos. Si una identidad
ya tiene una publicacion exactamente a esa hora, no se desplaza nada: corrige
la hora y vuelve a previsualizar. **Agregar al calendario** pide confirmacion
y guarda las rutas; no copia ni mueve archivos.

Guarda **defaults** si quieres conservar dias, intervalo y horas para futuros
carriles. Revisa el resultado en **Calendario**, donde puedes filtrar y abrir
los detalles/preview de cada entrada.

## 4. Entregar a Telegram

1. Confirma que las identidades tengan configurado su grupo/chat de Telegram.
2. En **Telegram**, deja **Topics** en **Por identidad y fecha** para reunir
   Reels, Stories, Posts y Marketplace de cada identidad en un topic
   cronologico. El modo **Separados por tipo** crea topics distintos por
   destino.
3. Selecciona las cuentas y define **Fecha Inicio**. Pulsa **INICIAR** para
   entregar las publicaciones pendientes en orden de fecha y hora local.
4. El mensaje de Telegram incluye destino, hora, caption y metadatos. En
   Stories incluye el enlace; usa el boton para copiar caption o enlace cuando
   aparezca.
5. Publica manualmente en Instagram/Facebook y luego pulsa **Publicado** en
   Telegram. La entrega a Telegram y la publicacion real son estados distintos.

El modo **Envío express** puede omitir el mensaje de contexto de publicaciones
legacy; los carriles multicanal siempre conservan ese mensaje para no perder
fecha, destino ni datos de Marketplace.

No uses **Borrar calendarizaciones** para reordenar: elimina las entradas de
las cuentas seleccionadas. Una entrada ya enviada a Telegram no se vuelve a
enviar en la siguiente ejecucion normal.

## Limites actuales

- No hay OAuth, adaptadores de publicacion ni llamadas de publicacion a Meta.
- Telegram organiza y entrega; la hora es una indicacion para publicacion
  manual, no un programador de Meta.
- Los metadatos de Marketplace son una ayuda para completar la publicacion en
  Meta; no crean el anuncio.
- Photo Forge ofrece placements y presets de intensidad con parámetros
  deterministas; todavía no expone controles manuales independientes para cada
  efecto ni deformación de perspectiva, y aún no está conectado a una cola de
  producción persistente/Vault de recetas.
- Photo Reel es un destino manual de Instagram: Telegram entrega la imagen y
  la VA la publica desde la app de Instagram. No hay publicación automática.
