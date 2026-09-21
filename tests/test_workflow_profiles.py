import sqlite3

import pytest

from workflow_queue import ensure_workflow_queue_schema
from workflow_profiles import (
    delete_profile,
    get_profile,
    list_profiles,
    save_profile,
)


def _connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def test_profiles_start_empty_and_are_filtered_by_module_and_subtype():
    connection = _connection()

    assert list_profiles(connection) == []
    save_profile(connection, "forge", "trials", "Trials real", {"trial_mode": "Trials"})
    save_profile(connection, "logistica", "por_tandas", "Tandas real", {"mode": "por_tandas"})

    assert [item["name"] for item in list_profiles(connection, "forge", "trials")] == ["Trials real"]
    assert list_profiles(connection, "forge", "normal") == []


def test_profile_round_trip_does_not_create_queue_steps():
    connection = _connection()
    ensure_workflow_queue_schema(connection)

    saved = save_profile(connection, "forge", "normal", "Forge normal real", {"copies": 2, "fx_enabled": {"mirror": False}})
    loaded = get_profile(connection, saved["profile_id"])

    assert loaded["module_type"] == "forge"
    assert loaded["subtype"] == "normal"
    assert loaded["recipe"]["fx_enabled"] == {"mirror": False}
    assert connection.execute("select count(*) from workflow_job_queue_steps").fetchone()[0] == 0


def test_profile_names_are_unique_only_inside_the_same_module_and_subtype():
    connection = _connection()
    save_profile(connection, "forge", "normal", "Base", {"copies": 1})

    with pytest.raises(ValueError, match="ya existe"):
        save_profile(connection, "forge", "normal", "Base", {"copies": 2})

    other = save_profile(connection, "forge", "trials", "Base", {"copies": 2})
    assert other["subtype"] == "trials"


def test_delete_profile_removes_only_the_selected_profile():
    connection = _connection()
    first = save_profile(connection, "telegram", "send", "Cuenta A", {"account_names": ["a"]})
    second = save_profile(connection, "telegram", "send", "Cuenta B", {"account_names": ["b"]})

    deleted = delete_profile(connection, first["profile_id"])

    assert deleted["profile_id"] == first["profile_id"]
    assert [item["profile_id"] for item in list_profiles(connection)] == [second["profile_id"]]
