# Trust boundaries and eventual controls

## Boundary decisions

| Boundary | Inputs | Current decision | Required eventual control |
| --- | --- | --- | --- |
| Local operator to GUI | Forms, file selections, account identifiers | Treat all UI values and selected paths as untrusted until validated. Do not infer file-system authority from a displayed path. | Validation, rooted paths, authorization in the future agent. |
| GUI to local SQLite | Account data, schedules, state | Persist only through the database layer; SQLite integrity and confidentiality depend on local process and filesystem control. | Transactions, file permissions, migration backups. |
| GUI to external update service | Manifest and ZIP | Treat remote metadata and archives as untrusted until authenticated transport, archive checks, hash verification, version checks, and allowlist checks succeed. | Authenticated HTTPS, manifest signature, hash, anti-downgrade. |
| GUI to Telegram | Media, captions, destinations | Treat delivery as an explicit external operation. Keep authorization material out of source, releases, and logs; restrict the action to selected destinations and supported operations. | Server-side token relay or DPAPI fallback, allowlisted operations, redacted logs. |
| Future dashboard to API | Identity and commands | This is a planned boundary, not a current web-service claim. Commands must be scoped to the installation and safe to retry. | Short-lived tokens, roles, installation binding, idempotency. |

## Decision rules at the boundaries

### Local operator to GUI

- Validate field types, lengths, required values, and allowed account/state
  transitions before calling a writer.
- Resolve file selections against a declared allowed root; reject traversal,
  unexpected links/reparse points, and unsupported media types.
- Preserve an audit trail that identifies the action without copying sensitive
  values into diagnostics.

### GUI to local SQLite

- Use explicit transactions for related state changes and preserve a verified
  backup before migrations or replacement operations.
- Limit database-file and backup access to the local installation owner and
  trusted process identity where the operating system supports it.
- Validate migration outcomes and retain enough redacted status to recover
  safely without exposing account or delivery records.

### GUI to external update service

- Require HTTPS authentication appropriate to the service; protect any local
  authorization material from source control, releases, and logs.
- Verify manifest authenticity, ZIP hash, member paths, file allowlist, and
  strictly newer version before changing local files.
- Reject downgrades unless an explicit, independently authorized recovery
  mechanism is introduced and audited.

### GUI to Telegram

- Prefer a server-side token relay when the future architecture supports it;
  otherwise use a DPAPI-protected local fallback with the smallest necessary
  access scope.
- Allowlist delivery operations, media roots, and destinations selected by the
  authorized workflow; never make arbitrary remote calls from unchecked input.
- Redact authorization material, destination identifiers, and sensitive media
  paths from logs and user-visible error messages.

### Future dashboard to API

- Issue short-lived credentials and enforce roles before accepting a command.
- Bind requests to the intended installation and an allowlisted command shape.
- Give each command an idempotency key and record redacted execution status so
  retries cannot create duplicate local actions.

## Non-goals of this audit

This document does not claim that the eventual controls are implemented. It
records the decision points that later SQLite, Vault, release, secret, and
remote-control work must satisfy.
