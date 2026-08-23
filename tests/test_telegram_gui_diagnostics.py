from pathlib import Path

import gui_premium_v7


def test_telegram_runtime_diagnostics_reports_version_and_database(tmp_path):
    db_path = tmp_path / "organizador.db"
    db_path.write_bytes(b"sqlite")

    class Db:
        pass

    Db.db_path = str(db_path)

    lines = gui_premium_v7._telegram_runtime_diagnostics(
        Db(),
        app_dir=tmp_path,
        version_reader=lambda _path: "1.0.34",
    )

    joined = "\n".join(lines)
    assert "version=1.0.34" in joined
    assert f"db_path={db_path}" in joined
    assert "db_exists=True" in joined
    assert "db_size=6" in joined
    assert f"app_dir={Path(tmp_path)}" in joined


def test_telegram_done_logs_include_worker_exception_detail():
    logs = gui_premium_v7._telegram_done_logs(False, "unable to open database file")

    assert ("Error interno Telegram: unable to open database file", "ERROR") in logs
    assert ("El bot se detuvo por un error o cancelacion.", "ERROR") in logs
