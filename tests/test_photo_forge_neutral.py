import json
from pathlib import Path

import pytest
from PIL import Image

from photo_forge import (
    create_neutral_photo_batch,
    discover_photo_batches,
    plan_neutral_photo_batch,
    render_photo_preview,
    validated_neutral_outputs,
)


def _source(path, offset):
    image = Image.new("RGB", (40, 50))
    image.putdata([((x * 5 + offset) % 256, (y * 7 + offset) % 256, (x + y) % 256)
                   for y in range(50) for x in range(40)])
    image.save(path)
    return path


def test_neutral_batch_is_flat_and_account_free(tmp_path):
    sources = [_source(tmp_path / f"source_{index}.png", index * 20) for index in range(2)]
    root = tmp_path / "imagenes_finales"
    plan = plan_neutral_photo_batch(sources, root, "tanda_fotos", finals_per_photo=3)

    assert len(plan) == 6
    assert len({row["source_id"] for row in plan}) == 2
    assert all("username" not in row and "account_id" not in row for row in plan)
    assert all((root / "tanda_fotos") == Path(row["output_path"]).parent for row in plan)

    result = create_neutral_photo_batch(plan, root, "tanda_fotos")
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["version"] == 3
    assert manifest["status"] == "validated"
    assert len(manifest["entries"]) == 6
    assert len({row["output_sha256"] for row in manifest["entries"]}) == 6
    assert len(validated_neutral_outputs(result["batch_dir"])) == 6
    assert discover_photo_batches(root)[0]["status"] == "validated"


def test_neutral_batch_detects_drift_without_touching_manifest(tmp_path):
    source = _source(tmp_path / "source.png", 4)
    root = tmp_path / "imagenes_finales"
    plan = plan_neutral_photo_batch([source], root, "lote", finals_per_photo=2)
    result = create_neutral_photo_batch(plan, root, "lote")
    manifest_path = Path(result["manifest_path"])
    before = manifest_path.read_bytes()
    Path(plan[0]["output_path"]).write_bytes(b"changed")

    with pytest.raises(ValueError, match="cambi[oó]|inv[aá]lid"):
        validated_neutral_outputs(result["batch_dir"])
    assert discover_photo_batches(root)[0]["status"] == "incomplete"
    assert discover_photo_batches(root)[0]["capacity"] == 1
    assert manifest_path.read_bytes() == before


def test_neutral_batch_does_not_replace_legacy_manifest(tmp_path):
    source = _source(tmp_path / "source.png", 1)
    root = tmp_path / "imagenes_finales"
    batch = root / "legacy"
    batch.mkdir(parents=True)
    old = batch / "photo_forge_manifest.json"
    old.write_text('{"version": 1, "entries": []}', encoding="utf-8")
    plan = plan_neutral_photo_batch([source], root, "legacy", finals_per_photo=1)

    with pytest.raises(ValueError, match="legado"):
        create_neutral_photo_batch(plan, root, "legacy")
    assert old.read_text(encoding="utf-8") == '{"version": 1, "entries": []}'


def test_interrupted_batch_is_visible_but_not_schedulable(tmp_path, monkeypatch):
    import photo_forge

    source = _source(tmp_path / "source.png", 8)
    root = tmp_path / "imagenes_finales"
    plan = plan_neutral_photo_batch([source], root, "interrupted", finals_per_photo=2)
    original = photo_forge._render_variant
    calls = 0

    def interrupted(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return original(*args)

    monkeypatch.setattr(photo_forge, "_render_variant", interrupted)
    with pytest.raises(KeyboardInterrupt):
        create_neutral_photo_batch(plan, root, "interrupted")
    batch = discover_photo_batches(root)[0]
    assert batch["status"] == "incomplete"
    assert batch["capacity"] == 1
    with pytest.raises(ValueError, match="validada"):
        validated_neutral_outputs(batch["path"])


def test_neutral_preview_uses_the_first_final_recipe(tmp_path):
    source = _source(tmp_path / "source.png", 14)
    plan = plan_neutral_photo_batch([source], tmp_path / "out", "batch", finals_per_photo=3,
                                    profile="post_4_5", strength="strong")
    preview = render_photo_preview(
        source, tmp_path / "preview.png", profile="post_4_5", strength="strong",
        account={"id": plan[0]["source_id"], "username": ""}, batch_name="batch",
        variants_per_image=3, variant_index=1,
    )
    assert preview["parameters"] == plan[0]["parameters"]
