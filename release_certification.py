"""Deterministic local release gate; never overstates external validation."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


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
            try:
                passed = int(value.get("passed", 0))
                skipped = int(value.get("skipped", 0))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"evidencia invalida para {name}") from exc
            if passed < 1 or skipped < 0:
                raise ValueError(f"evidencia invalida para {name}")
            evidence[name] = {"status": "passed", "command": str(value["command"]), "passed": passed, "skipped": skipped}
        else:
            raise ValueError(f"evidencia invalida para {name}")
    return {"status": "certified_local", "gates": list(REQUIRED_GATES), "evidence": evidence, "external_validation": "required", "production_media": "not_run", "real_platform_publish": "not_run"}


def make_gate_evidence(command: str, *, passed: int, skipped: int = 0) -> dict:
    if not str(command).strip() or int(passed) < 1 or int(skipped) < 0:
        raise ValueError("evidencia de gate invalida")
    return {"status": "passed", "command": str(command), "passed": int(passed), "skipped": int(skipped)}


def verify_release_artifact(manifest_path, package_path):
    """Verify a release ZIP against its repository manifest before distribution."""
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        package = Path(package_path)
        digest = hashlib.sha256(package.read_bytes()).hexdigest()
        expected = str(manifest.get("sha256") or "").strip().lower()
        if not expected or digest != expected:
            raise ValueError("sha256 del paquete no coincide")
        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            raise ValueError("manifest sin files")
        with zipfile.ZipFile(package) as archive:
            present = set(archive.namelist())
        missing = [str(name) for name in files if str(name) not in present]
        if missing:
            raise ValueError("archivos ausentes en ZIP: " + ", ".join(missing))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise ValueError(f"artefacto de release invalido: {exc}") from exc
    version = str(manifest.get("version") or "").strip()
    package_kind = str(manifest.get("package_kind") or "").strip()
    if not version or package_kind not in {"application", "bootstrap"}:
        raise ValueError("manifest de release incompleto")
    return {"status": "verified", "version": version, "package_kind": package_kind, "files": len(files)}
