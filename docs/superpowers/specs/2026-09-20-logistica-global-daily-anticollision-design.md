# Logística Por Cuentas: anti-colisión global diaria

## Objetivo

Evitar que una cuenta reciba el mismo origen lógico de video dos veces durante el mismo día en `Logística > Por Cuentas`, permitiendo que otras cuentas reciban sus propias copias físicas del mismo set de orígenes.

## Diseño aprobado

`source_key_from_filename()` seguirá siendo la identidad lógica del origen. La planificación mantendrá una regla dura y una preferencia:

1. Una cuenta no puede recibir dos veces el mismo origen lógico en el mismo día.
2. Si es posible, se penaliza repetir el mismo origen entre cuentas en el mismo día, pero no se bloquea.

`acc_today_vid_ids` sigue siendo el filtro duro por cuenta. `day_vid_ids_used` conserva su penalización de scoring para repartir mejor cuando hay orígenes disponibles, sin impedir que cada cuenta consuma su propio set de copias. `assigned` sigue evitando reutilizar exactamente el mismo archivo físico dentro de la ejecución.

Si el número de orígenes lógicos disponibles para una cuenta no alcanza para llenar sus slots de un día, la ejecución debe fallar con el error existente de falta de candidatos. La disponibilidad global no se divide entre cuentas: 20 copias de 30 orígenes permiten 20 cuentas con esos 30 orígenes.

No se cambia la rotación entre días ni el flujo de manifest/captions; el alcance es exclusivamente la anti-colisión diaria de Por Cuentas.

## Validación

Se agrega una regresión E2E con 20 cuentas, 30 orígenes y 20 copias físicas por origen. La prueba verifica 30 videos por cuenta, origen único por cuenta/día y reutilización permitida entre cuentas.
