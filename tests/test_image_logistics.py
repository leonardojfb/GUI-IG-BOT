from pathlib import Path

import pytest
from PIL import Image

from calendar_manifest import append_scheduled_entries_from_plan, load_entries
from image_logistics import build_image_plan
from photo_forge import create_neutral_photo_batch, plan_neutral_photo_batch


def _batch(tmp_path, count):
    tmp_path.mkdir(parents=True, exist_ok=True)
    sources = []
    for index in range(2):
        path = tmp_path / f"source{index}.png"
        image = Image.new("RGB", (40, 50))
        image.putdata([((x * 5 + index * 20) % 256, (y * 7) % 256, (x + y) % 256)
                       for y in range(50) for x in range(40)])
        image.save(path)
        sources.append(path)
    root = tmp_path / "imagenes_finales"
    plan = plan_neutral_photo_batch(sources, root, "batch", finals_per_photo=count)
    result = create_neutral_photo_batch(plan, root, "batch")
    return Path(result["batch_dir"]), [plan[0]["source_id"], plan[count]["source_id"]]


def _block(source_ids, **overrides):
    return {
        "source_ids": source_ids,
        "targets": ["instagram_post", "facebook_page_post"],
        "start_date": "2030-01-01",
        "horizon_days": 1,
        "every_days": 1,
        "times": ["12:00"],
        "quantity_daily": 1,
        "timezone": "America/Buenos_Aires",
        "caption": "Prueba",
        **overrides,
    }


def test_full_set_carousel_two_accounts_two_platforms(tmp_path):
    batch, ids = _batch(tmp_path, 4)
    accounts = [{"username": "a", "id": 1}, {"username": "b", "id": 2}]
    entries = build_image_plan(batch, "CAT", accounts, [_block(ids)], [])

    assert len(entries) == 4
    assert all(len(row["media_items"]) == 2 for row in entries)
    assert len({item["source_path"] for row in entries for item in row["media_items"]}) == 8
    assert {row["publication_target"] for row in entries} == {"instagram_post", "facebook_page_post"}
    assert all(row["source_path"] == row["media_items"][0]["source_path"] for row in entries)


def test_ten_accounts_require_ten_distinct_finals_per_platform(tmp_path):
    batch, ids = _batch(tmp_path, 20)
    accounts = [{"username": f"acct_{index}", "id": index} for index in range(10)]
    entries = build_image_plan(batch, "CAT", accounts, [_block([ids[0]])], [])
    assert len(entries) == 20
    assert len({entry["source_path"] for entry in entries}) == 20
    assert all({entry["publication_target"] for entry in entries if entry["username"] == account["username"]}
               == {"instagram_post", "facebook_page_post"} for account in accounts)


def test_each_identity_keeps_its_own_story_link(tmp_path):
    batch, ids = _batch(tmp_path, 4)
    accounts = [{"username": "a", "id": 1}, {"username": "b", "id": 2}]
    links = {"a": "https://example.com/a", "b": "https://other.example/b"}
    block = _block([ids[0]], targets=["instagram_story", "facebook_story"],
                   story_announcement_text="Hoy", story_links=links)
    entries = build_image_plan(batch, "CAT", accounts, [block], [])
    assert len(entries) == 4
    assert {row["story_link_url"] for row in entries if row["username"] == "a"} == {links["a"]}
    assert {row["story_link_url"] for row in entries if row["username"] == "b"} == {links["b"]}


def test_marketplace_requires_conditional_fields_and_photo_reel_is_ig_only(tmp_path):
    batch, ids = _batch(tmp_path, 2)
    account = [{"username": "a", "id": 1}]
    with pytest.raises(ValueError, match="Marketplace necesita"):
        build_image_plan(batch, "CAT", account,
                         [_block([ids[0]], targets=["facebook_marketplace_listing"])], [])
    market = {"title": "Producto", "price": "20", "condition": "Nuevo", "description": "Detalle"}
    entries = build_image_plan(batch, "CAT", account, [
        _block([ids[0]], targets=["facebook_marketplace_listing"], marketplace=market),
    ], [])
    assert entries[0]["platform_payload"] == market
    with pytest.raises(ValueError, match="carrusel"):
        build_image_plan(batch, "CAT", account,
                         [_block(ids, targets=["instagram_photo_reel"])], [])


def test_insufficient_capacity_and_collision_leave_calendar_unchanged(tmp_path):
    batch, ids = _batch(tmp_path, 3)
    path = tmp_path / "calendar_manifest.json"
    accounts = [{"username": "a", "id": 1}, {"username": "b", "id": 2}]

    with pytest.raises(ValueError, match="capacidad|disponibles"):
        append_scheduled_entries_from_plan(path, lambda current: build_image_plan(batch, "CAT", accounts, [_block(ids)], current))
    assert not path.exists()

    batch2, ids2 = _batch(tmp_path / "other", 4)
    old = {"id": "old", "username": "a", "source_path": str(tmp_path / "old.mp4"),
           "scheduled_date": "2030-01-01", "scheduled_time": "12:00"}
    from calendar_manifest import replace_entries
    replace_entries(path, [old], {"a"}, "normal")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Choque de horario"):
        append_scheduled_entries_from_plan(
            path, lambda current: build_image_plan(batch2, "CAT", accounts, [_block(ids2)], current),
        )
    assert path.read_bytes() == before


def test_interleaves_story_with_existing_reels_and_reserves_once(tmp_path):
    batch, ids = _batch(tmp_path, 1)
    path = tmp_path / "calendar_manifest.json"
    reels = [
        {"id": hour, "username": "a", "source_path": str(tmp_path / f"{hour}.mp4"),
         "scheduled_date": "2030-01-01", "scheduled_time": hour}
        for hour in ("10:00", "13:00")
    ]
    from calendar_manifest import replace_entries
    replace_entries(path, reels, {"a"}, "normal")
    block = _block([ids[0]], targets=["instagram_story"],
                   story_announcement_text="Hoy", story_links={"a": "https://example.com/a"})
    result = append_scheduled_entries_from_plan(
        path, lambda current: build_image_plan(batch, "CAT", [{"username": "a", "id": 1}], [block], current),
    )
    assert not result.conflicts
    assert [row["scheduled_time"] for row in load_entries(path, require_source=False)] == ["10:00", "12:00", "13:00"]
    assert load_entries(path, require_source=False)[1]["story_link_url"] == "https://example.com/a"
    before = path.read_bytes()
    with pytest.raises(ValueError, match="capacidad|disponibles"):
        append_scheduled_entries_from_plan(
            path, lambda current: build_image_plan(batch, "CAT", [{"username": "a", "id": 1}], [block], current),
        )
    assert path.read_bytes() == before
