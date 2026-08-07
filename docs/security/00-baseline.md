# Security baseline: local Windows GUI

## Scope and reproduction

This is a static and test-backed baseline of the checked-out local Windows GUI. It does not start `launcher.py`, the GUI, or a Telegram delivery run. In particular, invoking the launcher is intentionally excluded because its update check can contact the network.

Run the baseline from the linked worktree:

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
py --version
node --version
npm --version
Get-Content -LiteralPath requirements.txt
py -m pytest -q
```

## Immutable repository and runtime facts

| Fact | Observed value |
| --- | --- |
| Worktree branch | `security/00-audit` |
| Audited commit | `abda724bab8956bd0f9b4b9f67f2f33eb415df7c` |
| Working-tree status before this documentation task | `?? .superpowers/` |
| Python | `Python 3.14.0` |
| Node.js | `v24.15.0` |
| npm | `11.12.1` |
| Python requirements | `customtkinter==5.2.2`, `requests==2.32.3`, `tzdata` |

The pre-existing untracked `.superpowers/` path is task-management material and is not baseline application source. It is deliberately excluded from the commit.

## Launcher contract

Static inspection and the test suite evidence the following contract:

```text
entrypoint: launcher.py
GUI child: gui_premium_v7.py
local operational database: organizador.db
update behavior: launcher checks updates before opening the GUI
```

`launcher.py` ensures time-zone support and an operational database, calls `updater.check_and_apply`, and then launches the GUI child with a windowless Python executable when available. It writes update-status information for the GUI to present. This is not evidence of a live update, Telegram connection, or Telegram send.

## Baseline test result

Command: `py -m pytest -q`

Result: `144 passed in 116.10s (0:01:56)` on this worktree and audited commit before the documentation commit.

## Credential-handling boundary

This audit records only component, storage method, readers, risk, and recommendation. It does not reproduce credential values. Local configuration and source modules may be readers of operational credentials; later remediation must inventory and remove or rotate exposed material without placing values in audit artifacts.
