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

## Estado R01

Cerrado para compatibilidad bootstrap con updaters historicos reales y
resolucion local de feeds por cohorte. Sigue pendiente dentro de R01/R02:
journal durable ante terminacion abrupta, staging de runtime, healthcheck y
matriz U01-U24.
