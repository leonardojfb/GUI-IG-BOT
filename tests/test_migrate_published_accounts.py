import pytest

from migrate_published_accounts import build_updates


def test_build_updates_derives_account_and_publication_key():
    source_hash = "a" * 64
    updates, unresolved = build_updates([{
        "id": "rec1",
        "fields": {
            "SHA-256": source_hash,
            "Archivo original": "clip__ACC149__D1__S1.mp4",
        },
    }])

    assert updates == [{
        "id": "rec1",
        "fields": {
            "Account ID": "149",
            "Publication key": "149:" + source_hash,
        },
    }]
    assert unresolved == []


def test_build_updates_is_idempotent_for_already_migrated_row():
    source_hash = "b" * 64
    updates, unresolved = build_updates([{
        "id": "rec2",
        "fields": {
            "SHA-256": source_hash,
            "Archivo original": "clip__ACC2__D1__S1.mp4",
            "Account ID": "2",
            "Publication key": "2:" + source_hash,
        },
    }])

    assert updates == []
    assert unresolved == []


def test_build_updates_reports_row_without_account_identity():
    updates, unresolved = build_updates([{
        "id": "legacy",
        "fields": {
            "SHA-256": "c" * 64,
            "Archivo original": "legacy.mp4",
        },
    }])

    assert updates == []
    assert unresolved == ["legacy"]


def test_build_updates_rejects_manifest_based_account_inference():
    source_hash = "d" * 64
    with pytest.raises(TypeError):
        build_updates([{
            "id": "rec3",
            "fields": {
                "SHA-256": source_hash,
                "Archivo original": "physical-copy.mov",
            },
        }], {source_hash: {"7"}})


def test_build_updates_preserves_persisted_account_on_conflict():
    source_hash = "f" * 64
    updates, unresolved = build_updates([{
        "id": "rec5",
        "fields": {
            "SHA-256": source_hash,
            "Archivo original": "clip__ACC7__D1__S1.mp4",
            "Account ID": "9",
            "Publication key": "9:" + source_hash,
        },
    }])

    assert updates == []
    assert unresolved == ["rec5"]


def test_build_updates_repairs_key_using_persisted_account_without_other_evidence():
    source_hash = "1" * 64
    updates, unresolved = build_updates([{
        "id": "rec6",
        "fields": {
            "SHA-256": source_hash,
            "Archivo original": "legacy.mp4",
            "Account ID": "9",
            "Publication key": "wrong",
        },
    }])

    assert updates == [{
        "id": "rec6",
        "fields": {"Publication key": "9:" + source_hash},
    }]
    assert unresolved == []
