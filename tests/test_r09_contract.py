import sqlite3

from durable_jobs import ensure_job_schema


def test_r09_schema_is_opt_in_and_uses_existing_sqlite_connection():
    conn = sqlite3.connect(":memory:")
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='durable_jobs'").fetchone() is None
    ensure_job_schema(conn)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"durable_jobs", "durable_job_steps", "durable_job_events"} <= names


def test_r09_modules_are_import_safe():
    import durable_jobs  # noqa: F401
    import job_runner  # noqa: F401

