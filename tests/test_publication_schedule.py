from calendar_manifest import build_entry
from publication_schedule import expand_lane_slots, merge_scheduled_entries


def _entry(tmp_path, username, filename, date, time):
    source = tmp_path / filename
    source.write_bytes(b"media")
    return build_entry(
        username,
        1,
        "normal",
        1,
        1,
        "OCTUBRE",
        str(source),
        filename,
        scheduled_date=date,
        scheduled_time=time,
        timezone="America/Argentina/Buenos_Aires",
    )


def test_merge_intercalates_new_publication_between_existing_times(tmp_path):
    early = _entry(tmp_path, "luna", "reel-1000.mp4", "2026-10-05", "10:00")
    late = _entry(tmp_path, "luna", "reel-1300.mp4", "2026-10-05", "13:00")
    post = _entry(tmp_path, "luna", "post-1200.jpg", "2026-10-05", "12:00")

    result = merge_scheduled_entries([early, late], [post])

    assert result.conflicts == []
    assert [entry["telegram_filename"] for entry in result.entries] == [
        "reel-1000.mp4",
        "post-1200.jpg",
        "reel-1300.mp4",
    ]


def test_merge_reports_exact_same_account_time_collision_without_dropping_existing(tmp_path):
    reel = _entry(tmp_path, "luna", "reel.mp4", "2026-10-05", "12:00")
    story = _entry(tmp_path, "luna", "story.jpg", "2026-10-05", "12:00")

    result = merge_scheduled_entries([reel], [story])

    assert len(result.conflicts) == 1
    assert result.conflicts[0].username == "luna"
    assert result.conflicts[0].scheduled_time == "12:00"
    assert result.entries == [reel]


def test_merge_allows_same_time_for_different_accounts(tmp_path):
    luna = _entry(tmp_path, "luna", "luna.mp4", "2026-10-05", "12:00")
    sol = _entry(tmp_path, "sol", "sol.mp4", "2026-10-05", "12:00")

    result = merge_scheduled_entries([luna], [sol])

    assert result.conflicts == []
    assert result.entries == [luna, sol]


def test_manifest_keeps_schedule_fields_optional_for_legacy_entries(tmp_path):
    legacy_source = tmp_path / "legacy.mp4"
    legacy_source.write_bytes(b"media")
    legacy = build_entry("luna", 1, "normal", 1, 1, "T", str(legacy_source), "legacy.mp4")
    scheduled = _entry(tmp_path, "luna", "new.mp4", "2026-10-05", "12:00")

    result = merge_scheduled_entries([legacy], [scheduled])

    assert result.conflicts == []
    assert result.entries[0] is scheduled
    assert result.entries[1] is legacy


def test_expand_lane_slots_uses_every_n_days_and_sorts_hours():
    slots = expand_lane_slots(
        start_date="2026-10-05",
        horizon_days=7,
        every_days=3,
        times=["16:00", "09:00"],
    )

    assert [(slot.scheduled_date, slot.scheduled_time) for slot in slots] == [
        ("2026-10-05", "09:00"),
        ("2026-10-05", "16:00"),
        ("2026-10-08", "09:00"),
        ("2026-10-08", "16:00"),
        ("2026-10-11", "09:00"),
        ("2026-10-11", "16:00"),
    ]


def test_expand_lane_slots_rejects_non_positive_frequency():
    try:
        expand_lane_slots("2026-10-05", 7, 0, ["09:00"])
    except ValueError as error:
        assert "cada N dias" in str(error)
    else:
        raise AssertionError("La frecuencia invalida debe bloquearse")
