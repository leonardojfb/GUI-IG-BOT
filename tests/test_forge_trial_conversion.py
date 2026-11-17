import json
import sqlite3

import pytest

from database import DatabaseManager


def _forge_batch(db, root, name="Batch", *, status=True, complete=True):
    folder = root / name
    folder.mkdir(parents=True)
    names = ["first__c01.mp4", "first__c02.mp4"]
    for filename in names:
        output = folder / filename
        output.write_bytes(b"video")
        db.save_forge_video(name, "first.mp4", filename, "a" * 64)
        db.save_video_transform_log("forge", str(root / "source.mp4"), str(output), {},
                                    tanda_name=name, source_identity="a" * 64)
    db.add_tanda(name, name, name, "captions.txt")
    if status:
        (folder / "forge_batch_status.json").write_text(json.dumps({
            "state": "complete" if complete else "incomplete",
            "expected_count": len(names),
            "validated": names if complete else names[:1],
            "pending": [] if complete else [{"output_name": names[-1]}],
        }), encoding="utf-8")
    return folder, names


@pytest.mark.parametrize("has_status", [True, False])
def test_convert_completed_forge_batch_marks_trial_without_changing_calendar(tmp_path, has_status):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    root = tmp_path / "videos_finales"
    root.mkdir()
    folder, names = _forge_batch(db, root, status=has_status)
    old_output = tmp_path / "old" / names[0]
    old_output.parent.mkdir()
    old_output.write_bytes(b"old")
    db.save_video_transform_log("forge", str(tmp_path / "old-source.mp4"),
                                str(old_output), {}, tanda_name="Batch")
    calendar = tmp_path / "calendar_manifest.json"
    calendar.write_text('{"entries":[{"delivery_kind":"normal"}]}', encoding="utf-8")
    before_calendar = calendar.read_bytes()

    preview = db.preview_completed_forge_trial_conversion("Batch", root)
    assert preview["video_count"] == 2
    result = db.convert_completed_forge_tanda_to_trial("Batch", root, tmp_path / "backups")

    assert result["video_count"] == 2
    assert result["converted_logs"] == 2
    assert db.is_trial_tanda("Batch")
    assert db.get_tanda_by_name("Batch")["captions_file_path"] == "captions.txt"
    assert calendar.read_bytes() == before_calendar
    assert db.conn.execute("SELECT process_kind FROM video_transform_logs WHERE output_path=?",
                           (str(old_output),)).fetchone()[0] == "forge"
    assert all(db.conn.execute("SELECT process_kind FROM video_transform_logs WHERE output_path=?",
                               (str(folder / name),)).fetchone()[0] == "forge_trial" for name in names)
    backups = list((tmp_path / "backups").glob("organizador-before-forge-trial-*.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute("SELECT COUNT(*) FROM trial_tandas WHERE tanda_name='Batch'").fetchone()[0] == 0
    db.close()


def test_incomplete_forge_batch_cannot_be_converted(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    root = tmp_path / "videos_finales"
    root.mkdir()
    _forge_batch(db, root, complete=False)
    with pytest.raises(ValueError, match="incompleta"):
        db.convert_completed_forge_tanda_to_trial("Batch", root, tmp_path / "backups")
    assert not db.is_trial_tanda("Batch")
    assert not (tmp_path / "backups").exists()
    db.close()


def test_unregistered_legacy_forge_file_cannot_be_converted(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    root = tmp_path / "videos_finales"
    root.mkdir()
    folder, _names = _forge_batch(db, root, status=False)
    (folder / "unregistered.mp4").write_bytes(b"extra")
    with pytest.raises(ValueError, match="registrar"):
        db.preview_completed_forge_trial_conversion("Batch", root)
    assert not db.is_trial_tanda("Batch")
    db.close()
