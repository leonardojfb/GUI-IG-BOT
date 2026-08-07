# Remediation plan and release gates

## Non-negotiable P0 release gate

> No new binary, updater package, installer or source distribution may be published
> while a shared active permanent Telegram credential is embedded in source, release
> payload or local configuration in plaintext. A revoked credential that remains
> only in private Git history is recorded as residual exposure and is not a release
> blocker; this program does not rewrite Git history.

This is an operational publishing gate, not a documentation-only finding. It
remains active until the replacement implementation is reviewed and verified.

## Dedicated P0 remediation PR

A later dedicated PR must, before the external owner revokes or rotates the
production credential:

1. Add an injectable credential provider.
2. Remove the embedded value from affected modules, release payloads, and local
   plaintext configuration.
3. Protect the local fallback with DPAPI.
4. Add tests that prove credential redaction in logs, failures, and support
   diagnostics.
5. Move the owner token to the future server relay only after that path exists
   and is tested.
6. Test the replacement path without a real Telegram send; then have the owner
   revoke or rotate the external production credential.

Any private Git-history occurrence is recorded only as residual exposure,
without its value. This program does not rewrite Git history.

## Follow-on branches and acceptance gates

Each branch is independently reviewable. It may start only after explicit review
of the preceding PR, and cannot be claimed complete based only on audit
documentation.

| Branch | Scope | Acceptance gate |
| --- | --- | --- |
| `security/01-code-hardening` | Credential provider, request/subprocess/path/ZIP fixes, redaction tests. | Preceding PR explicitly reviewed; regression tests show provider/input-boundary behavior without secret output. |
| `security/02-telegram-secrets` | DPAPI fallback, simulated Telegram tests, relay contract; no real send. | `security/01-code-hardening` explicitly reviewed; DPAPI and simulated tests pass with no real send or disclosure. |
| `security/03-sqlite-protection` | Transaction/permission review, backups, reversible migration decision. | `security/02-telegram-secrets` explicitly reviewed; backup/restore and transaction behavior tested; reversible decision recorded. |
| `security/04-control-plane` | FastAPI/PostgreSQL identity, installations, roles, command queue, agent contract. | `security/03-sqlite-protection` explicitly reviewed; typed, scoped, idempotent authorization tests pass without arbitrary shell, SQL, path, or generic-file commands. |
| `security/05-vault-local` | Rooted Vault, hashes, local index, lineage, audit events. | `security/04-control-plane` explicitly reviewed; rooted storage, hash/lineage, append-only event tests pass. |
| `security/06-metrics-dashboard` | Manual metric snapshots and read-only analysis views. | `security/05-vault-local` explicitly reviewed; views are read-only and snapshots do not claim causality. |
| `security/07-build-release` | Nuitka/PyArmor evaluation, signed manifest, SBOM, Authenticode checklist. | `security/06-metrics-dashboard` explicitly reviewed; release artifact, manifest/signature, SBOM, signing evidence reviewed. |
| `security/08-validation` | Clean-machine, tamper, authorization, rollback, reverse-engineering validation. | `security/07-build-release` explicitly reviewed; acceptance matrix demonstrates each scenario and residual risks. |

## Release decision record

No branch above changes the P0 publication decision merely by existing. The P0
gate is cleared only when the dedicated remediation PR passes review, its
replacement path is tested, active plaintext placement is gone from
source/release/local configuration, and the owner completes external
revoke-or-rotate action. Private historical exposure remains a residual risk,
not a release blocker after revocation.
