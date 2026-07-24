# Forge sin distribución automática

## Objetivo

Simplificar la pantalla Forge porque la distribución ya se realiza desde la
pestaña Logística.

## Alcance

- Ocultar/eliminar de Forge el campo `Categoría destino`.
- Ocultar/eliminar de Forge el check `Distribuir automáticamente al procesar`.
- Eliminar de `forge_process` la validación, confirmación y ejecución de la
  distribución automática.
- Mantener la generación de variantes, el registro de la tanda y todos los
  controles restantes de Forge sin cambios.
- Mantener sin cambios la categoría y la distribución de la pestaña Logística.

## Comportamiento resultante

Al procesar Forge, la aplicación solo genera los archivos en la tanda y la
registra en la base de datos. La confirmación ya no muestra categoría ni estado
de distribución. La distribución posterior se inicia desde Logística.

## Verificación

- Compilar `gui_premium_v7.py`.
- Verificar por búsqueda que los controles y la rama de distribución automática
  ya no pertenezcan al flujo Forge.
- Ejecutar la suite de pruebas existente, si está disponible para este checkout.
- Revisar que el diff solo afecte la pantalla y el flujo Forge, además de este
  documento.
