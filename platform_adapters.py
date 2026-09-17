"""Explicit-capability platform adapter contract; no network implementation."""
from __future__ import annotations


PHASES = ("prepare", "deliver", "schedule", "publish", "verify")


class PlatformAdapter:
    def __init__(self, platform: str, capabilities, *, handlers=None):
        self.platform = _required(platform, "platform")
        self.capabilities = frozenset(str(item) for item in (capabilities or []))
        unknown = self.capabilities - set(PHASES)
        if unknown:
            raise ValueError(f"capacidades desconocidas: {sorted(unknown)}")
        self.handlers = dict(handlers or {})


def execute_platform_action(adapter: PlatformAdapter, phase: str, request: dict):
    phase = _required(phase, "phase")
    if phase not in PHASES:
        raise ValueError(f"fase no soportada: {phase}")
    if phase not in adapter.capabilities:
        raise ValueError(f"{adapter.platform} no soporta {phase}")
    handler = adapter.handlers.get(phase)
    if handler is None:
        raise RuntimeError(f"adapter {adapter.platform} no tiene handler para {phase}")
    result = handler(dict(request or {}))
    if not isinstance(result, dict) or not result:
        raise RuntimeError("el adapter debe devolver un resultado explicito")
    return {"platform": adapter.platform, "phase": phase, **result}


def execute_publication_group(group, adapters, phase="publish"):
    """Execute sibling destinations without converting one failure into all failures."""
    results = []
    for item in group or []:
        destination_id = _required(item.get("destination_id"), "destination_id")
        adapter_key = _required(item.get("adapter"), "adapter")
        adapter = (adapters or {}).get(adapter_key)
        if adapter is None:
            results.append({"destination_id": destination_id, "status": "failed", "error": "adapter no encontrado"})
            continue
        try:
            outcome = execute_platform_action(adapter, phase, item.get("request") or {})
            results.append({"destination_id": destination_id, **{key: value for key, value in outcome.items() if key != "phase"}})
        except (RuntimeError, ValueError) as exc:
            results.append({"destination_id": destination_id, "platform": adapter.platform, "status": "failed", "error": str(exc)})
    if not results:
        raise ValueError("publication group vacio")
    statuses = {result.get("status") for result in results}
    status = "confirmed" if statuses == {"confirmed"} else "partial" if "confirmed" in statuses else "failed"
    return {"status": status, "results": results}


def detect_downstream_duplicates(assignments):
    """Find same-root assignments colliding on the exact downstream lane."""
    groups = {}
    for index, item in enumerate(assignments or []):
        key = (item.get("root_id"), item.get("destination_id"), item.get("lane"))
        if all(part not in (None, "") for part in key):
            groups.setdefault(key, []).append(index)
    return [
        {"indexes": indexes, "root_id": key[0], "destination_id": key[1], "lane": key[2]}
        for key, indexes in groups.items() if len(indexes) > 1
    ]


def _required(value, field):
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} no puede estar vacio")
    return normalized
