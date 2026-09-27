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

Para video, usa los finales validados de Forge en `videos_finales/<tanda>`.
Para fotos, abre **Photo Forge**:

1. Define nombre de tanda y carpeta de salida.
2. Agrega las imágenes. Logística asigna los finales a los turnos por nombre
   de archivo, no por el orden de selección; usa nombres con prefijos como
   `01_`, `02_` si necesitas un orden concreto.
3. Selecciona las identidades destino. Cada una recibe su propio archivo final.
4. Deja **Espejo horizontal** apagado para conservar exactamente los bytes; si
   lo activas, se crea una variante reflejada y el original no cambia.
5. Revisa la previsualizacion y confirma **Generar finales por cuenta**.

Photo Forge abre **Logistica** con la carpeta de salida y las identidades
seleccionadas. Revisa esa seleccion antes de calendarizar.

## 3. Crear un carril

En **Logistica > Por Cuentas > Agregar carril al calendario**:

- **Destino**: Instagram Reel/Trial/Story/Post o Facebook Story/Post/Reel/
  Marketplace.
- **Carpeta de finales por cuenta**: carpeta que contiene una subcarpeta por
  identidad. Photo Forge completa este campo al terminar.
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

No uses **Borrar calendarizaciones** para reordenar: elimina las entradas de
las cuentas seleccionadas. Una entrada ya enviada a Telegram no se vuelve a
enviar en la siguiente ejecucion normal.

## Limites actuales

- No hay OAuth, adaptadores de publicacion ni llamadas de publicacion a Meta.
- Telegram organiza y entrega; la hora es una indicacion para publicacion
  manual, no un programador de Meta.
- Los metadatos de Marketplace son una ayuda para completar la publicacion en
  Meta; no crean el anuncio.
