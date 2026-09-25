# Forge: fecha actual y piso de dispositivo/iOS

## Objetivo

Hacer que cada salida generada por Forge registre la fecha y hora reales del momento de procesamiento, y limitar las fingerprints usadas por Forge a modelos iPhone 16 o superiores con iOS 26 o superior.

## Alcance

- Aplicar la fecha dinámica a los caminos Legacy MP4 e iPhone MOV (SDR/HLG).
- Escribir metadata QuickTime compatible en las salidas:
  - `creation_time` en UTC ISO-8601.
  - `com.apple.quicktime.creationdate` en hora local con offset.
- Filtrar el pool de combinaciones a `iPhone 16` o superior y versiones iOS `>= 26.0`.
- Rechazar en la capa de validación combinaciones antiguas aunque provengan de metadata reutilizada o de una tanda pendiente.
- Mantener las validaciones existentes de color, codec, audio, contenedor y decodificación.

El catálogo actual no se ampliará con modelos que todavía no existan en el pool; por tanto, tras aplicar el piso quedarán disponibles los modelos iPhone 16 actualmente declarados.

## Diseño

### Fuente de fecha

La fecha se calculará durante la ejecución de cada salida, dentro del camino que construye el comando FFmpeg. No se copiará la fecha del archivo fuente y no se fijará durante el preview. Así, dos copias procesadas en momentos distintos podrán tener timestamps distintos y cada salida reflejará su momento real de Forge.

Se usará un helper compartido para producir los dos tags QuickTime a partir de un instante consciente de zona horaria. El instante será UTC; la representación local conservará el offset del sistema.

### Restricción de fingerprint

El pool declarará límites reutilizables:

- generación mínima de iPhone: `16`;
- versión mínima de iOS: `26.0`.

El generador filtrará modelos y versiones antes de construir combinaciones. La validación de metadata comprobará el mismo contrato para evitar que un objeto antiguo evite el filtro del generador. El parser de modelo extraerá la generación numérica del nombre `iPhone N...`; el parser de iOS comparará componentes numéricos, por lo que `26.0.1` será válido y `18.7.9` será rechazado.

### Integración

- `metadata_pool.py` será responsable del helper de fecha, del contrato de límites y de aplicarlos al camino Legacy.
- `forge_iphone_profile.py` usará el contrato al validar metadata y aplicará los tags dinámicos al render iPhone.
- Los tests unitarios cubrirán generador, validador y tags.
- Los tests de integración existentes de render verificarán que las salidas reales mantienen los contratos actuales y contienen timestamps válidos.

## Comportamiento ante errores

- Una metadata con modelo menor que iPhone 16 o iOS menor que 26 produce un error claro antes de invocar FFmpeg.
- Una salida que no contenga ambos timestamps requeridos será inválida durante `validate_probe`.
- No se cambiará la política de reintentos, no se sobrescribirán salidas existentes y no se tocará la metadata de archivos ya publicados.

## Criterios de aceptación

1. `generate_unique_metadata` nunca devuelve iPhone 12–15 ni iOS 18 o anteriores.
2. iPhone 16 con iOS 26.x se acepta.
3. Una combinación antigua es rechazada por la validación aunque se entregue directamente.
4. Una salida Legacy y una salida MOV contienen `creation_time` y `com.apple.quicktime.creationdate` válidos y cercanos al instante de render.
5. Las pruebas actuales de Forge siguen pasando.
6. La comprobación real con FFmpeg continúa siendo exitosa para video y audio.

