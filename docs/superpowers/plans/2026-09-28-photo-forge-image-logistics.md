# Plan de implementacion: Photo Forge neutral y Logistica de Imagenes

Especificacion: `docs/superpowers/specs/2026-09-28-photo-forge-image-logistics-design.md`.
Rama: `feature/por-cuentas-multicanal`. No publicar release ni enviar contenido real a Telegram en pruebas.

## Etapa 1: contrato neutral de Photo Forge

Archivos: `photo_forge.py`, `tests/test_photo_forge.py` (o prueba nueva dedicada).

1. Agregar pruebas para N fuentes x M finales, nombres planos sin cuenta, IDs logicos estables, hashes y dimensiones verificados, y salida unica por indice.
2. Introducir una API neutral de planificacion que no acepte cuentas. Conservar el lector y generador antiguo solo para compatibilidad de manifiestos existentes; la GUI nueva no los invocara.
3. Escribir manifiesto versionado con estado, identificador de tanda, fuentes, receta y finales. Validar cada archivo y escribir atomica y exclusivamente dentro de la tanda.
4. Descubrir tandas bajo `imagenes_finales` a partir de manifiestos, distinguiendo neutral/legado/incompleta y reportando capacidad fisica real.
5. Ejecutar pruebas focalizadas; verificar que un manifiesto viejo sigue leyendose sin cambiar sus archivos.

## Etapa 2: pantalla Photo Forge

Archivos: `gui_premium_v7.py`, pruebas de GUI Photo Forge.

1. Sustituir identidades, variantes elegidas y comparacion por identidad por `Finales por foto`.
2. Conectar previsualizacion y generacion a la API neutral. Mostrar demanda total y destino plano antes de ejecutar.
3. Mantener perfil, intensidad, rangos de efectos, espejo y fuentes. La salida exitosa debe aparecer en el inventario de Logistica sin reiniciar.
4. Probar previsualizacion, generacion y error sin mutacion de una tanda existente.

## Etapa 3: planificador puro de imagenes

Archivos: nuevo modulo de logistica de imagenes, `calendar_manifest.py`, pruebas del planificador.

1. Modelar bloque con fuentes ordenadas, destino compatible, plataformas, categoria/cuentas, fecha, zona horaria, cantidad diaria, cada N dias, horas y total/periodo.
2. Validar campos condicionales: enlace individual para Story, caption para Post/album, titulo/precio/condicion/descripcion para Marketplace.
3. Expandir deterministamente cada bloque para cada cuenta y plataforma; cada una recibe el set completo. Calcular capacidad por fuente antes de elegir archivos.
4. Reservar solo finales validados y aun no presentes en calendario. Prohibir duplicados, hashes desviados, faltantes, combinaciones incompatibles y capacidad insuficiente.
5. Construir publicaciones con `media_items` ordenados y `source_path` compatible para lectores historicos; una publicacion por cuenta/plataforma/ocurrencia.
6. Previsualizar colisiones exactas contra agenda existente. Confirmar bajo bloqueo con revalidacion y escritura atomica, sin reservas ni entradas parciales en error.
7. Probar diez cuentas, IG+FB, carrusel, sobrantes, deficit, conflicto de hora, cambio entre preview/confirmacion y preservacion de entradas antiguas.

## Etapa 4: Logistica > Imagenes

Archivos: `gui_premium_v7.py`, pruebas de widgets y flujo.

1. Restaurar `Por Tandas`, `Por Cuentas` y `Trials` sin el bloque generico de carriles.
2. Agregar pestaña `Imagenes` con selector de tanda, categoria, cuentas, zona horaria, inventario por fuente y miniaturas.
3. Permitir crear varios bloques, seleccionar/reordenar fuentes de carrusel, elegir plataformas compatibles, completar campos condicionales y frecuencia por bloque.
4. Mostrar demanda/capacidad, agenda intercalada y conflictos; confirmar solo una previsualizacion vigente.
5. Recorrer manualmente en GUI una tanda de prueba, sin alterar datos runtime del usuario.

## Etapa 5: calendario compartido

Archivos: `calendar_manifest.py`, `gui_premium_v7.py`, pruebas de calendario.

1. Leer entradas simples existentes y nuevas unidades multimedia sin migracion destructiva.
2. Listar por cuenta, fecha/hora local y secuencia estable, intercalando Reels e imagenes.
3. Mostrar miniatura, cantidad de elementos, caption resumido y estado; detalle con orden, enlace de Story y datos Marketplace.
4. Probar Story 12:00 entre Reels 10:00 y 13:00, incluyendo entrada historica.

## Etapa 6: Telegram manual

Archivos: `organizadortg.py`, callback/estado correspondiente, pruebas con emisor falso.

1. Reutilizar topics por identidad/dia y exponer opcion de topics por tipo.
2. Enviar imagen simple como foto, video por flujo actual y carrusel de 2-10 elementos con `sendMediaGroup` ordenado.
3. Poner caption en el primer elemento y mandar un solo mensaje de control por unidad con `Marcar como publicado`.
4. Resolver enlace de Story por identidad. Reintentos no deben duplicar unidades confirmadas.
5. Probar fallo parcial, reintento, orden mixto y marcado de la publicacion completa, sin red real.

## Etapa 7: compatibilidad y cierre

Archivos: `updater.py`, `build_release.ps1`, documentacion y pruebas de upgrade.

1. Incluir modulos nuevos en allowlists de instalacion; excluir DB, calendario, credenciales, tandas y medios runtime.
2. Probar upgrade simulado con manifiesto antiguo, calendario existente y tandas intactas.
3. Ejecutar pruebas focalizadas y suite amplia, `compileall`, recorrido GUI y emisor Telegram falso. Registrar limites ambientales de FFmpeg sin presentarlos como exito.
4. Dejar commits por etapa validada. Publicar release solo despues de prueba de instalacion/actualizacion y autorizacion explicita.

## Invariantes de cada etapa

- Nunca copiar a `CALENDARIO_POSTEO` ni publicar por API Meta.
- Nunca usar un mismo final fisico dos veces ni crear calendarios parciales.
- Nunca sobrescribir datos runtime existentes ni alterar las tres logisticas heredadas.
- Cada etapa debe dejar pruebas focalizadas verdes y la GUI anterior operativa antes de avanzar.
