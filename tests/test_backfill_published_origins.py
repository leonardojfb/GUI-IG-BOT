import hashlib

from backfill_published_origins import unique_forge_log_origin, verified_log_origin
from database import DatabaseManager


def test_verified_log_origin_requires_exact_bytes_and_unique_identity(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    folder = tmp_path / "WAN CLON MAIN"
    folder.mkdir()
    output = folder / "clip__c01.mov"
    output.write_bytes(b"published copy")
    db.save_video_transform_log(
        "forge", str(tmp_path / "source.mov"), str(output), {},
        tanda_name="WAN CLON MAIN", source_identity="a" * 64 + "_1",
    )
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    assert verified_log_origin(db, output.name, digest, {}) == "a" * 64
    assert verified_log_origin(db, output.name, "b" * 64, {}) is None
    assert unique_forge_log_origin(db, output.name) == "a" * 64
    conflicting = tmp_path / "OTHER" / output.name
    conflicting.parent.mkdir()
    db.save_video_transform_log(
        "forge", str(tmp_path / "other.mov"), str(conflicting), {},
        tanda_name="OTHER", source_identity="b" * 64 + "_1",
    )
    assert unique_forge_log_origin(db, output.name) is None
    db.close()
