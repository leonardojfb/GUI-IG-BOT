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

Tras corregir los hallazgos de la primera revision independiente, la suite
termino primero con `316 passed, 1 skipped` y, sobre el `HEAD` final, con
`316 passed, 2 skipped` en `114.73s`. Los skips variables fueron de UI Tk sin
display; ninguna prueba funcional fallo.

Compilacion de los modulos modificados:

```powershell
py -3.14 -B -m py_compile updater.py launcher.py calendar_manifest.py database.py organizadortg.py gui_premium_v7.py social_publishing.py
```

Resultado: codigo de salida `0`.

Builder real ejecutado en ambos modos:

```powershell
.\build_release.ps1 -BootstrapUpdater -OutputDirectory releases/r00-validation/bootstrap
.\build_release.ps1 -OutputDirectory releases/r00-validation/application
```

- Bootstrap: `MetodoIG-v1.0.41-bootstrap.zip`, solo `updater.py` y
  `version.json`, con `update_phase=bootstrap` y SHA-256
  `96b4773d8a09531fa7266247ac39aa90d26fbd6eb431a95addd52b5f1c0fd890`.
- Application: `MetodoIG-v1.0.41.zip`, manifest completo, sin datos locales y
  SHA-256 `6cb90e4f7d32305e4fe8cb725a3ceb4fda45f8be049165ad0d5c8cfff4a6f107`.
- La prueba automatizada aplica bootstrap y application de la misma version en
  secuencia; la segunda fase completa la app y elimina `update_phase`.

Recorrido E2E explicito, incluido paquete extraido:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/smoke_e2e_pipeline.py -q
```

Resultado: `2 passed in 241.07s`.

- El primer smoke corre productores, Logistica, manifest vigente y Telegram fake
  desde el checkout.
- El segundo smoke crea un ZIP temporal con el `$ReleaseFiles` real, lo extrae
  en una ruta nueva, ejecuta `launcher.main()` en esa instalacion parcheando solo
  el `Popen`, y luego corre el mismo pipeline importando los modulos desde el ZIP
  extraido.
- El contrato validado para el calendario actual es JSON-first: `27` outputs
  producidos, `9` entradas vigentes en `calendar_manifest.json`, `9` envios
  fake de Telegram y `0` copias fisicas obligatorias en `CALENDARIO_POSTEO`.

Inventario de BAT e imports:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_r00_inventory.py -q
```

Resultado: `2 passed in 0.12s`.

- `docs/R00_LAUNCH_IMPORT_INVENTORY.md` lista los `4` BAT/CMD del checkout y
  todos los modulos Python declarados en `$ReleaseFiles`.
- El inventario separa entrypoints de cliente, herramientas heredadas y modulos
  con efectos top-level como `organizadortg.py`, `gui_premium_v7.py` y
  `vercuentas.py`.

Runtime limpio desde release extraida:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/smoke_clean_runtime.py -q
```

Resultado: `1 passed in 23.35s`.

- El smoke crea un ZIP temporal con `$ReleaseFiles`, lo extrae, crea una venv
  limpia, instala solo `requirements.txt`, importa los modulos criticos y
  ejecuta `launcher.main()` con `Popen` falso.
- El primer rojo encontro que `telegram_core.py` importaba `pyrogram` top-level
  aunque la dependencia no esta en `requirements.txt`; se corrigio con import
  lazy dentro del helper de cliente Telegram.

Smoke visual con display Windows:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/smoke_ui_visual.py -q -rs
```

Resultado: `1 passed in 5.28s`.

- La prueba abre `InstagramAutoPro` con DB temporal, fuerza ventana visible,
  captura `%TEMP%\metodoig_r00_ui_visual.png` y valida tamano minimo,
  diversidad visual y presencia del fondo oscuro propio del GUI.
- La captura revisada muestra Dashboard, sidebar, tabla principal, botones y
  toast inicial visibles en `1200x760`.

## Contratos incorporados

- El manifest v1 conserva `caption_mode` y agrega el destino Reel/Trial explicito
  mediante campos aditivos que los lectores anteriores ignoran.
- Los destinos manuales permanecen bloqueados hasta publicar primero un lector
  de manifest v2; no pueden escribirse dentro de v1.
- Las entradas v1 sin destino siguen resolviendo Reel o Trial Reel segun
  `delivery_kind`.
- Regenerar Reel/Trial solo reemplaza su propio destino y conserva cualquier
  entrada manual preexistente.
- Telegram solo consume los dos destinos explicitamente soportados por su flujo.
- La DB conserva dominio Story compartido y override individual por cuenta.
- La pantalla Cuentas permite guardar el dominio y editar/desactivar el override.
- Un update normal exige `package_kind=application`, el conjunto completo de
  archivos y coincidencia exacta ZIP/manifest. El bootstrap admite exactamente
  `updater.py` y `version.json`.
- Tanto application como bootstrap rechazan `organizador.db` e historiales
  aunque el manifest los solicite.
- Builder y updater comparten `console_encoding.py` en sus allowlists.
- Un rollback no verificable retiene el backup, produce `RECOVERY_REQUIRED` y
  deja un marcador durable; launcher y updater bloquean ejecuciones posteriores.

## Hashes del corte

```text
6560ca85c8048e739d817e4feb9dfc09c68283c355cc62f4489cf5c12b7ba230  updater.py
84e6b1219568f55450a7a480cb33b4b9269b560be134c722a47d7a3c511bcb83  launcher.py
909c8b19a442b1c97024a7c1e70b52760e03909e525280d698291775c17d54a1  calendar_manifest.py
0a2eb084fe92fa0bbf7b4755a0e396be853cdda56c732d8a62010e87f7ee894c  database.py
d56b9ef100ef33df41ad087d4779398950579bbb4946ed1b2fb4e5ad831d700f  organizadortg.py
c39b615b4db198129f9202ac5f4ff5d5347ab404712d1bc6389ae629c6ac039f  gui_premium_v7.py
20d33bd5bc04b3b302573802a9990781785109c7d8c7cb1697c8546ba1d7a987  social_publishing.py
afdcb2ee2bf9a1c592f4d71462025296c0895a6a14cc4da4ce31e0eafb4d5101  build_release.ps1
a2f53f199df8b659ba48a679ec5507b854723468911fd38f08bb446591816a46  requirements.txt
b86674dfe4aa9f48596fe2e70bb067993a2bf13c6423c456f8f29385dd426860  release-manifest.json
59af7fb08016a6e5a6cab8e0aed9cf8375441d47d7f2719712dc9d69e5ac9fac  version.json
```

## Pendientes fuera de R00

R01 ya valida bootstrap contra updaters historicos reales desde `v1.0.2` hasta
`v1.0.41`; `v1.0.1` no contiene updater y queda como reinstalacion asistida.
R01 tambien resuelve feeds por cohorte desde `update_config.json` sin romper el
`manifest_url` historico y bloquea updates si queda un journal durable de
actualizacion interrumpida. R01/R02 todavia tienen fuera de este cierre: staging
de runtime, healthcheck y la matriz completa de interrupciones U01-U24.
