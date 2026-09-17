"""Deterministic local release gate; never overstates external validation."""
from __future__ import annotations


REQUIRED_GATES = tuple([f"R{number:02d}" for number in range(11, 20)] + ["full_suite"])


def certify_checkpoints(gates):
    missing = [name for name in REQUIRED_GATES if not gates.get(name)]
    if missing:
        raise ValueError(f"gates pendientes: {', '.join(missing)}")
    evidence = {}
    for name in REQUIRED_GATES:
        value = gates[name]
        if value is True:
            evidence[name] = {"status": "passed", "evidence_quality": "legacy_boolean"}
        elif isinstance(value, dict) and value.get("status") == "passed" and value.get("command"):
            evidence[name] = {"status": "passed", "command": str(value["command"]), "passed": int(value.get("passed", 0)), "skipped": int(value.get("skipped", 0))}
        else:
            raise ValueError(f"evidencia invalida para {name}")
    return {"status": "certified_local", "gates": list(REQUIRED_GATES), "evidence": evidence, "external_validation": "required", "production_media": "not_run", "real_platform_publish": "not_run"}


def make_gate_evidence(command: str, *, passed: int, skipped: int = 0) -> dict:
    if not str(command).strip() or int(passed) < 1 or int(skipped) < 0:
        raise ValueError("evidencia de gate invalida")
    return {"status": "passed", "command": str(command), "passed": int(passed), "skipped": int(skipped)}
