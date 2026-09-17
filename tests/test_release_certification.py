import pytest

from release_certification import certify_checkpoints, make_gate_evidence


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
