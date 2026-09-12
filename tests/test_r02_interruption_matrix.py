import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = REPO_ROOT / "docs" / "R02_INTERRUPTION_MATRIX.md"


def test_r02_interruption_matrix_lists_u01_through_u24_once():
    text = MATRIX_PATH.read_text(encoding="utf-8")
    ids = re.findall(r"^\| (U\d{2}) \|", text, re.M)

    assert ids == [f"U{number:02d}" for number in range(1, 25)]
    assert len(ids) == len(set(ids))


def test_r02_interruption_matrix_has_no_unautomated_gaps():
    text = MATRIX_PATH.read_text(encoding="utf-8")

    assert "falta test dedicado" not in text
    assert "cada corte U01-U24 tiene una" in text
