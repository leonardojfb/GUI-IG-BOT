# Edición masiva de categoría y VA para cuentas

## Objetivo

Permitir seleccionar varias cuentas desde la tabla principal y cambiarles la categoría, el VA asignado o ambos desde un único diálogo.

## Alcance

- Modificar únicamente el flujo de gestión de cuentas del dashboard principal.
- Mantener la selección múltiple existente de la tabla.
- Mantener sin cambios la distribución, programación, OAuth, publicaciones y mensajería.
- Reutilizar `DatabaseManager.bulk_update_accounts(...)` para persistir el cambio masivo.

## Experiencia de usuario

1. El usuario selecciona una o más filas en “Cuentas registradas”.
2. Pulsa un botón único, “Editar cuentas seleccionadas”.
3. Se abre un diálogo con dos campos:
   - Categoría: opción “Sin cambios” más las categorías existentes.
   - VA: opción “Sin cambios” más “Sin Asignar” y los VAs existentes.
4. El usuario puede elegir solo categoría, solo VA o ambos.
5. El diálogo muestra el número de cuentas afectadas y permite confirmar o cancelar.
6. Al confirmar, se ejecuta una actualización masiva sobre los IDs de las cuentas seleccionadas.
7. La tabla y los indicadores se refrescan y se informa el resultado.

## Reglas y errores

- Sin selección: mostrar advertencia y no abrir el diálogo.
- Sin cambios elegidos: deshabilitar o rechazar la confirmación con una advertencia.
- La categoría seleccionada se registra también mediante `add_category` si fuera necesario, respetando la convención actual.
- “Sin Asignar” se persiste como el valor actual usado por la aplicación (`assigned_va = 'Sin Asignar'`).
- La actualización debe aplicar solo los campos elegidos; el campo marcado “Sin cambios” no se incluye en `bulk_update_accounts`.
- Ante un error de persistencia, no mostrar mensaje de éxito; informar el error y dejar la tabla sin afirmar que el cambio se completó.
- Las acciones individuales existentes deben seguir funcionando sin alterar su comportamiento.

## Diseño técnico

- En la barra de acciones del dashboard, reemplazar las dos acciones actuales de categoría y VA por una acción masiva única.
- Obtener las cuentas seleccionadas desde los identificadores de la tabla y resolver sus IDs de base de datos antes de actualizar.
- Crear un diálogo reutilizable para seleccionar los dos valores opcionales.
- Construir un diccionario de actualización únicamente con `account_type` y/o `assigned_va`, y pasarlo a `bulk_update_accounts(account_ids, **updates)`.
- Refrescar la tabla después de una actualización exitosa.

## Verificación

- Test de base de datos: actualizar categoría y VA para varios IDs y comprobar que las cuentas no seleccionadas permanecen intactas.
- Test de base de datos: actualizar solo categoría y comprobar que el VA no cambia; repetir al revés.
- Test de interfaz/lógica: selección vacía y diálogo sin cambios no ejecutan actualización.
- Verificación estática: compilación de `database.py` y `gui_premium_v7.py`, y `git diff --check`.
- Ejecutar la suite existente del repositorio y reportar el resultado real.
