# Captions individuales en Logística por Cuentas

## Objetivo

Agregar un switch opcional `Captions individuales` en Logística > Por Cuentas.
Al activarlo, la tanda seleccionada se agrupa por video fuente `__cNN`, muestra
un preview junto a cada fuente y permite guardar un caption literal por fuente.

## Comportamiento

- Apagado: el flujo actual de caption por tanda se conserva sin cambio.
- Encendido: cada fuente tiene preview y editor de caption.
- Todas las copias de la misma fuente usan el mismo caption literal, sin
  rotación ni shuffle de hashtags.
- Los captions normales individuales se guardan separados de los captions
  Trial; Trials no se modifica.
- La calendarización conserva el nombre de tanda y la resolución Telegram
  selecciona el mapa individual solo cuando la tanda fue marcada con captions
  individuales.

## Pruebas

- Switch visible en Por Cuentas.
- Agrupado fuente/copia y persistencia normal independiente.
- Dos copias reciben el mismo caption exacto.
- Con el switch apagado, caption normal por tanda mantiene su comportamiento.

