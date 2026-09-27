from pathlib import Path

from por_cuentas_lanes import LaneRequest, build_lane_entries


def test_build_lane_entries_uses_existing_paths_without_calendar_copies(tmp_path):
    first = tmp_path / "story_a.jpg"
    second = tmp_path / "story_b.jpg"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    request = LaneRequest(
        username="luna",
        account_id=12,
        tanda="OCTUBRE",
        delivery_kind="normal",
        publication_target="instagram_story",
        timezone="America/Argentina/Buenos_Aires",
        media_kind="image",
        lane_id="stories-ig",
        plan_id="plan-1",
        start_date="2026-10-05",
        horizon_days=1,
        every_days=1,
        times=["09:00", "16:00"],
        story_link_url="https://links.example/luna",
        story_announcement_text="Nuevo contenido",
    )

    entries = build_lane_entries(request, [first, second])

    assert [entry["source_path"] for entry in entries] == [str(first.resolve()), str(second.resolve())]
    assert [(entry["scheduled_date"], entry["scheduled_time"]) for entry in entries] == [
        ("2026-10-05", "09:00"),
        ("2026-10-05", "16:00"),
    ]
    assert all("CALENDARIO_POSTEO" not in entry["source_path"] for entry in entries)
    assert all(entry["publication_target"] == "instagram_story" for entry in entries)


def test_build_lane_entries_requires_one_existing_final_per_slot(tmp_path):
    only = tmp_path / "only.jpg"
    only.write_bytes(b"one")
    request = LaneRequest(
        username="luna",
        account_id=12,
        tanda="OCTUBRE",
        delivery_kind="normal",
        publication_target="instagram_post",
        timezone="America/Argentina/Buenos_Aires",
        media_kind="image",
        lane_id="posts-ig",
        plan_id="plan-1",
        start_date="2026-10-05",
        horizon_days=4,
        every_days=3,
        times=["14:00"],
    )

    try:
        build_lane_entries(request, [only])
    except ValueError as error:
        assert "finales existentes" in str(error)
    else:
        raise AssertionError("No se pueden inventar ni reutilizar archivos finales")
