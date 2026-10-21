from rollback_inferred_published_accounts import build_clears


def test_build_clears_only_fields_added_to_unchanged_record():
    source_hash = "a" * 64
    before = [{
        "id": "rec1",
        "fields": {"SHA-256": source_hash, "Archivo original": "clip.mov"},
    }]
    current = [{
        "id": "rec1",
        "fields": {
            "SHA-256": source_hash,
            "Archivo original": "clip.mov",
            "Account ID": "7",
            "Publication key": "7:" + source_hash,
        },
    }]

    clears, skipped = build_clears(before, current)

    assert clears == [{
        "id": "rec1",
        "fields": {"Account ID": None, "Publication key": None},
    }]
    assert skipped == []


def test_build_clears_preserves_record_changed_after_migration():
    source_hash = "b" * 64
    before = [{
        "id": "rec2",
        "fields": {"SHA-256": source_hash, "Message ID": "1"},
    }]
    current = [{
        "id": "rec2",
        "fields": {
            "SHA-256": source_hash,
            "Message ID": "2",
            "Account ID": "8",
            "Publication key": "8:" + source_hash,
        },
    }]

    clears, skipped = build_clears(before, current)

    assert clears == []
    assert skipped == ["rec2"]


def test_build_clears_does_not_remove_preexisting_account_scope():
    source_hash = "c" * 64
    fields = {
        "SHA-256": source_hash,
        "Account ID": "9",
        "Publication key": "9:" + source_hash,
    }

    clears, skipped = build_clears(
        [{"id": "rec3", "fields": fields}],
        [{"id": "rec3", "fields": fields}],
    )

    assert clears == []
    assert skipped == []
