from captions.importer import preview_txt
from captions.service import CaptionService, MissingCaptionError
from database import DatabaseManager


def test_preview_txt_parses_paragraph_captions_with_original_text(tmp_path):
    txt = tmp_path / "captions.txt"
    txt.write_text(
        "Hook uno\n\n"
        "Body uno\n\n"
        "#uno #dos\n\n"
        "Caption dos\n#tres\n",
        encoding="utf-8",
    )

    preview = preview_txt(str(txt))

    assert preview.source_path == str(txt)
    assert preview.original_text.startswith("Hook uno")
    assert preview.captions == [
        "Hook uno\n\nBody uno\n\n#uno #dos",
        "Caption dos\n#tres",
    ]


def test_editing_caption_creates_new_version_without_mutating_snapshot(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    service = CaptionService(db)
    pool = service.create_pool("normal", "T1", "T1 general")
    first = service.create_version(pool.pool_id, "Caption v1", source_ref="manual")
    snapshot = service.snapshot(first.caption_id, mode="general", source_id="T1")

    second = service.create_version(first.caption_id, "Caption v2", source_ref="editor")

    assert first.caption_id == second.caption_id
    assert first.version == 1
    assert second.version == 2
    assert snapshot.caption_version == 1
    assert snapshot.text == "Caption v1"
    assert service.snapshot(first.caption_id, version=2, mode="general", source_id="T1").text == "Caption v2"
    db.close()


def test_individual_resolution_blocks_missing_caption_unless_fallback_is_explicit(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    service = CaptionService(db)
    general_pool = service.create_pool("normal", "T1", "T1 general")
    service.import_txt(general_pool.pool_id, ["General caption"], source_ref="captions.txt")

    try:
        service.resolve_individual("asset-1", strategy="manual")
    except MissingCaptionError as exc:
        assert exc.asset_id == "asset-1"
        assert exc.fallback_available is False
    else:
        raise AssertionError("resolve_individual should block without an explicit fallback")

    fallback = service.resolve_individual(
        "asset-1",
        strategy="manual",
        allow_general_fallback=True,
        fallback_pool_id=general_pool.pool_id,
    )

    assert fallback.resolution_mode == "general_fallback"
    assert fallback.resolution_source_id == general_pool.pool_id
    assert fallback.text == "General caption"
    db.close()


def test_legacy_caption_migration_is_idempotent_and_records_mapping(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    txt = tmp_path / "captions.txt"
    txt.write_text("General uno\n#uno\n\nGeneral dos\n#dos\n", encoding="utf-8")
    db.add_tanda("T1", "p1", "p2", str(txt))
    db.set_normal_source_caption("T1", "source-a", "Individual A")
    db.set_tanda_trial("T1", True)
    db.set_trial_source_caption("T1", "trial-a", "Trial A")

    service = CaptionService(db)
    first = service.migrate_legacy_captions()
    second = service.migrate_legacy_captions()

    assert first["general_imported"] == 2
    assert first["normal_individual_imported"] == 1
    assert first["trial_individual_imported"] == 1
    assert second["general_imported"] == 0
    assert second["normal_individual_imported"] == 0
    assert second["trial_individual_imported"] == 0

    mappings = service.get_migration_mappings("T1")
    assert {(row["legacy_kind"], row["source_key"], row["status"]) for row in mappings} == {
        ("general_txt", "", "imported"),
        ("normal_individual", "source-a", "imported"),
        ("trial_individual", "trial-a", "imported"),
    }
    db.close()
