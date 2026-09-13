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
    db.set_tanda_trial("T1", True)
    db.conn.execute(
        """
        INSERT INTO normal_source_captions (tanda_name, source_key, caption_text)
        VALUES ('T1', 'source-a', 'Individual A')
        """
    )
    db.conn.execute(
        """
        INSERT INTO trial_source_captions (tanda_name, source_key, caption_text)
        VALUES ('T1', 'trial-a', 'Trial A')
        """
    )
    db.conn.commit()

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


def test_legacy_normal_caption_setter_writes_versioned_caption(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    db.add_tanda("T1", "p1", "p2", None)

    db.set_normal_source_caption("T1", "source-a", "Caption A v1")
    db.set_normal_source_caption("T1", "source-a", "Caption A v2")

    service = CaptionService(db)
    [mapping] = [
        row for row in service.get_migration_mappings("T1")
        if row["legacy_kind"] == "normal_individual" and row["source_key"] == "source-a"
    ]
    snapshot = service.snapshot(mapping["caption_id"], version=1)
    latest = service.snapshot(mapping["caption_id"])

    assert snapshot.text == "Caption A v1"
    assert latest.caption_version == 2
    assert latest.text == "Caption A v2"
    db.close()


def test_legacy_trial_caption_setter_writes_versioned_caption(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    db.add_tanda("T1", "p1", "p2", None)
    db.set_tanda_trial("T1", True)

    db.set_trial_source_caption("T1", "source-a", "Trial A v1")
    db.set_trial_source_caption("T1", "source-a", "Trial A v2")

    service = CaptionService(db)
    [mapping] = [
        row for row in service.get_migration_mappings("T1")
        if row["legacy_kind"] == "trial_individual" and row["source_key"] == "source-a"
    ]
    snapshot = service.snapshot(mapping["caption_id"], version=1)
    latest = service.snapshot(mapping["caption_id"])

    assert snapshot.text == "Trial A v1"
    assert latest.caption_version == 2
    assert latest.text == "Trial A v2"
    db.close()


def test_resolve_legacy_manifest_caption_freezes_general_and_individual(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    txt = tmp_path / "captions.txt"
    txt.write_text("General uno\n#uno\n\nGeneral dos\n#dos\n", encoding="utf-8")
    db.add_tanda("T1", "p1", "p2", str(txt))
    db.add_tanda("T2", "p1", "p2", None)
    db.set_normal_source_caption("T2", "source-a", "Individual A v1")

    service = CaptionService(db)
    service.migrate_legacy_captions()
    general = service.resolve_legacy_manifest_caption(
        tanda_name="T1",
        filename="any__TANDA_T1__ACC1__D1__S1.mp4",
        mode="general",
        pool_index=1,
    )
    individual = service.resolve_legacy_manifest_caption(
        tanda_name="T2",
        filename="source-a__c01__TANDA_T2__ACC1__D1__S1.mp4",
        mode="individual",
    )
    db.set_normal_source_caption("T2", "source-a", "Individual A v2")

    assert general.text == "General dos\n#dos"
    assert general.resolution_mode == "general"
    assert individual.text == "Individual A v1"
    assert individual.resolution_mode == "individual"
    assert service.snapshot(individual.caption_id).text == "Individual A v2"
    db.close()


def test_gui_caption_manifest_payload_uses_snapshot_contract(tmp_path):
    import gui_premium_v7

    db = DatabaseManager(str(tmp_path / "organizador.db"))
    db.add_tanda("T1", "p1", "p2", None)
    db.set_normal_source_caption("T1", "source-a", "Caption A")

    payload = gui_premium_v7._caption_snapshot_manifest_payload(
        db,
        tanda_name="T1",
        filename="source-a__c01.mp4",
        caption_mode="individual",
        delivery_kind="normal",
    )

    assert payload["caption"] == "Caption A"
    assert payload["caption_snapshot"]["caption_id"].startswith("caption-")
    assert payload["caption_snapshot"]["caption_version"] == 1
    assert payload["caption_snapshot"]["resolution_mode"] == "individual"
    assert "text" not in payload["caption_snapshot"]
    db.close()
