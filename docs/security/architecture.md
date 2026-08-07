# Local GUI architecture boundary map

## Runtime shape

The audited product is a local Windows Python/CustomTkinter application, not a web service. Its normal startup path is:

```text
launcher.py
  -> local database/time-zone preparation
  -> updater.check_and_apply (remote update check when configured)
  -> gui_premium_v7.py
```

The GUI owns local account, tanda, scheduling, distribution, Telegram, video-editing, and Forge-facing workflows. Worker threads keep long-running GUI operations off the UI thread.

## Boundaries

| Boundary | Components | Observed responsibility | Security relevance |
| --- | --- | --- | --- |
| GUI | `gui_premium_v7.py`, `styles/`, CustomTkinter/Tkinter | Desktop controls, background workers, account and content workflows | Local operator boundary; UI input reaches database, files, network, and helper modules. |
| Database | `database.py`, `organizador.db` | SQLite-backed operational state used by GUI, organizer, and Telegram modules | Local persistent state; later changes must preserve data and avoid exposing it through updater payloads. |
| Distribution and Telegram | `Organizador.py`, `organizadortg.py`, `telegram_core.py` | Content organization, scheduling/delivery support, and Telegram-facing workflows | Network and credential-consuming boundary; no live traffic was generated for this baseline. |
| Multimedia | `videos.py`, `video_editor.py`, `metadata_pool.py` | Video generation, probing, rendering, variants, metadata, and media files | Child-process boundary for FFmpeg/FFprobe-style tooling; paths and generated files are security-relevant inputs/outputs. |
| Updater | `updater.py`, `launcher.py`, `build_release.ps1` | Manifest retrieval, archive validation, package application, release assembly | Remote archive and local replacement boundary; updater has URL, hash, archive-member, allowlist, backup, and atomic-copy logic. |

## Storage and release separation

`organizador.db` is the local operational database. The release builder contains an explicit release-file collection and archive/manifest generation. A normal update must be evaluated separately from local operational data so a code update does not silently replace state.

## Network and process boundaries

- The GUI makes HTTP requests for an account-checking workflow; Telegram delivery is implemented in a separate local module.
- The updater uses Python `urllib` to retrieve configured update metadata and release assets, then verifies and applies a package.
- The launcher can run a dependency/time-zone recovery command and launches the GUI child. Multimedia modules invoke subprocesses for media tooling.
- No dynamic Python import mechanism was found by the static inventory (`importlib.import_module` and `__import__`).

## Baseline limitations

This document describes source-visible boundaries and a local test run only. It does not validate live credentials, remote availability, update execution, external API authorization, Telegram sending, filesystem contents, or database records.
