# Security Baseline Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Produce a safe, evidence-backed baseline, sensitive-data inventory and threat model for the local Windows GUI without changing application logic or exposing secrets.

**Architecture:** This is the first, documentation-only security PR for the existing local flow \`launcher.py -> gui_premium_v7.py\`. It records the current Python/SQLite/Telegram/update boundaries and creates an explicit P0 gate before any packaging or production use. The FastAPI/PostgreSQL control plane, Vault and dashboard from the approved design are separate follow-on subprojects; they must not be invented inside this audit PR.

**Tech Stack:** Python 3.14, CustomTkinter, SQLite, requests, Telegram Bot API, GitHub Release updater, PowerShell, pytest.

## Global Constraints

- Work only in \`security/00-audit\`; never modify the user's original dirty checkout.
- Do not edit runtime Python, database schema, release scripts, local data or production configuration in this plan.
- Do not start the GUI or send Telegram messages during the audit.
- Do not print, copy, commit or redact-and-replace a real token, cookie, password, private key or session value.
- Secret reports contain only type, file/component, storage method, readers, risk and recommendation.
- Preserve \`launcher.py -> gui_premium_v7.py\`, current SQLite files and normal code-only update behavior.
- Use \`py -m pytest -q\` for the full regression gate; the expected baseline is 144 passing tests at commit \`f74fb5e\`.
- Do not publish, package or deploy while a P0/P1 remains open.

## File Structure

| Path | Responsibility |
| --- | --- |
| \`docs/security/00-baseline.md\` | Git/runtime/test evidence and safe launch assessment. |
| \`docs/security/architecture.md\` | Current modules, entrypoint, external executables and network integrations. |
| \`docs/security/import-graph.md\` | Static import graph, dynamic-import findings and optional-module notes. |
| \`docs/security/data-flow.md\` | Account, media, SQLite, update and Telegram data flows. |
| \`docs/security/assets-inventory.md\` | Files, local databases, generated data, assets and writable roots. |
| \`docs/security/trust-boundaries.md\` | Actors, trust boundaries, allowed and untrusted inputs. |
| \`docs/security/threat-model.md\` | Assets, attackers, abuse paths and mitigations. |
| \`docs/security/findings.md\` | P0-P3 findings without secret values. |
| \`docs/security/remediation-plan.md\` | Ordered remediation gates and rollback requirements. |

---

### Task 1: Capture reproducible local baseline

**Files:**
- Create: \`docs/security/00-baseline.md\`
- Create: \`docs/security/architecture.md\`
- Create: \`docs/security/import-graph.md\`
- Modify: none
- Test: full existing suite via \`py -m pytest -q\`

**Interfaces:**
- Consumes: the checked-out local GUI and its tracked metadata only.
- Produces: a versioned baseline that later remediation PRs cite by commit and test command.

- [ ] **Step 1: Record immutable repository and runtime facts without reading secret values**

Run from the isolated worktree:

\`\`\`powershell
git branch --show-current
git rev-parse HEAD
git status --short
py --version
node --version
npm --version
Get-Content -LiteralPath requirements.txt
\`\`\`

Record absent tools as absent. Include the working-tree status verbatim only if it contains paths, never file contents.

- [ ] **Step 2: Record the real launcher contract**

Read \`launcher.py\`, \`gui_premium_v7.py\`, \`updater.py\` and \`build_release.ps1\`. In \`00-baseline.md\`, record only these facts when evidenced:

\`\`\`text
entrypoint: launcher.py
GUI child: gui_premium_v7.py
local operational database: organizador.db
update behavior: launcher checks updates before opening the GUI
\`\`\`

Do not invoke \`launcher.py\`: its update path may make a real network request. State that this is a static and test-backed baseline, not a live Telegram run.

- [ ] **Step 3: Build the static import and executable inventory**

Run the following commands and summarize their output by module group, not by copying source:

\`\`\`powershell
rg -n '^(import|from) ' --glob '*.py' --glob '!tests/**' .
rg -n -i 'importlib|__import__|subprocess|Popen|ffmpeg|ffprobe|shell=True|os\\.system' --glob '*.py' --glob '!tests/**' .
rg -n -i 'requests\\.|urllib|api\\.telegram\\.org|github\\.com|raw\\.githubusercontent\\.com' --glob '*.py' --glob '!tests/**' .
\`\`\`

\`import-graph.md\` must name importers, imported local modules, external Python dependencies, dynamic imports and child-process boundaries. \`architecture.md\` must identify the GUI, database, multimedia and updater boundaries.

- [ ] **Step 4: Run the full baseline test suite**

Run:

\`\`\`powershell
py -m pytest -q
\`\`\`

Expected at the audit base: \`144 passed\`. Record the exact count and elapsed time in \`00-baseline.md\`. If the command fails or times out, stop this plan and document the actual failure; do not call the baseline green.

- [ ] **Step 5: Self-review documentation and commit the baseline task**

Run:

\`\`\`powershell
git diff --check
git status --short
\`\`\`

Confirm that only the three documentation files are staged. Then commit:

\`\`\`powershell
git add docs/security/00-baseline.md docs/security/architecture.md docs/security/import-graph.md
git commit -m "docs: add security baseline audit"
\`\`\`

---

### Task 2: Inventory data, storage and trust boundaries without leaking secrets

**Files:**
- Create: \`docs/security/data-flow.md\`
- Create: \`docs/security/assets-inventory.md\`
- Create: \`docs/security/trust-boundaries.md\`
- Modify: none
- Test: \`py -m pytest tests/test_updater.py tests/test_release_package_manifest.py -q\`

**Interfaces:**
- Consumes: module/file names, database schema declarations and test behavior; never secret values or copied database rows.
- Produces: the asset and data map required for later secret, SQLite, Vault, release and remote-control work.

- [ ] **Step 1: Use a redacted sensitive-storage scanner before inspecting findings**

Create no new executable script. Use these PowerShell commands, which output only path and line number:

\`\`\`powershell
$patterns = 'token|secret|password|api[_-]?key|cookie|session|private[_-]?key|authorization'
Get-ChildItem -Recurse -File -Include *.py,*.json,*.ps1,*.bat,*.md |
  Select-String -Pattern $patterns -CaseSensitive:$false |
  Select-Object Path,LineNumber
git log --all --format='%H %ad %s' --date=short -G 'TOKEN|SECRET|PASSWORD|API[_-]?KEY'
\`\`\`

Never use \`Select-String\` output that includes \`Line\` or \`Matches\`; do not add \`-Context\` and do not open a matching value in the terminal.

- [ ] **Step 2: Inventory databases, writable roots and release inputs**

Run:

\`\`\`powershell
rg --files -uu -g '*.db' -g '*.sqlite' -g '*.sqlite3' -g '*.json' -g '*.log' -g '*.bak*' .
rg -n 'DB_PATH|sqlite3\\.connect|TemporaryDirectory|NamedTemporaryFile|mkstemp|release-manifest|DEFAULT_UPDATEABLE_FILES' --glob '*.py' --glob '*.ps1' .
\`\`\`

For each relevant item, record only path/type, writer, readers, persistence, classification and recommendation. \`assets-inventory.md\` must distinguish tracked release input from local user data and ignored backup/cache data.

- [ ] **Step 3: Describe the current data flows**

Write \`data-flow.md\` with five flows:

\`\`\`text
GUI account/configuration -> DatabaseManager -> organizador.db
local source/derived media -> videos_finales and CALENDARIO_POSTEO -> Telegram preparation
launcher -> updater -> verified ZIP -> atomic local replacement -> GUI
GUI update settings -> local update_config.json -> GitHub Release API
Telegram controller -> HTTPS Telegram Bot API -> delivery/status local state
\`\`\`

For every arrow, identify producer, consumer, storage, trust level and whether a secret or personal data may cross it. Do not record actual endpoint credentials or account values.

- [ ] **Step 4: Define the trust boundaries**

Write \`trust-boundaries.md\` with these boundaries and a decision for each input:

| Boundary | Inputs | Required eventual control |
| --- | --- | --- |
| Local operator to GUI | forms, file selections, account identifiers | validation, rooted paths, authorization in the future agent |
| GUI to local SQLite | account data, schedules, state | transactions, file permissions, migration backups |
| GUI to external update service | manifest and ZIP | authenticated HTTPS, manifest signature, hash, anti-downgrade |
| GUI to Telegram | media, captions, destinations | server-side token relay or DPAPI fallback, allowlisted operations, redacted logs |
| Future dashboard to API | identity and commands | short-lived tokens, roles, installation binding, idempotency |

- [ ] **Step 5: Verify existing updater/release protections and commit**

Run:

\`\`\`powershell
py -m pytest tests/test_updater.py tests/test_release_package_manifest.py -q
git diff --check
\`\`\`

Expected: all selected tests pass and no whitespace errors. Then commit:

\`\`\`powershell
git add docs/security/data-flow.md docs/security/assets-inventory.md docs/security/trust-boundaries.md
git commit -m "docs: map security data and trust boundaries"
\`\`\`

---

### Task 3: Produce the threat model, findings and P0 remediation gate

**Files:**
- Create: \`docs/security/threat-model.md\`
- Create: \`docs/security/findings.md\`
- Create: \`docs/security/remediation-plan.md\`
- Modify: none
- Test: \`py -m pytest -q\`

**Interfaces:**
- Consumes: the two prior audit commits and no secret values.
- Produces: severity-ranked decisions that gate all later code and release changes.

- [ ] **Step 1: Write the threat model against the real local architecture**

\`threat-model.md\` must cover at least:

\`\`\`text
local user with full PC access
recipient of a copied executable
user sharing an installation
attacker extracting Telegram credentials
attacker reading or modifying SQLite
attacker patching a local license check
attacker inspecting memory, files or network traffic
local malware
attacker replacing executable, installer, updater or dependency
\`\`\`

For every attacker, include asset, precondition, attack path, impact, current control, target control and residual risk. Classify token/cookie exposure, distribution tampering, arbitrary filesystem/command exposure, SQLite integrity and update integrity independently.

- [ ] **Step 2: Record findings using the mandatory redacted format**

\`findings.md\` uses exactly this table structure:

| ID | Severity | Type | File or component | Storage method | Who can read it | Risk | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |

Record the verified embedded Telegram credential as a \`P0\` by file/component and storage method only. Do not include its value, prefix, length, hash or an excerpt. Also record any further findings only after evidence from Tasks 1-2.

- [ ] **Step 3: Add a non-negotiable P0 release gate**

Write this operational decision in \`remediation-plan.md\`:

\`\`\`text
No new binary, updater package, installer or source distribution may be published
while a shared permanent Telegram credential is embedded in source, release
payload, local configuration in plaintext or reachable Git history.
\`\`\`

The remediation plan must require a later dedicated PR to add an injectable credential provider, remove the embedded value from affected modules, protect the local fallback with DPAPI, add redaction tests, and then move the owner token to the future server relay. Do not rotate or request a real secret inside this audit branch; rotating an external production credential requires the owner's separate action and a tested replacement path.

- [ ] **Step 4: Define follow-on plans with acceptance gates**

Append these independently reviewable follow-on branches to \`remediation-plan.md\`:

\`\`\`text
security/01-code-hardening: credential provider, request/subprocess/path/ZIP fixes and redaction tests.
security/02-telegram-secrets: DPAPI fallback, simulated Telegram tests and relay contract; no real send.
security/03-sqlite-protection: transaction/permission review, backups and reversible migration decision.
security/04-control-plane: FastAPI/PostgreSQL identity, installations, roles, command queue and agent contract.
security/05-vault-local: rooted Vault, hashes, local index, lineage and audit events.
security/06-metrics-dashboard: manual metric snapshots and read-only analysis views.
security/07-build-release: Nuitka/PyArmor evaluation, signed manifest, SBOM and Authenticode checklist.
security/08-validation: clean-machine, tamper, authorization, rollback and reverse-engineering validation.
\`\`\`

Each later plan must start after an explicit review of the preceding PR; no branch may be claimed complete based only on documentation from this audit.

- [ ] **Step 5: Run final evidence checks and commit**

Run:

\`\`\`powershell
py -m pytest -q
git diff --check
git status --short
\`\`\`

Expected: 144 passing tests, no whitespace errors and exactly the three threat model documents staged for this task. Then commit:

\`\`\`powershell
git add docs/security/threat-model.md docs/security/findings.md docs/security/remediation-plan.md
git commit -m "docs: add threat model and remediation gates"
\`\`\`

## Plan self-review

- The plan implements only the audit boundary required before application changes.
- It covers entrypoint, imports, subprocesses, SQLite, assets, updater, Telegram, secrets, trust boundaries, attacker model and P0-P3 findings.
- It maps the approved control plane, Vault, metric and release work to separate follow-on plans rather than mixing independent subsystems.
- The only verified P0 is recorded by type/component, never by secret value.
- Every task has exact paths, commands, a verification gate and a single-scope commit.
