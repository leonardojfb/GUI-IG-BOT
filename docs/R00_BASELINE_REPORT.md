# R00 baseline reproducible

Fecha: 2026-09-11

## Identidad

- Rama de trabajo: `feature/r00-reproducible-baseline`
- Worktree: `.worktrees/r00-reproducible-baseline`
- Base exacta: `3c8ba6f2c46eb1f3d43b5da54c7abb2bf8176d32`
- Base publicada local: `origin/main`, tag `v1.0.41`
- Version declarada en la base: `1.0.41`
- El checkout primario sucio no se uso como base ni se modifico.

## Evidencia ejecutada

Base sin cambios:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider -q
```

Resultado inicial: `293 passed, 1 skipped`.

Tras el primer corte R00:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider -q
```

Resultado preliminar: `309 passed, 2 skipped`. Esos skips correspondieron a
pruebas Tk que llaman `pytest.skip("no display available")`; no se convirtieron
fallos funcionales en skips.

La misma orden ejecutada nuevamente sobre el `HEAD` comprometido termino con
`311 passed` en `123.15s`, sin skips ni fallos.

Compilacion de los modulos modificados:

```powershell
py -3.14 -B -m py_compile updater.py launcher.py calendar_manifest.py database.py organizadortg.py gui_premium_v7.py social_publishing.py
```

Resultado: codigo de salida `0`.

## Contratos incorporados

- El manifest v1 conserva `caption_mode` y agrega destino de publicacion y
  metadata manual mediante campos aditivos.
- Las entradas v1 sin destino siguen resolviendo Reel o Trial Reel segun
  `delivery_kind`.
- Reemplazar un destino manual no elimina otros carriles de la misma cuenta.
- Telegram solo consume los dos destinos explicitamente soportados por su flujo.
- La DB conserva dominio Story compartido y override individual por cuenta.
- La pantalla Cuentas permite guardar el dominio y editar/desactivar el override.
- Un update normal exige `files`, exige que ZIP y manifest coincidan y rechaza
  `organizador.db` e historiales aunque el manifest los solicite.
- Builder y updater comparten `console_encoding.py` en sus allowlists.
- Un rollback no verificable produce `RECOVERY_REQUIRED`; el launcher no abre la
  GUI en ese estado.

## Hashes del corte

```text
835904b4a70ee25a25433475784a2d86b79eb5a57e469b5a626a533faf81536b  updater.py
de4b01fd3305c7aa19d5b93e3392a8e5d81867d4e557d468a64a021662e4cfae  launcher.py
833f771ebf594a175f86ef873cdba673b45b7307e1feab6986b71479bf54a19d  calendar_manifest.py
0a2eb084fe92fa0bbf7b4755a0e396be853cdda56c732d8a62010e87f7ee894c  database.py
75adb93f2663feb2f547bab786f093db08de88f6a160061d429d1b466335d39c  organizadortg.py
c39b615b4db198129f9202ac5f4ff5d5347ab404712d1bc6389ae629c6ac039f  gui_premium_v7.py
20d33bd5bc04b3b302573802a9990781785109c7d8c7cb1697c8546ba1d7a987  social_publishing.py
597cfacfcd5dabd7c1be1865707121e3de3dc91c51d0d5b45c5452802318ed0d  build_release.ps1
a2f53f199df8b659ba48a679ec5507b854723468911fd38f08bb446591816a46  requirements.txt
b86674dfe4aa9f48596fe2e70bb067993a2bf13c6423c456f8f29385dd426860  release-manifest.json
59af7fb08016a6e5a6cab8e0aed9cf8375441d47d7f2719712dc9d69e5ac9fac  version.json
```

## Pendientes antes de cerrar R00

- Ejecutar el recorrido launcher, GUI, productores, ambas logisticas, manifest y
  Telegram fake desde un ZIP extraido en una ruta nueva.
- Inventariar y clasificar todos los BAT y los imports con efectos secundarios.
- Verificar dependencias transitivas en una instalacion sin paquetes heredados.
- Convertir los recorridos UI hoy omitidos sin display en evidencia visual sobre
  Windows con display disponible.

R01 y R02 tampoco estan cerrados: faltan pruebas por cohorte del updater antiguo,
doble salto por puente, journal durable, backups retenidos, staging de runtime,
healthcheck y la matriz completa de interrupciones U01-U24.
