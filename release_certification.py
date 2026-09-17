"""Deterministic local release gate; never overstates external validation."""
from __future__ import annotations


REQUIRED_GATES = tuple([f"R{number:02d}" for number in range(11, 20)] + ["full_suite"])


def certify_checkpoints(gates):
    missing = [name for name in REQUIRED_GATES if not gates.get(name)]
    if missing:
        raise ValueError(f"gates pendientes: {', '.join(missing)}")
    return {"status": "certified_local", "gates": list(REQUIRED_GATES), "external_validation": "required", "production_media": "not_run", "real_platform_publish": "not_run"}
