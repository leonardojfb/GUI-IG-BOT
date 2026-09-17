import pytest

from release_certification import certify_checkpoints, make_gate_evidence, verify_release_artifact


def test_certification_requires_all_local_gates():
    report = certify_checkpoints({"R11": True, "R12": True, "R13": True, "R14": True, "R15": True, "R16": True, "R17": True, "R18": True, "R19": True, "full_suite": True})
    assert report["status"] == "certified_local"
    assert report["external_validation"] == "required"


def test_certification_rejects_missing_gate():
    with pytest.raises(ValueError, match="gates pendientes"):
        certify_checkpoints({"R11": True})


def test_certification_accepts_reproducible_gate_evidence():
    gates = {name: make_gate_evidence("py -m pytest", passed=2) for name in [f"R{number:02d}" for number in range(11, 20)]}
    gates["full_suite"] = make_gate_evidence("py -m pytest .\\tests", passed=518, skipped=1)
    report = certify_checkpoints(gates)
    assert report["evidence"]["full_suite"]["passed"] == 518


def test_certification_rejects_evidence_without_passed_tests():
    gates = {name: make_gate_evidence("py -m pytest", passed=1) for name in [f"R{number:02d}" for number in range(11, 20)]}
    gates["full_suite"] = {"status": "passed", "command": "py -m pytest", "passed": 0}
    with pytest.raises(ValueError, match="evidencia invalida"):
        certify_checkpoints(gates)


def test_release_artifact_verifier_checks_hash_and_declared_files(tmp_path):
    import hashlib
    import json
    import zipfile

    package = tmp_path / "release.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("version.json", "{}")
        archive.writestr("photo_forge.py", "# module")
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    manifest = tmp_path / "release-manifest.json"
    manifest.write_text(json.dumps({"version": "1.0.0", "package_kind": "application", "sha256": digest, "files": ["version.json", "photo_forge.py"]}), encoding="utf-8")

    result = verify_release_artifact(manifest, package)

    assert result == {"status": "verified", "version": "1.0.0", "package_kind": "application", "files": 2}

    manifest.write_text(json.dumps({"version": "1.0.0", "package_kind": "application", "sha256": digest, "files": ["version.json", "missing.py"]}), encoding="utf-8")
    try:
        verify_release_artifact(manifest, package)
    except ValueError as exc:
        assert "missing.py" in str(exc)
    else:
        raise AssertionError("manifest file missing from zip must block verification")
