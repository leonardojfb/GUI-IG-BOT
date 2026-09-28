import json
from datetime import datetime

import database
import organizadortg
from calendar_manifest import append_scheduled_entries, build_entry, load_entries, manifest_path


def test_send_media_group_order_and_first_caption(tmp_path, monkeypatch):
    paths = []
    for index in range(3):
        path = tmp_path / f"image{index}.jpg"
        path.write_bytes(f"image-{index}".encode())
        paths.append(path)
    sent = []

    class Response:
        status_code = 200

        def json(self):
            return {"ok": True}

    def fake_post(url, data, files, timeout):
        sent.append((url, json.loads(data["media"]), [file[1][0] for file in files.items()]))
        return Response()

    monkeypatch.setattr(organizadortg.requests, "post", fake_post)
    ok, topic = organizadortg._send_album_to_topic(
        "-100", 42, "Caption", [{"source_path": str(path)} for path in paths],
    )
    assert ok and topic == 42
    assert [row["media"] for row in sent[0][1]] == ["attach://file0", "attach://file1", "attach://file2"]
    assert sent[0][1][0]["caption"] == "Caption"
    assert all("caption" not in row for row in sent[0][1][1:])


def test_album_is_one_publication_and_retry_only_sends_control(tmp_path, monkeypatch):
    db = database.DatabaseManager(str(tmp_path / "telegram-test.db"))
    try:
        db.add_category("promo")
        db.add_va("VA Manual")
        db.update_va_telegram_group("VA Manual", "-100123")
        db.add_virtual_account("manual_user", "promo")
        db.update_account("manual_user", assigned_va="VA Manual")
        files = []
        for index in range(2):
            path = tmp_path / f"photo{index}.png"
            path.write_bytes(f"photo-{index}".encode())
            files.append(path)
        entry = build_entry(
            username="manual_user", account_id=1, delivery_kind="normal", day=1, slot=1,
            tanda="PHOTOS", source_path=str(files[0]), telegram_filename=files[0].name,
            publication_target="instagram_post", caption="Carrusel", media_kind="image",
            scheduled_date="2030-01-02", scheduled_time="12:00", timezone="America/Buenos_Aires",
        )
        entry["media_items"] = [{"source_path": str(path), "telegram_filename": path.name, "order": index}
                                for index, path in enumerate(files)]
        append_scheduled_entries(manifest_path(tmp_path), [entry])

        state = {}
        album_calls = []
        control_calls = []
        monkeypatch.setattr(organizadortg, "base_dir", str(tmp_path))
        monkeypatch.setattr(organizadortg, "load_tanda_caption_pools", lambda: {})
        monkeypatch.setattr(organizadortg, "load_trial_caption_maps", lambda: {})
        monkeypatch.setattr(organizadortg, "load_normal_individual_caption_maps", lambda: {})
        monkeypatch.setattr(organizadortg, "load_airtable_config", lambda: object())
        monkeypatch.setattr(organizadortg, "fetch_published_video_hashes", lambda _config: set())
        monkeypatch.setattr(organizadortg, "load_json", lambda _path: state)
        monkeypatch.setattr(organizadortg, "save_json", lambda *_args: None)
        monkeypatch.setattr(organizadortg.time, "sleep", lambda _seconds: None)
        monkeypatch.setattr(organizadortg, "get_or_create_topic", lambda *_args, **_kwargs: 91)
        monkeypatch.setattr(organizadortg, "_send_album_to_topic",
                            lambda chat, topic, caption, items: (album_calls.append([item["source_path"] for item in items]) or True, topic))

        def fake_api(method, data, silent=False):
            if method == "sendMessage" and data.get("reply_markup"):
                control_calls.append(data)
                return {"ok": len(control_calls) > 1}
            return {"ok": True}

        monkeypatch.setattr(organizadortg, "call_tg", fake_api)
        first = organizadortg.execute_telegram_plan(
            datetime(2030, 1, 2), selected_accounts=["manual_user"], db_manager=db,
        )
        assert "Se enviaron 0 publicaciones" in first
        assert load_entries(manifest_path(tmp_path), require_source=False)[0]["manual_status"] == "media_sent_telegram"
        second = organizadortg.execute_telegram_plan(
            datetime(2030, 1, 2), selected_accounts=["manual_user"], db_manager=db,
        )
        assert "Se enviaron 1 publicaciones" in second
        assert len(album_calls) == 1
        assert len(control_calls) == 2
        assert len(json.loads(control_calls[-1]["reply_markup"])["inline_keyboard"]) == 1
        assert load_entries(manifest_path(tmp_path), require_source=False)[0]["manual_status"] == "sent_telegram"
    finally:
        db.close()
