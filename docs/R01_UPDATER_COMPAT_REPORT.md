# R01 - Compatibilidad de updaters historicos

Fecha: 2026-09-12

Branch: `feature/r00-reproducible-baseline`

## Objetivo

Validar que las instalaciones existentes puedan recibir primero un paquete
bootstrap minimo antes de una release normal con modulos, manifiestos y reglas
mas estrictas. Esta fase evita que un cliente con un updater viejo reciba de
golpe una release que su allowlist o semantica anterior no sabe aplicar.

## Contrato validado

El paquete bootstrap contiene solamente:

- `updater.py`
- `version.json`

El `version.json` del bootstrap marca:

```json
{
  "version": "1.0.42",
  "update_phase": "bootstrap"
}
```

La release normal posterior puede usar la misma version si la instalacion local
quedo en fase `bootstrap`; el updater actual lo interpreta como finalizacion de
fase y permite aplicar el paquete `application` completo sin requerir una version
numerica distinta.

## Tags cubiertos

`tests/test_legacy_updater_tags.py` carga el `updater.py` real desde cada tag
historico `v1.0.*` que lo contiene, crea una instalacion temporal con datos de
cliente y aplica el bootstrap. El test exige:

- que `updater.py` sea reemplazado por el puente;
- que `version.json` avance a la version bootstrap;
- que `organizador.db` no cambie;
- que `telegram_state_v11.json` no cambie.

Tags validados: 38.

```text
v1.0.2, v1.0.3, v1.0.4, v1.0.5, v1.0.6, v1.0.7, v1.0.9,
v1.0.10, v1.0.11, v1.0.12, v1.0.13, v1.0.14, v1.0.15,
v1.0.16, v1.0.17, v1.0.18, v1.0.19, v1.0.20, v1.0.21,
v1.0.22, v1.0.23, v1.0.24, v1.0.25, v1.0.27, v1.0.28,
v1.0.29, v1.0.30, v1.0.31, v1.0.32, v1.0.33, v1.0.34,
v1.0.35, v1.0.36, v1.0.37, v1.0.38, v1.0.39, v1.0.40,
v1.0.41
```

`v1.0.1` queda fuera de esta garantia porque ese tag no contiene `updater.py`;
una instalacion en ese estado requiere entrega manual o reinstalacion asistida.

## Evidencia

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_legacy_updater_tags.py -q
```

Resultado: `1 passed in 5.19s`.

## Enrolamiento por cohorte

`updater.load_config()` mantiene compatibilidad con el formato historico:

```json
{
  "manifest_url": "https://updates.example.test/stable.json"
}
```

Si una instalacion tiene `manifest_feeds`, el updater resuelve la URL final
desde `channel` antes de tocar red:

```json
{
  "channel": "bootstrap",
  "manifest_url": "https://updates.example.test/stable.json",
  "manifest_feeds": {
    "stable": "https://updates.example.test/stable.json",
    "bootstrap": "https://updates.example.test/bootstrap.json"
  }
}
```

Reglas:

- sin `manifest_feeds`, se usa `manifest_url` como antes;
- con `manifest_feeds`, `channel` por defecto es `stable`;
- si el canal elegido no existe o no tiene URL, el update falla antes de red y
  el launcher conserva la app local salvo que exista `RECOVERY_REQUIRED`;
- `update_config.json` sigue siendo local del cliente y no se empaqueta en la
  release normal.

Evidencia focal:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_updater.py -q
```

Resultado: `20 passed in 1.09s`.

## Journal durable

`apply_package()` escribe `.update_journal.json` cuando empieza la fase de
aplicacion, despues de crear el backup y antes de copiar archivos al directorio
real. En una salida limpia, el journal se elimina. Si el proceso muere entre
copias, el siguiente `check_and_apply()` detecta el journal antes de consultar
red y levanta `RECOVERY_REQUIRED`.

Reglas:

- `.update_status.json` sigue teniendo prioridad si ya existe un error de
  recuperacion explicito;
- `.update_journal.json` bloquea nuevas comprobaciones antes de red;
- el mensaje incluye el `backup_dir` cuando quedo persistido;
- un rollback exitoso limpia el journal y conserva el comportamiento no fatal;
- un rollback no verificable mantiene `RECOVERY_REQUIRED` y deja evidencia para
  reparacion manual.

Evidencia focal:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_updater.py -q
```

Resultado: `22 passed in 1.17s`.

## Healthcheck local

`updater.healthcheck()` inspecciona la instalacion sin red y sin importar la GUI.
Tambien queda disponible como:

```powershell
py updater.py --healthcheck
```

Salida:

- `ok`: `true` solo si no hay errores;
- `version`: version local valida, si se pudo leer;
- `recovery_required`: `true` si existe `.update_status.json` o
  `.update_journal.json` bloqueante;
- `manifest_url` y `channel`: configuracion local ya resuelta por cohorte;
- `missing_required_files`: archivos de aplicacion que faltan;
- `missing_optional_files`: archivos opcionales ausentes;
- `errors` y `warnings`: diagnostico para soporte.

Evidencia focal:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_updater.py -q
```

Resultado: `24 passed in 1.22s`.

## Staging de runtime

`tests/test_update_staging.py` construye una instalacion temporal que representa
un cliente ya instalado, con archivos de app antiguos y datos locales:

- `organizador.db`;
- `telegram_state_v11.json`;
- `update_config.json`.

Luego aplica:

1. paquete `bootstrap` con `updater.py` y `version.json` en fase `bootstrap`;
2. paquete `application` completo con la misma version numerica;
3. `healthcheck()` sobre la instalacion final.

La validacion exige que la version final no conserve `update_phase`, que los
datos locales no cambien, que no queden `.update_journal.json` ni
`.update_status.json`, y que el healthcheck final sea `ok`.

Evidencia focal:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_update_staging.py -q
```

Resultado: `1 passed in 10.70s`.

## Estado R01

Cerrado para compatibilidad bootstrap con updaters historicos reales y
resolucion local de feeds por cohorte. Cerrado tambien el bloqueo por journal
durable ante terminacion abrupta, el healthcheck local y el staging de runtime.
R02 define la matriz U01-U24; sigue pendiente automatizar los gaps marcados
como "falta test dedicado".
