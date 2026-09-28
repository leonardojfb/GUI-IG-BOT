# Photo Forge y Logistica > Imagenes

## Ejemplo: cinco dias, diez identidades, Instagram y Facebook

Objetivo por identidad: un Reel a las 10:00 cada dia, una Story a las 12:00
cada dia y un carrusel de tres imagenes a las 15:00 los dias 1 y 4.

1. Calendariza los cinco Reels por identidad en `Logistica > Por Cuentas`
   con la tanda de video existente. No cambies el flujo de video para preparar
   las fotos.
2. En `Photo Forge`, selecciona una foto para Stories, la receta deseada y
   `Finales por foto = 100`. Calcula: 5 dias x 10 identidades x 2 plataformas.
   Genera una tanda llamada, por ejemplo, `STORIES_5D`. Los cien finales
   quedan en una carpeta plana. Todavia no pertenecen a ninguna cuenta.
3. En `Logistica > Imagenes`, actualiza el inventario, selecciona
   `STORIES_5D` y la categoria de diez cuentas. Agrega la fuente al orden de
   publicacion, elige `instagram_story` y marca `Instagram y Facebook`.
   Configura fecha inicial, `Días de período = 5`, `Cada N días = 1`,
   `Cantidad diaria = 1`, `Horas = 12:00`, zona horaria y texto Story.
   Cada identidad toma su propio enlace configurado en `Cuentas`.
   Añade el bloque, previsualiza las 100 publicaciones y confirma.
4. En `Photo Forge`, selecciona tres fotos para carrusel y genera otra tanda,
   `CAROUSELES_5D`, con `Finales por foto = 40`. Cada una de las tres fuentes
   necesita 2 publicaciones x 10 identidades x 2 plataformas = 40 finales.
5. En `Logistica > Imagenes`, selecciona `CAROUSELES_5D`, la misma categoria
   y agrega las tres fuentes en el orden del carrusel. Usa las flechas para
   corregir ese orden. Elige `instagram_post` y marca ambas plataformas.
   Configura `Días de período = 5`, `Cada N días = 3`, `Cantidad diaria = 1`,
   `Horas = 15:00` y el caption. Añade el bloque, previsualiza y confirma.

La previsualizacion muestra la demanda exacta por fuente. Si una tanda no
tiene capacidad o hay choque exacto de cuenta, plataforma, fecha y hora, no
se escribe ninguna publicacion parcial. Un final usado deja de estar libre.

## Resultado diario

Para cada identidad, el calendario y su topic predeterminado de Telegram
quedan ordenados por fecha y hora local:

| Dia | 10:00 | 12:00 | 15:00 |
| --- | --- | --- | --- |
| 1 | Reel | Story IG + Story FB | Carrusel IG + album FB |
| 2 | Reel | Story IG + Story FB | - |
| 3 | Reel | Story IG + Story FB | - |
| 4 | Reel | Story IG + Story FB | Carrusel IG + album FB |
| 5 | Reel | Story IG + Story FB | - |

Instagram y Facebook son unidades separadas y usan finales fisicos distintos.
Un carrusel se entrega como grupo multimedia en su orden configurado, seguido
por un solo mensaje con el boton `Publicado`. La publicacion en IG/FB sigue
siendo manual. El calendario guarda rutas absolutas a los finales; no crea
copias en `CALENDARIO_POSTEO`.

La opcion `Telegram > Topics` permite mantener todo en un topic por identidad
ordenado por dia (predeterminado), o separar topics por tipo de publicacion.
Los campos de zona horaria, horarios y frecuencia son configurables en cada
bloque; `Guardar defaults` conserva los valores iniciales para la proxima vez.
