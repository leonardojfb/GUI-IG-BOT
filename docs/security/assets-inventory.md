# Asset inventory and storage classification

## Scope and handling rule

This is a static inventory of paths, components, and storage roles in the
`security/00-audit` worktree. It intentionally records no configuration
values, database rows, credential literals, account values, or media contents.
The sensitive-storage scan was run before inspection with path and line-number
output only.

Classifications used below are:

- **Tracked release input**: versioned source or metadata that can enter a
  release under the release-builder and updater rules.
- **Local user data**: persistent installation-specific operational data that
  must stay with the local installation in normal releases.
- **Ignored backup/cache data**: disposable, recovery, temporary, generated,
  or cached state that must not enter source control or a normal release.

## Persistent and release assets

| Path or asset | Type and classification | Writer | Readers | Persistence and risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `organizador.db` | SQLite; local user data | `DatabaseManager` and narrowly scoped maintenance utilities | GUI, organizer, Telegram, video, and reporting modules through `database.py` | Checkout-local persistent state. Schema holds account identifiers, category/assignment data, schedules, delivery/fingerprint paths and status, Telegram group identifiers, and media metadata. High confidentiality and integrity impact. | Keep ignored and out of normal releases; enforce local file permissions, transaction/migration backups, and a documented backup/restore flow. |
| `organizador.default.db` | Generated SQLite template; conditional release input | `make_default_db.py` via `DatabaseManager` schema creation | `launcher.py` for first-install database creation | Generated only with `build_release.ps1 -IncludeClientDatabase`; it is intended to be schema-only, not customer state. Integrity-sensitive but not a source of user data when generated correctly. | Generate in a clean build directory, verify it contains schema only, and retain the first-install-only replacement rule. |
| `dist_accounts_history.json` | JSON; local user data, exceptional conditional release input | Distribution/account-history workflow | Distribution workflow and any explicit recovery/release path | Persistent account-history state can link operations to identifiers. It is ignored locally, but builder and updater allow an explicit exception. | Exclude from normal releases; require an explicit, reviewed export decision and document recipient/retention when inclusion is authorized. |
| `telegram_state_v11.json` | JSON; local user data | Telegram controller | Telegram controller and GUI status presentation | Ignored delivery/status state; may associate local deliveries with destinations and timing. | Keep local and ignored; protect with local permissions and redact diagnostics. |
| `update_config.json` | JSON; local user configuration | Local operator or GUI update-settings workflow | `updater.py`, launcher update check, and GUI update controls | Ignored installation configuration. It can contain update-service authorization material and remote update settings. | Do not package or commit it; move authorization material to a protected local secret store or DPAPI-backed setting and redact logs. |
| `.update_status.json` | JSON; ignored cache/status data | Updater | GUI status presentation | Local update outcome cache, not a release input. Integrity affects operator decisions. | Keep ignored; validate structure before display and avoid storing authorization data. |
| `update_config.example.json` | JSON; tracked release/source example | Maintainer | Human installer or release setup process | Template must be non-sensitive. | Keep examples value-free and test that no real authorization material is copied into them. |
| `version.json` and `release-manifest.json` | JSON; tracked release inputs | Release builder | Updater, launcher, release process | Version and package metadata; manifest contains package location, hash, and file list. Integrity-critical, not a suitable secret store. | Treat as signed/verified release metadata; validate hash, allowed files, version monotonicity, and provenance before application. |
| `build_release.ps1` release-file list and optional switches | PowerShell; tracked release assembly control | Release maintainer | Release builder and release tests | The base list is code-focused. Optional switches can include the template, real database, or history. | Make normal builds code-only; require explicit review and post-build manifest inspection for any data-bearing switch. |
| `updater.py` `DEFAULT_UPDATEABLE_FILES` | Python allowlist; tracked release-application control | Source maintainer | Updater and updater tests | A file is applied only when both manifest-listed and allowlisted. It currently includes narrow data-file exceptions. | Preserve dual allowlisting; require an explicit security review before adding files, especially persistent state. |

## Writable roots and transient artifacts

| Root or artifact | Type and classification | Writer | Readers | Persistence and risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `videos_finales/` | Derived local media; local user data | Video and editing workflows | Organizer and Telegram preparation | Ignored generated media; filenames and contents may be personal or commercially sensitive. | Keep outside release archives; constrain paths to the selected rooted workspace and apply retention/deletion policy. |
| `CALENDARIO_POSTEO/` | Scheduled local media tree; local user data | Organizer/scheduling workflow | Telegram preparation and delivery workflow | Ignored calendar state linking media, schedules, and destinations. | Keep local; validate path traversal and protect the root with filesystem permissions. |
| `releases/` and `release-*test/` | ZIPs, manifests, test release outputs; ignored backup/cache data | Release builder and tests | Installer/updater test process | Generated artifacts can accidentally contain optional data. | Keep ignored; inspect archive contents and manifest before publishing; remove expired local artifacts under an approved retention policy. |
| Database journal files and `*.sqlite` / `*.sqlite3` | SQLite journal, copies, or test data; ignored backup/cache data | SQLite and test helpers | SQLite/test processes | Transient or copied state can expose the same records as the operational database. | Keep ignored, do not distribute, and securely remove obsolete copies according to the recovery policy. |
| Temporary directories created by updater | Temporary ZIP/download extraction; ignored cache data | `updater.py` | Updater during a single update | OS temporary storage; contains untrusted archive material before validation and staged replacement files after validation. | Use restrictive temp permissions where available, validate before apply, and clean up on success and failure. |
| Named temporary Telegram files and preview files | Temporary media; ignored cache data | `organizadortg.py` and `video_editor.py` | Telegram preparation or preview process | Local transient media; may carry source/derived content. | Create in controlled temporary locations, delete deterministically, and never log full sensitive paths unnecessarily. |
| `*.bak*` | Backup artifacts; no matching file was observed in this worktree scan | Recovery/maintenance process when used | Operator recovery process | A backup has the confidentiality of its source database or configuration. | Keep backups outside release staging, encrypt or permission-protect them, and record retention/restore ownership. |

## Storage and release decision

Normal releases are code and non-sensitive metadata only. Local databases,
delivery state, update configuration, media, backups, and caches remain local.
The builder's optional data switches and the updater's corresponding narrow
allowlist are exceptions that require a deliberate, reviewed release decision;
their presence is not authorization to distribute local customer data.
