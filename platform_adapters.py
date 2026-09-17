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


def _required(value, field):
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} no puede estar vacio")
    return normalized
