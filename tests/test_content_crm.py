import pytest

from content_crm import build_reuse_request, evaluate_reuse, list_account_content, list_root_cards
from database import DatabaseManager


def seeded_crm_db(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    db.conn.executemany(
        "INSERT INTO virtual_accounts (username, account_type, trials_active) VALUES (?, ?, ?)",
        [
            ("wrong-kind", "promo", 0),
            ("scheduled-root", "promo", 1),
            ("sent-root", "promo", 1),
            ("same-output", "promo", 1),
            ("free", "promo", 1),
        ],
    )
    db.conn.commit()
    return db


def add_usable_output(db, tmp_path, root_id, name="usable.mp4"):
    output = tmp_path / name
    output.write_bytes(name.encode("ascii"))
    asset = db.upsert_vault_asset(output)
    db.add_asset_to_content_root(root_id, asset["id"], "tanda_output")
    return asset


def add_use(db, root_id, asset_id, account_id, username, state, key, day=1, slot=1):
    db.upsert_content_account_use(
        {
            "calendar_entry_key": key,
            "content_root_id": root_id,
            "vault_asset_id": asset_id,
            "account_id": account_id,
            "username": username,
            "delivery_kind": "normal",
            "tanda_name": "T1",
            "transform_log_id": None,
            "day": day,
            "slot": slot,
            "state": state,
        }
    )


def test_root_cards_keep_successful_delivery_history_without_metrics(tmp_path):
    db = seeded_crm_db(tmp_path)
    root = db.create_content_root("Night set")
    output = add_usable_output(db, tmp_path, root["id"])
    add_use(db, root["id"], output["id"], 2, "scheduled-root", "sent_telegram", "sent")
    add_use(db, root["id"], output["id"], 3, "sent-root", "failed", "failed")

    cards = list_root_cards(db)

    assert cards == [
        {
            "id": root["id"],
            "name": "Night set",
            "status": "active",
            "asset_count": 1,
            "usable_output_count": 1,
            "scheduled_count": 0,
            "sent_telegram_count": 1,
            "successful_use_count": 1,
            "last_successful_use_at": cards[0]["last_successful_use_at"],
        }
    ]
    assert cards[0]["last_successful_use_at"]
    assert not {"metrics", "score", "performance"} & set(cards[0])

    account_content = list_account_content(db, 2)
    assert account_content[0]["root_name"] == "Night set"
    assert account_content[0]["state"] == "sent_telegram"
    db.close()


def test_reuse_prioritizes_delivery_root_and_same_output_conflicts_in_caller_order(tmp_path):
    db = seeded_crm_db(tmp_path)
    root = db.create_content_root("Reusable")
    other_root = db.create_content_root("Other family")
    output = add_usable_output(db, tmp_path, root["id"])
    db.add_asset_to_content_root(other_root["id"], output["id"], "tanda_output")
    add_use(db, root["id"], output["id"], 2, "scheduled-root", "scheduled", "scheduled-root")
    add_use(db, root["id"], output["id"], 3, "sent-root", "sent_telegram", "sent-root")
    add_use(db, other_root["id"], output["id"], 4, "same-output", "scheduled", "same-output")

    decision = evaluate_reuse(db, root["id"], [5, 1, 2, 3, 4], delivery_kind="trial")

    assert decision["eligible"] == [{"account_id": 5, "username": "free"}]
    assert decision["excluded"] == [
        {"account_id": 1, "username": "wrong-kind", "reason": "wrong_delivery_kind"},
        {"account_id": 2, "username": "scheduled-root", "reason": "already_scheduled_root"},
        {"account_id": 3, "username": "sent-root", "reason": "already_sent_root"},
        {"account_id": 4, "username": "same-output", "reason": "same_asset_scheduled"},
    ]
    db.close()


def test_reuse_excludes_missing_usable_output_after_other_checks(tmp_path):
    db = seeded_crm_db(tmp_path)
    root = db.create_content_root("Missing output")
    output = add_usable_output(db, tmp_path, root["id"], "gone.mp4")
    output_path = output["source_path"]
    assert output_path
    (tmp_path / "gone.mp4").unlink()

    decision = evaluate_reuse(db, root["id"], [5], delivery_kind="normal")

    assert decision == {
        "eligible": [],
        "excluded": [{"account_id": 5, "username": "free", "reason": "missing_usable_output"}],
    }
    db.close()


def test_reuse_rejects_missing_or_archived_root(tmp_path):
    db = seeded_crm_db(tmp_path)
    archived = db.create_content_root("Archived")
    db.conn.execute("UPDATE content_roots SET status='archived' WHERE id=?", (archived["id"],))
    db.conn.commit()

    with pytest.raises(ValueError, match="familia seleccionada"):
        evaluate_reuse(db, archived["id"], [5])
    with pytest.raises(ValueError, match="familia seleccionada"):
        evaluate_reuse(db, 99999, [5])
    db.close()


def test_reuse_request_contains_only_eligible_accounts_and_real_output_assets(tmp_path):
    db = seeded_crm_db(tmp_path)
    root = db.create_content_root("Reusable request")
    output = add_usable_output(db, tmp_path, root["id"])
    add_use(db, root["id"], output["id"], 2, "scheduled-root", "scheduled", "already-scheduled")

    request = build_reuse_request(db, root["id"], [2, 5])

    assert request["root_id"] == root["id"]
    assert request["delivery_kind"] == "normal"
    assert request["eligible_account_ids"] == [5]
    assert request["asset_ids"] == [output["id"]]
    assert request["decision"] == {
        "eligible": [{"account_id": 5, "username": "free"}],
        "excluded": [{
            "account_id": 2,
            "username": "scheduled-root",
            "reason": "already_scheduled_root",
        }],
    }
    db.close()


def test_reuse_request_rejects_when_no_account_is_eligible(tmp_path):
    db = seeded_crm_db(tmp_path)
    root = db.create_content_root("No reuse")
    output = add_usable_output(db, tmp_path, root["id"])
    add_use(db, root["id"], output["id"], 5, "free", "scheduled", "already-scheduled")

    with pytest.raises(ValueError, match="^No hay cuentas elegibles para reutilizar esta familia\\.$"):
        build_reuse_request(db, root["id"], [5])
    db.close()
