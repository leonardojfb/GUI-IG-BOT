from pathlib import Path
import pytest

from photo_forge import (
    build_photo_forge_job_spec,
    audit_photo_forge_reuse,
    make_photo_forge_handler,
    perceptual_distance,
    perceptual_signature,
    render_photo_preview,
    render_photo_variant,
    validate_image,
)


def _image(path, color="red", size=(640, 480)):
    from PIL import Image

    Image.new("RGB", size, color).save(path)


def test_photo_recipe_is_versioned_and_deterministic(tmp_path):
    source = tmp_path / "source.jpg"
    _image(source)

    spec = build_photo_forge_job_spec(
        [source],
        output_dir=tmp_path / "out",
        variants=[{"brightness": 1.1}, {"flip": True}],
        profile="instagram_post",
    )

    assert spec["job_type"] == "photo_forge.variant.v1"
    assert spec["recipe"]["recipe_version"] == 1
    assert len(spec["steps"]) == 2
    assert spec["steps"][0]["payload"]["variant_id"] == "v01"
    assert spec["steps"][1]["payload"]["output_path"].endswith("__pf02.jpg")


def test_validate_image_rejects_corrupt_and_bad_space(tmp_path):
    broken = tmp_path / "broken.jpg"
    broken.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="corrupta"):
        validate_image(broken)

    wide = tmp_path / "wide.jpg"
    _image(wide, size=(2000, 400))
    with pytest.raises(ValueError, match="aspect"):
        validate_image(wide, profile="instagram_post")


def test_variant_and_preview_never_mutate_source(tmp_path):
    source = tmp_path / "source.jpg"
    _image(source, size=(640, 480))
    before = source.read_bytes()
    output = tmp_path / "out" / "variant.jpg"

    result = render_photo_variant(source, output, {"brightness": 1.2, "rotate": 4}, profile="instagram_post")
    preview = render_photo_preview(source, tmp_path / "preview.jpg", {"flip": True})

    assert result["output_path"] == str(output)
    assert output.is_file() and output.stat().st_size > 0
    assert preview["path"].endswith("preview.jpg")
    assert source.read_bytes() == before
    assert validate_image(output)["width"] > 0


def test_perceptual_signature_is_deterministic_and_distance_is_bounded(tmp_path):
    source = tmp_path / "source.png"
    similar = tmp_path / "similar.png"
    different = tmp_path / "different.png"
    from PIL import Image, ImageDraw

    for path, color in ((source, "white"), (similar, "white"), (different, "black")):
        image = Image.new("RGB", (64, 64), color)
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 8, 28, 28), fill="red" if color == "white" else "blue")
        image.save(path)
    first = perceptual_signature(source)
    assert first == perceptual_signature(source)
    assert perceptual_distance(first, perceptual_signature(similar)) == 0
    assert 0 <= perceptual_distance(first, perceptual_signature(different)) <= 64


def test_photo_handler_resumes_and_records_vault_lineage(tmp_path):
    import database
    from vault.lineage import VaultLineage
    from vault.storage import VaultStorage

    source = tmp_path / "source.jpg"
    _image(source)
    output = tmp_path / "out.jpg"
    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    storage = VaultStorage(db, tmp_path / "vault")
    source_asset = storage.import_managed(source)
    handler = make_photo_forge_handler(db, vault_storage=storage)
    step = {"payload": {"source_path": str(source), "output_path": str(output), "operations": {"flip": True}, "profile": "instagram_post", "variant_id": "v01"}}

    first = handler(step, {}, lambda value: None)
    second = handler(step, {}, lambda value: None)

    assert first["resumed"] is False
    assert second["resumed"] is True
    logs = db.list_video_transform_logs()
    assert len(logs) == 1
    output_asset = storage.import_managed(output)
    parents = VaultLineage(db).parents_for_asset(output_asset["asset_id"])
    assert source_asset["asset_id"] in [row["parent_asset_id"] for row in parents]
    db.close()


def test_photo_reuse_policy_blocks_same_account_and_flags_cross_account(tmp_path):
    import database
    from vault.lineage import VaultLineage
    from vault.signatures import VaultSignatures
    from vault.storage import VaultStorage

    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    storage = VaultStorage(db, tmp_path / "vault")
    source = tmp_path / "source.jpg"
    other = tmp_path / "other.jpg"
    _image(source, size=(640, 480))
    _image(other, size=(640, 480))
    first = storage.import_managed(source)["asset_id"]
    second = storage.import_managed(other)["asset_id"]
    signatures = VaultSignatures(db)
    signatures.record_signature(first, "visual_bucket", "scene-1", algorithm="manual")
    signatures.record_signature(second, "visual_bucket", "scene-1", algorithm="manual")
    VaultLineage(db).record_usage(first, "calendar", "entry-1", {"username": "alice", "lane": "feed"})

    same_account = audit_photo_forge_reuse(db, [{"asset_id": second, "username": "ALICE", "lane": "feed"}])
    cross_account = audit_photo_forge_reuse(db, [{"asset_id": second, "username": "bob", "lane": "feed"}])

    assert same_account["status"] == "blocked"
    assert same_account["conflicts"][0]["reason"] == "same_account_lane"
    assert cross_account["status"] == "warning"
    assert cross_account["conflicts"][0]["reason"] == "cross_account_reuse"
    db.close()


def test_legacy_gui_exposes_photo_forge_controls():
    source = open("gui_premium_v7.py", encoding="utf-8").read()
    assert 'title="Photo Forge"' in source
    assert "def photo_forge_add_images" in source
    assert "def photo_forge_preview" in source
    assert "def photo_forge_generate" in source
