import pytest

from release_certification import certify_checkpoints


def test_certification_requires_all_local_gates():
    report = certify_checkpoints({"R11": True, "R12": True, "R13": True, "R14": True, "R15": True, "R16": True, "R17": True, "R18": True, "R19": True, "full_suite": True})
    assert report["status"] == "certified_local"
    assert report["external_validation"] == "required"


def test_certification_rejects_missing_gate():
    with pytest.raises(ValueError, match="gates pendientes"):
        certify_checkpoints({"R11": True})
