import json

import organizadortg


def test_load_json_recovers_from_corrupt_state_file(tmp_path, capsys):
    state_file = tmp_path / "telegram_state_v11.json"
    state_file.write_text("", encoding="utf-8")

    data = organizadortg.load_json(state_file)

    assert data == {}
    backups = list(tmp_path.glob("telegram_state_v11.json.corrupt_*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == ""
    assert not state_file.exists()
    assert "Estado JSON corrupto" in capsys.readouterr().out


def test_save_json_writes_valid_json_atomically(tmp_path):
    state_file = tmp_path / "telegram_state_v11.json"

    organizadortg.save_json(state_file, {"topic": {"id": 123}})

    assert json.loads(state_file.read_text(encoding="utf-8")) == {"topic": {"id": 123}}
    assert not list(tmp_path.glob("*.tmp"))
