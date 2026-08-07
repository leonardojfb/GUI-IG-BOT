# Security findings

## Evidence boundary

Findings are limited to the source-visible baseline, asset inventory, data-flow,
import inventory, and trust-boundary documents from the two prior audit commits.
Credential evidence is redacted: no credential value, prefix, length, hash, or
excerpt is recorded here.

| ID | Severity | Type | File or component | Storage method | Who can read it | Risk | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SEC-001 | P0 | Shared Telegram credential exposure | Telegram delivery source component(s) identified by baseline audit | Embedded plaintext source literal | Anyone with source, source distribution, or copied readable installation | A shared active permanent credential can be extracted and used to exercise Telegram authority. | Block publication; implement/test replacement path, remove embedded value, then owner revokes or rotates external credential. |
| SEC-002 | P1 | Update provenance gap | `updater.py`, `launcher.py`, release manifest, release builder | Remote manifest/ZIP with hash, archive, version, and allowlist checks but no documented signature/provenance control | Update service operator, local updater, or anyone altering acquisition path | A compromised or substituted update channel can target program integrity despite current checks. | Add signed-manifest, anti-downgrade, SBOM/provenance, Authenticode, and tamper validation on release branch. |
| SEC-003 | P1 | Local SQLite confidentiality and integrity exposure | `organizador.db`, journals, copies, backups through `database.py` | Checkout-local SQLite and filesystem artifacts | Local Windows user or process with filesystem access | Records may reveal operational data; direct modification can change schedules, destinations, metadata, and delivery status. | Review transactions and permissions, define backup/restore, choose reversible migration. |
| SEC-004 | P2 | Untrusted path and child-process boundary | GUI selection, media roots, `videos.py`, `video_editor.py`, `metadata_pool.py`, `organizadortg.py`, launcher recovery | UI/local paths and subprocess argument construction | Local operator or process influencing paths/files | Malformed or out-of-root input can cause unintended access or unsafe tool invocation if validation is incomplete. Static inventory found no `shell=True` or `os.system`, which does not prove path safety. | Add rooted-path, argument, ZIP, and subprocess validation with regression tests. |
| SEC-005 | P2 | Sensitive update configuration at rest | `update_config.json` and update-settings flow | Ignored local plaintext JSON that may contain update-service authorization material | Local Windows user or process with access to installation/configuration | Authorization material/settings can be copied, altered, or leaked through diagnostics. | Keep out of releases/commits; move authorization to protected storage and redact logs. |
| SEC-006 | P2 | Exceptional release of operational state | `build_release.ps1`, updater allowlist, optional database/history inputs | Explicit optional release switches and narrow updater exceptions | Release maintainer, recipient of exceptional package, local updater | An exceptional package can distribute state normal code-only updates should leave local. | Require review, manifest inspection, recipient/retention decision, and code-only defaults. |
| SEC-007 | P3 | Live-validation coverage limitation | Audit execution boundary for launcher, updater, Telegram workflows | Static/test-backed audit; live network actions deliberately excluded | Reviewers and release decision-makers relying on audit | Documentation cannot prove remote availability, credential validity, update installation, or delivery authorization. | Execute clean-machine, tamper, authorization, rollback, and reverse-engineering validation before relying on runtime properties. |

## Finding status

Only SEC-001 is a release blocker under the P0 gate. P1 through P3 findings
define separate follow-on work; none is represented as fixed by this
documentation.
