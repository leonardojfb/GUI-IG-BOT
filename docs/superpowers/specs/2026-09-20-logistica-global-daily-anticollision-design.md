# Logística Por Cuentas: anti-colisión global diaria

## Objetivo

Evitar que dos cuentas reciban el mismo origen lógico de video durante el mismo día en `Logística > Por Cuentas`, incluso cuando existan varias copias físicas del origen con sufijos `__cNN`.

## Diseño aprobado

`source_key_from_filename()` seguirá siendo la identidad lógica del origen. La planificación mantendrá dos reglas duras:

1. Una cuenta no puede recibir dos veces el mismo origen lógico en el mismo día.
2. Dos cuentas distintas no pueden recibir el mismo origen lógico en el mismo día.

La segunda regla convierte el conjunto diario `day_vid_ids_used` de una penalización de scoring en un filtro de candidatos. `assigned` seguirá evitando reutilizar exactamente el mismo archivo físico dentro de la ejecución.

Si el número de orígenes lógicos disponibles no alcanza para llenar los slots de un día, la ejecución debe fallar con el error existente de falta de candidatos, sin rellenar mediante otra copia física del mismo origen.

No se cambia la rotación entre días ni el flujo de manifest/captions; el alcance es exclusivamente la anti-colisión diaria de Por Cuentas.

## Validación

Se agrega una regresión E2E con dos cuentas, un día y dos archivos físicos que comparten el mismo origen lógico. La prueba debe fallar antes del cambio porque el plan actual asigna ambas copias, y pasar después porque la ejecución informa que no hay candidatos suficientes.
