from datetime import datetime

import database
import organizadortg
from calendar_manifest import append_scheduled_entries, build_entry, load_entries, manifest_path


def test_telegram_delivers_mixed_calendar_rows_in_time_order_and_updates_status(tmp_path, monkeypatch):
    db = database.DatabaseManager(str(tmp_path / "telegram-test.db"))
    try:
        db.add_category("promo")
        db.add_va("VA Manual")
        db.update_va_telegram_group("VA Manual", "-100123")
        db.add_virtual_account("manual_user", "promo")
        db.update_account("manual_user", assigned_va="VA Manual")

        video = tmp_path / "reel.mp4"
        video.write_bytes(b"fake-reel")
        story = tmp_path / "story.png"
        story.write_bytes(b"fake-story-image")
        marketplace = tmp_path / "marketplace.png"
        marketplace.write_bytes(b"fake-marketplace-image")
        common = {
            "username": "manual_user",
            "account_id": 1,
            "delivery_kind": "normal",
            "day": 1,
            "tanda": "MULTICANAL",
            "timezone": "America/Argentina/Buenos_Aires",
            "lane_id": "mixed-lane",
            "plan_id": "mixed-plan",
        }
        entries = [
            build_entry(
                **common,
                slot=1,
                source_path=str(video),
                telegram_filename="reel.mp4",
                publication_target="instagram_reel",
                caption="Caption Reel",
                scheduled_date="2030-01-02",
                scheduled_time="10:00",
                media_kind="video",
            ),
            build_entry(
                **common,
                slot=2,
                source_path=str(story),
                telegram_filename="story.png",
                publication_target="instagram_story",
                story_link_url="https://links.example/manual_user",
                story_announcement_text="Mira la historia",
                scheduled_date="2030-01-02",
                scheduled_time="12:00",
                media_kind="image",
            ),
            build_entry(
                **common,
                slot=3,
                source_path=str(marketplace),
                telegram_filename="marketplace.png",
                publication_target="facebook_marketplace_listing",
                platform_payload={"title": "Artículo", "price": "20"},
                scheduled_date="2030-01-02",
                scheduled_time="13:00",
                media_kind="image",
            ),
        ]
        append_scheduled_entries(manifest_path(tmp_path), entries)

        events = []
        topics_state = {}
        monkeypatch.setattr(organizadortg, "base_dir", str(tmp_path))
        monkeypatch.setattr(organizadortg, "load_tanda_caption_pools", lambda: {})
        monkeypatch.setattr(organizadortg, "load_trial_caption_maps", lambda: {})
        monkeypatch.setattr(organizadortg, "load_normal_individual_caption_maps", lambda: {})
        monkeypatch.setattr(organizadortg, "load_airtable_config", lambda: object())
        monkeypatch.setattr(organizadortg, "fetch_published_video_hashes", lambda _config: set())
        monkeypatch.setattr(organizadortg, "load_json", lambda _path: topics_state)
        monkeypatch.setattr(organizadortg, "save_json", lambda *_args: None)
        monkeypatch.setattr(organizadortg.time, "sleep", lambda _seconds: None)

        def fake_topic(_chat, username, _tag, _state, **_kwargs):
            events.append(("topic", username))
            return 91

        def fake_api(method, data, silent=False):
            if method == "sendMessage":
                events.append(("context", data["text"]))
            return {"ok": True}

        def fake_send(kind):
            def send(_chat, topic_id, caption, path, _state, username, _tag, *_args, **kwargs):
                events.append((
                    "media", kind, username, path, caption,
                    kwargs.get("story_link_url"), topic_id,
                ))
                return True, topic_id
            return send

        monkeypatch.setattr(organizadortg, "get_or_create_topic", fake_topic)
        monkeypatch.setattr(organizadortg, "call_tg", fake_api)
        monkeypatch.setattr(organizadortg, "_send_video_to_topic", fake_send("video"))
        monkeypatch.setattr(organizadortg, "_send_image_to_topic", fake_send("image"))

        result = organizadortg.execute_telegram_plan(
            datetime(2030, 1, 2), selected_accounts=["manual_user"], db_manager=db,
        )

        assert "Se enviaron 3 publicaciones" in result
        media_events = [event for event in events if event[0] == "media"]
        assert [(event[1], event[3]) for event in media_events] == [
            ("video", str(video)),
            ("image", str(story)),
            ("image", str(marketplace)),
        ]
        assert media_events[1][5] == "https://links.example/manual_user"
        context_events = [event[1] for event in events if event[0] == "context"]
        assert [item.split("\n")[1] for item in context_events] == [
            "Fecha: 2030-01-02", "Fecha: 2030-01-02", "Fecha: 2030-01-02",
        ]
        assert "Hora: 10:00 America/Argentina/Buenos_Aires" in context_events[0]
        assert "Hora: 12:00 America/Argentina/Buenos_Aires" in context_events[1]
        assert "Hora: 13:00 America/Argentina/Buenos_Aires" in context_events[2]
        assert "Enlace Story: https://links.example/manual_user" in context_events[1]
        assert "Titulo: Artículo" in context_events[2]
        saved = load_entries(manifest_path(tmp_path), require_source=False)
        assert {row["manual_status"] for row in saved} == {"sent_telegram"}
    finally:
        db.close()
