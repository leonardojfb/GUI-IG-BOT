# Current data flows

## Scope

These are source-visible current flows, recorded without credentials, account
values, database rows, or media contents. A trust level describes the origin at
the time it reaches the arrow, not whether the source is benign.

## 1. GUI account/configuration to local database

```text
GUI account/configuration -> DatabaseManager -> organizador.db
```

| Arrow | Producer | Consumer | Storage | Trust level | Secret or personal data crossing |
| --- | --- | --- | --- | --- | --- |
| GUI account/configuration -> `DatabaseManager` | Local operator through GUI forms | `database.py` `DatabaseManager` | In-memory form values before SQLite writes | Locally supplied and untrusted until validated | Account identifiers, categories, assignments, notes, schedules, group identifiers, and media-related paths may cross; no credential value is documented here. |
| `DatabaseManager` -> `organizador.db` | `DatabaseManager` | Checkout-local SQLite file | Persistent local SQLite | Application-controlled write after validation; local filesystem remains a trust boundary | The same operational/personal data may persist; database fields that identify destinations or content need confidentiality and integrity protection. |

## 2. Local media preparation for Telegram

```text
local source/derived media -> videos_finales and CALENDARIO_POSTEO -> Telegram preparation
```

| Arrow | Producer | Consumer | Storage | Trust level | Secret or personal data crossing |
| --- | --- | --- | --- | --- | --- |
| Local source/derived media -> `videos_finales` and `CALENDARIO_POSTEO` | Local operator, video/editing and organizer workflows | Derived-media and calendar roots | Local ignored media trees | Local file input is untrusted until path/content checks; generated output is application-controlled but still sensitive | Source and derived media, filenames, captions, schedule context, and account-linked organization metadata may cross. |
| `videos_finales` and `CALENDARIO_POSTEO` -> Telegram preparation | Local media roots | Telegram preparation/controller modules | In-memory preparation and temporary media files | Local state selected for an external action | Media, captions, destination association, and schedule/status metadata may cross; operational authorization is consumed by the controller but is not recorded. |

## 3. Update acquisition and application

```text
launcher -> updater -> verified ZIP -> atomic local replacement -> GUI
```

| Arrow | Producer | Consumer | Storage | Trust level | Secret or personal data crossing |
| --- | --- | --- | --- | --- | --- |
| `launcher` -> updater | `launcher.py` | `updater.py` | Local process invocation and local update configuration | Local code, with configuration-controlled remote target | Update settings and status may cross; authorization material may be read locally and must remain redacted. |
| Updater -> verified ZIP | Remote update service through updater | Updater validation logic | Temporary download/extraction directory | Remote artifact is untrusted until URL, archive members, hash, version, and allowlist checks pass | Manifest/package metadata crosses; no personal data should be required for a normal code update. |
| Verified ZIP -> atomic local replacement | Updater validation/apply logic | Allowed application files in local application directory | Temporary staging, backup/replacement path, then application directory | Trusted only after verification; local replacement remains integrity-sensitive | Normal flow should carry code and release metadata only. Any explicit local-data exception requires separate authorization. |
| Atomic local replacement -> GUI | Updated local application files | `gui_premium_v7.py` child launched by launcher | Application directory | Locally verified program files | No secret or personal data should cross from a normal release; GUI later reads its own local state. |

## 4. Update settings and remote manifest service

```text
GUI update settings -> local update_config.json -> GitHub Release API
```

| Arrow | Producer | Consumer | Storage | Trust level | Secret or personal data crossing |
| --- | --- | --- | --- | --- | --- |
| GUI update settings -> local `update_config.json` | Local operator/GUI settings workflow | Local updater configuration file | Ignored local JSON | Operator input is untrusted until validation; file is sensitive local configuration | Remote endpoint/repository settings and update authorization material may cross into local storage. |
| Local `update_config.json` -> GitHub Release API | Updater using configuration | External update service | HTTPS request and response | Local configuration crosses to a remote service boundary; remote response is untrusted until verified | Authorization material may be used for the request; release metadata and ZIP location return. Do not log authorization material. |

## 5. Telegram delivery and local state

```text
Telegram controller -> HTTPS Telegram Bot API -> delivery/status local state
```

| Arrow | Producer | Consumer | Storage | Trust level | Secret or personal data crossing |
| --- | --- | --- | --- | --- | --- |
| Telegram controller -> HTTPS Telegram Bot API | Telegram controller/preparation modules | External Telegram service | HTTPS request and temporary local media as needed | External service boundary; outbound operation must be explicitly authorized | Media, captions, destination identifiers, and service authorization are used; they are not written into this document. |
| HTTPS Telegram Bot API -> delivery/status local state | External Telegram service response | Telegram controller and GUI status views | Ignored local delivery/status state and SQLite-linked workflow state | Remote response is untrusted until validated | Delivery result, timestamps, destination association, and error/status data may cross; logs must redact authorization and sensitive identifiers. |

## Cross-flow constraints

- Local operational state does not become release input by default.
- Media and destination information should cross the network only through the
  selected, allowlisted delivery operation.
- Remote manifests, ZIPs, and Telegram responses remain untrusted data until
  their relevant validation step succeeds.
- Future secret remediation must change storage and access paths without adding
  secret literals to source, release artifacts, or audit documentation.
