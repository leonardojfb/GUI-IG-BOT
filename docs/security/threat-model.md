# Threat model: local Windows GUI

## Scope

The checked-out local application runs `launcher.py`, the updater, and
`gui_premium_v7.py`; it uses local SQLite, local media roots, Telegram-facing
modules, media-tool subprocesses, and a GitHub-backed update path. This is a
source-visible model, not a claim that live network, update, or Telegram
delivery behavior was tested.

## Independent risk classifications

| Risk class | Assets and boundary | Current control | Target control |
| --- | --- | --- |
| Token/cookie exposure | Telegram and update authorization across source, local configuration, memory, HTTPS requests, and diagnostics | HTTPS at external boundaries; source-visible handling is unsafe for a shared permanent Telegram credential. | Injectable provider, DPAPI-protected fallback, redaction, and future relay; never source, release, or plaintext configuration. |
| Distribution tampering | Executable, installer, ZIP, manifest, updater, and dependencies | URL, archive-member, hash, version, allowlist, backup, and atomic-copy checks. | Signed manifest, provenance/SBOM, Authenticode decision, and clean-machine tamper tests. |
| Arbitrary filesystem/command exposure | GUI paths, media roots, temporary files, launcher recovery, and FFmpeg/FFprobe processes | Argument-based subprocess calls; static inventory found no `shell=True` or `os.system`; UI paths remain untrusted. | Rooted-path validation, argument allowlists, ZIP/path checks, and regression tests. |
| SQLite integrity | `organizador.db`, journals, copies, and backup/restore | Database layer is the normal persistence route; filesystem is still a trust boundary. | Transaction and permission review, verified backups, and a reversible migration decision. |
| Update integrity | Remote manifest/ZIP and local replacement | HTTPS plus current verification and allowlisting; metadata remains untrusted before validation. | Signed anti-downgrade manifest, release provenance, and validation exercises. |

## Attackers and risk decisions

| Attacker | Asset | Precondition | Attack path | Impact | Current control | Target control | Residual risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Local user with full PC access | SQLite, media, config, installed files, memory | Same Windows account or accessible filesystem | Read, alter, copy, or replace local state/program files | Disclosure, unauthorized delivery setup, data loss, altered code execution | Database layer, ignored local state, updater checks | OS permissions, DPAPI fallback, transaction/backups, signed releases | Privileged local user can still inspect or alter their own installation. |
| Recipient of a copied executable | Program, updater settings, bundled files, local license behavior | Obtains executable or source distribution | Reverse engineers, copies configuration, patches local checks | Unauthorized reuse, tampered behavior, exposure of bundled material | Release list and updater allowlist constrain normal payloads | Release signing, protected local secrets, licensing/control-plane design | Client-side checks cannot make a copied binary inherently secret or unpatchable. |
| User sharing an installation | Accounts, schedules, Telegram authorization, media, SQLite | Multiple people can access one profile or app directory | Uses existing session/state or changes records | Cross-user disclosure or unauthorized external action | GUI workflow separation and database layer only | Installation identity, roles, protected storage, audit events | Shared OS access remains high trust until identity controls exist. |
| Attacker extracting Telegram credentials | Telegram authorization | Source, release, plaintext config, memory, or logs are readable | Searches readable artifacts or captures a running process | Takeover of Telegram operations | Credential-handling boundary is documented; no value is reproduced | Provider PR, removal from modules, DPAPI, redaction tests, future relay | Revoked material in private Git history remains residual exposure. |
| Attacker reading or modifying SQLite | Database, journals, copies, backups | Filesystem access to checkout-local state | Copies database or changes schedules, destinations, metadata, status | Confidentiality breach or integrity loss | `DatabaseManager` in normal application use | Permissions, transactions, backups, integrity checks, reversible migration | Filesystem compromise bypasses application validation. |
| Attacker patching a local license check | Executable and authorization decisions | Can modify executable, Python files, or memory | Changes local conditionals or intercepts results | Unauthorized feature use or bypassed policy | No server-side authorization plane exists today | Identity, installation binding, roles, server-issued policy | Offline local code cannot fully resist a determined modifier. |
| Attacker inspecting memory, files or network traffic | Tokens/cookies, personal data, media, manifests, delivery metadata | Can observe process, files, or network endpoint | Reads plaintext state/memory or captures traffic metadata | Disclosure and replay attempts | HTTPS; ignored files reduce accidental commits | DPAPI, short-lived relay credentials, TLS validation, redacted logs | Endpoint compromise can expose plaintext while client uses it. |
| Local malware | All local assets and execution paths | Executes as or above user account | Reads/modifies files, injects process, replaces dependencies, exfiltrates | Full local compromise and fraudulent operations | Updater verification limits one package path | Code signing, protected storage, endpoint controls, tamper tests, audit events | Malware with user-level access can act as that user. |
| Attacker replacing executable, installer, updater or dependency | Program integrity and execution authority | Can write application/release/dependency locations or influence acquisition | Substitutes binary, script, archive, or dependency before launch/update | Arbitrary code execution and persistence | Archive/hash/allowlist/backup/atomic update logic; no dynamic imports found | Authenticode, signed manifest, SBOM/provenance, locked build inputs | Local write access before launch is beyond an application-only control. |

## Security decisions

- Treat UI values, selected paths, manifests, ZIPs, and Telegram responses as
  untrusted until their relevant validation succeeds.
- A local user account is a trust boundary, not a substitute for authorization,
  secret storage, or integrity verification.
- No live network activity, credential validation, Telegram send, or update
  installation occurred in this audit.
