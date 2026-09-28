"""Functional coverage for Logistica's third distribution mode: 'Por Cuentas'.

Organizador.distribute_tanda() (the 'Por Tandas' tab) is exercised end-to-end by
tests/smoke_e2e_pipeline.py. It is NOT the only live distribution path: gui_premium_v7.py's
_acct_dist_run() ('Por Cuentas' tab, EJECUTAR POR CUENTAS button) is a second, fully
independent implementation with its own account selection (manual, cross-category),
its own videos/day x period model, and its own anti-collision key (Forge-style vid_id,
stripping a trailing __cNN). Before this test the only coverage for that code path was
tests/test_logistica_caption_ui.py, which just greps the method source for a string --
it never actually ran the algorithm. This test drives the real bound method (same
pattern as tests/test_dashboard_refresh.py) so the file counts, tanda tag, and caption
routing get checked against real output instead of a string match.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

ctk = pytest.importorskip("customtkinter")

import database


class _SyncWorkerThread:
    """Runs WorkerThread's task/callback pair synchronously, in-thread.

    The real WorkerThread runs task() on a background OS thread and reports
    back via self.root.after(0, ...). Tk's after() rejects registration from
    a non-main thread unless a real mainloop is pumping (RuntimeError: main
    thread is not in main loop) -- this harness never runs one. Swapping in
    this synchronous stand-in exercises the exact same production task()
    closure (the real distribution algorithm) without the cross-thread Tk call.
    """

    def __init__(self, root, callback, task, *args, **kwargs):
        self.callback = callback
        self.task = task
        self.args = args
        self.kwargs = kwargs

    def start(self):
        try:
            result = self.task(*self.args, **self.kwargs)
        except Exception as exc:
            if self.callback:
                self.callback(False, str(exc))
            return
        if self.callback:
            self.callback(True, result)


def _make_app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    original_db_path = database.DB_PATH
    database.DB_PATH = path

    import gui_premium_v7 as gui

    try:
        app = gui.InstagramAutoPro()
    except Exception:
        database.DB_PATH = original_db_path
        if os.path.exists(path):
            os.remove(path)
        pytest.skip("no display available")

    app.withdraw()

    def _cleanup():
        app.db.conn.close()
        # gui_premium_v7 imports organizadortg, which opens its own module-level
        # DatabaseManager against database.DB_PATH at import time -- a second
        # handle on the same temp file that Windows will keep locked unless
        # it's closed too.
        try:
            import organizadortg

            organizadortg.db.conn.close()
        except Exception:
            pass
        app.destroy()
        database.DB_PATH = original_db_path
        try:
            import organizadortg

            organizadortg.db = database.DatabaseManager()
        except Exception:
            pass
        if os.path.exists(path):
            os.remove(path)

    return app, _cleanup


def test_por_cuentas_distributes_manual_cross_category_accounts_without_mixing(tmp_path, monkeypatch):
    app, cleanup = _make_app()
    try:
        import Organizador
        import gui_premium_v7 as gui

        base_dir = str(tmp_path)
        monkeypatch.setattr(Organizador, "output_root", os.path.join(base_dir, "CALENDARIO_POSTEO"))
        monkeypatch.setattr(gui, "_BASE_DIR", base_dir)
        monkeypatch.setattr(gui, "_ACCT_HIST_FILE", os.path.join(base_dir, "acct_hist.json"))
        monkeypatch.setattr(gui, "WorkerThread", _SyncWorkerThread)
        # _SyncWorkerThread runs done() synchronously (see its docstring), which
        # calls messagebox.showinfo(...) on success. A real modal dialog with no
        # mainloop pumping events would block forever waiting for a click that
        # can never come, so these are no-ops for the duration of the test.
        monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "showerror", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "showwarning", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "askyesno", lambda *a, **k: True)

        app.db.add_category("PC_CAT_X")
        app.db.add_category("PC_CAT_Y")
        app.db.add_va("PC_VA_X")
        app.db.add_va("PC_VA_Y")
        app.db.add_virtual_account("pc_acc_x", "PC_CAT_X")
        app.db.update_account("pc_acc_x", assigned_va="PC_VA_X")
        app.db.add_virtual_account("pc_acc_y", "PC_CAT_Y")
        app.db.update_account("pc_acc_y", assigned_va="PC_VA_Y")

        tanda_name = "PC_SRC"
        tanda_dir = os.path.join(base_dir, "videos_finales", tanda_name)
        os.makedirs(tanda_dir, exist_ok=True)
        needed = 2 * 1 * 7  # 2 accounts x 1 video/day x "1 semana"
        for i in range(1, needed + 1):
            with open(os.path.join(tanda_dir, f"PC_SRC__c{i:02d}.mp4"), "wb") as fh:
                fh.write(f"fake-video-{i}".encode())
        app.db.add_tanda(tanda_name, tanda_name, tanda_name, "")

        caption_path = os.path.join(base_dir, "CAP_PC.txt")
        with open(caption_path, "w", encoding="utf-8") as fh:
            fh.write("CAPTION_PC_UNIQUE\nSecond line\n#pc_one #pc_two\n")
        app.db.set_tanda_captions(tanda_name, caption_path)

        app.reload_dist_lists()
        app.acct_dist_tanda.set(tanda_name)
        app.acct_dist_list.delete("1.0", "end")
        app.acct_dist_list.insert("end", "pc_acc_x\npc_acc_y\n")
        app.acct_dist_vpd.set(1)
        app.acct_dist_period.set("1 semana")

        app._acct_dist_run(preview_only=False)

        result_text = app.acct_dist_result.get("1.0", "end")
        assert "❌" not in result_text, f"Por Cuentas run reported an error: {result_text}"

        manifest_path = Path(base_dir) / "calendar_manifest.json"
        assert manifest_path.exists()
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        produced = [
            row for row in payload["entries"]
            if row["delivery_kind"] == "normal" and row["username"] in {"pc_acc_x", "pc_acc_y"}
        ]

        assert len(produced) == needed, (
            f"expected {needed} manifest entries (2 accounts x 7 days x 1/day), got {len(produced)}"
        )

        accounts_seen = {row["username"] for row in produced}
        assert accounts_seen == {"pc_acc_x", "pc_acc_y"}, (
            f"Por Cuentas must only write to the manually selected accounts, got {accounts_seen}"
        )

        for row in produced:
            source = Path(row["source_path"])
            assert source.exists()
            assert "videos_finales" in source.parts
            assert row["telegram_filename"].endswith(".mp4")
            fname = row["telegram_filename"]
            assert f"__TANDA_{tanda_name}__" in fname, (
                f"calendar filename lost its tanda tag: {fname}"
            )
        assert not any((Path(base_dir) / "CALENDARIO_POSTEO").rglob("*.mp4"))

        import organizadortg

        pools = organizadortg.load_tanda_caption_pools(app.db.get_all_tandas())
        caption_indexes = {}
        for row in produced:
            fname = row["telegram_filename"]
            caption = organizadortg.caption_for_calendar_video(fname, pools, caption_indexes)
            assert caption is not None and "CAPTION_PC_UNIQUE" in caption, (
                f"Por Cuentas file did not receive its own tanda's caption: {fname} -> {caption}"
            )
    finally:
        cleanup()


def test_por_cuentas_max_period_uses_all_complete_account_rounds(tmp_path, monkeypatch):
    app, cleanup = _make_app()
    try:
        import Organizador
        import gui_premium_v7 as gui

        base_dir = str(tmp_path)
        monkeypatch.setattr(Organizador, "output_root", os.path.join(base_dir, "CALENDARIO_POSTEO"))
        monkeypatch.setattr(gui, "_BASE_DIR", base_dir)
        monkeypatch.setattr(gui, "_ACCT_HIST_FILE", os.path.join(base_dir, "acct_hist.json"))
        monkeypatch.setattr(gui, "WorkerThread", _SyncWorkerThread)
        monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "showerror", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "showwarning", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "askyesno", lambda *a, **k: True)

        app.db.add_category("PC_MAX_CAT")
        app.db.add_va("PC_MAX_VA")
        app.db.add_virtual_account("pc_max_a", "PC_MAX_CAT")
        app.db.update_account("pc_max_a", assigned_va="PC_MAX_VA")
        app.db.add_virtual_account("pc_max_b", "PC_MAX_CAT")
        app.db.update_account("pc_max_b", assigned_va="PC_MAX_VA")

        tanda_name = "PC_MAX_SRC"
        tanda_dir = os.path.join(base_dir, "videos_finales", tanda_name)
        os.makedirs(tanda_dir, exist_ok=True)
        for i in range(1, 11):
            with open(os.path.join(tanda_dir, f"PC_MAX__SRC{i:02d}__P2.mp4"), "wb") as fh:
                fh.write(f"fake-video-{i}".encode())
        app.db.add_tanda(tanda_name, tanda_name, tanda_name, "")

        app.reload_dist_lists()
        assert "MAX" in app.acct_dist_period.cget("values")
        app.acct_dist_tanda.set(tanda_name)
        app.acct_dist_list.delete("1.0", "end")
        app.acct_dist_list.insert("end", "pc_max_a\npc_max_b\n")
        app.acct_dist_vpd.set(3)
        app.acct_dist_period.set("MAX")

        app._acct_dist_run(preview_only=False)

        result_text = app.acct_dist_result.get("1.0", "end")
        assert "Error" not in result_text, result_text
        assert "MAX" in result_text
        assert "Dia_1" in result_text and "Dia_2" in result_text

        manifest_path = Path(base_dir) / "calendar_manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        produced = [
            row for row in payload["entries"]
            if row["delivery_kind"] == "normal" and row["username"] in {"pc_max_a", "pc_max_b"}
        ]

        assert len(produced) == 10
        assert {row["username"] for row in produced} == {"pc_max_a", "pc_max_b"}
        assert {row["day"] for row in produced} == {1, 2}
        assert sum(1 for row in produced if row["username"] == "pc_max_a") == 5
        assert sum(1 for row in produced if row["username"] == "pc_max_b") == 5
        for username in {"pc_max_a", "pc_max_b"}:
            assert sum(1 for row in produced if row["username"] == username and row["day"] == 1) == 3
            assert sum(1 for row in produced if row["username"] == username and row["day"] == 2) == 2
    finally:
        cleanup()


def test_por_cuentas_can_shuffle_two_source_tandas_into_one_account_batch(tmp_path, monkeypatch):
    app, cleanup = _make_app()
    try:
        import Organizador
        import gui_premium_v7 as gui

        base_dir = str(tmp_path)
        monkeypatch.setattr(Organizador, "output_root", os.path.join(base_dir, "CALENDARIO_POSTEO"))
        monkeypatch.setattr(gui, "_BASE_DIR", base_dir)
        monkeypatch.setattr(gui, "_ACCT_HIST_FILE", os.path.join(base_dir, "acct_hist.json"))
        monkeypatch.setattr(gui, "WorkerThread", _SyncWorkerThread)
        monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "showerror", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "showwarning", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "askyesno", lambda *a, **k: True)

        app.db.add_category("PC_MIX_CAT")
        app.db.add_va("PC_MIX_VA")
        app.db.add_virtual_account("pc_mix_a", "PC_MIX_CAT")
        app.db.update_account("pc_mix_a", assigned_va="PC_MIX_VA")
        app.db.add_virtual_account("pc_mix_b", "PC_MIX_CAT")
        app.db.update_account("pc_mix_b", assigned_va="PC_MIX_VA")

        for tanda_name in ("PC_MIX_ONE", "PC_MIX_TWO"):
            tanda_dir = os.path.join(base_dir, "videos_finales", tanda_name)
            os.makedirs(tanda_dir, exist_ok=True)
            for index in range(1, 3):
                with open(os.path.join(tanda_dir, f"{tanda_name}__SRC{index:02d}__P2.mp4"), "wb") as fh:
                    fh.write(f"{tanda_name}-{index}".encode())
            app.db.add_tanda(tanda_name, tanda_name, tanda_name, "")

        app.reload_dist_lists()
        app.acct_dist_tanda.set("PC_MIX_ONE")
        app.acct_dist_tanda_2.set("PC_MIX_TWO")
        app.acct_dist_caption_mode_1.set("Individual")
        app.acct_dist_caption_mode_2.set("General")
        for source_key in ("SRC01", "SRC02"):
            app.db.set_normal_source_caption("PC_MIX_ONE", source_key, f"caption {source_key}")
        general_caption_path = os.path.join(base_dir, "PC_MIX_TWO_CAPTIONS.txt")
        with open(general_caption_path, "w", encoding="utf-8") as fh:
            fh.write("general caption two\n#mix\n")
        app.db.set_tanda_captions("PC_MIX_TWO", general_caption_path)
        app.acct_dist_list.delete("1.0", "end")
        app.acct_dist_list.insert("end", "pc_mix_a\npc_mix_b\n")
        app.acct_dist_vpd.set(1)
        app.acct_dist_period.set("MAX")

        app._acct_dist_run(preview_only=False)

        result_text = app.acct_dist_result.get("1.0", "end")
        assert "Error" not in result_text, result_text
        assert "PC_MIX_ONE + PC_MIX_TWO" in result_text

        payload = json.loads((Path(base_dir) / "calendar_manifest.json").read_text(encoding="utf-8"))
        produced = [
            row for row in payload["entries"]
            if row["delivery_kind"] == "normal" and row["username"] in {"pc_mix_a", "pc_mix_b"}
        ]

        assert len(produced) == 4
        assert {row["tanda"] for row in produced} == {"PC_MIX_ONE", "PC_MIX_TWO"}
        assert {
            row["caption_mode"] for row in produced if row["tanda"] == "PC_MIX_ONE"
        } == {"individual"}
        assert {
            row["caption_mode"] for row in produced if row["tanda"] == "PC_MIX_TWO"
        } == {"general"}
        assert {
            Path(row["source_path"]).parent.name for row in produced
        } == {"PC_MIX_ONE", "PC_MIX_TWO"}
        assert all(f"__TANDA_{row['tanda']}__" in row["telegram_filename"] for row in produced)
        for username in {"pc_mix_a", "pc_mix_b"}:
            assert sum(1 for row in produced if row["username"] == username) == 2
    finally:
        cleanup()


def test_por_cuentas_mixed_caption_modes_send_both_tandas_to_each_account(tmp_path, monkeypatch):
    app, cleanup = _make_app()
    try:
        import Organizador
        import gui_premium_v7 as gui
        import organizadortg

        base_dir = str(tmp_path)
        monkeypatch.setattr(Organizador, "output_root", os.path.join(base_dir, "CALENDARIO_POSTEO"))
        monkeypatch.setattr(gui, "_BASE_DIR", base_dir)
        monkeypatch.setattr(gui, "_ACCT_HIST_FILE", os.path.join(base_dir, "acct_hist.json"))
        monkeypatch.setattr(gui, "WorkerThread", _SyncWorkerThread)
        monkeypatch.setattr(gui.random, "shuffle", lambda _items: None)
        monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "showerror", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "showwarning", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "askyesno", lambda *a, **k: True)

        app.db.add_category("PC_MODE_CAT")
        app.db.add_va("PC_MODE_VA")
        usernames = [f"pc_mode_{index:02d}" for index in range(1, 11)]
        for username in usernames:
            app.db.add_virtual_account(username, "PC_MODE_CAT")
            app.db.update_account(username, assigned_va="PC_MODE_VA")

        for tanda_name, source_prefix in (
            ("PC_MODE_INDIVIDUAL", "I"),
            ("PC_MODE_GENERAL", "G"),
        ):
            tanda_dir = os.path.join(base_dir, "videos_finales", tanda_name)
            os.makedirs(tanda_dir, exist_ok=True)
            for index in range(1, 11):
                with open(os.path.join(tanda_dir, f"{tanda_name}__{source_prefix}{index:02d}__P2.mp4"), "wb") as fh:
                    fh.write(f"{tanda_name}-{index}".encode())
            app.db.add_tanda(tanda_name, tanda_name, tanda_name, "")

        for source_key in (f"I{index:02d}" for index in range(1, 11)):
            app.db.set_normal_source_caption("PC_MODE_INDIVIDUAL", source_key, f"individual {source_key}")
        general_caption_path = os.path.join(base_dir, "PC_MODE_GENERAL_CAPTIONS.txt")
        with open(general_caption_path, "w", encoding="utf-8") as fh:
            fh.write("general caption\n#general\n")
        app.db.set_tanda_captions("PC_MODE_GENERAL", general_caption_path)

        app.reload_dist_lists()
        app.acct_dist_tanda.set("PC_MODE_INDIVIDUAL")
        app.acct_dist_tanda_2.set("PC_MODE_GENERAL")
        app.acct_dist_caption_mode_1.set("Individual")
        app.acct_dist_caption_mode_2.set("General")
        app.acct_dist_list.delete("1.0", "end")
        app.acct_dist_list.insert("end", "\n".join(usernames) + "\n")
        app.acct_dist_vpd.set(2)
        app.acct_dist_period.set("MAX")

        app._acct_dist_run(preview_only=False)

        result_text = app.acct_dist_result.get("1.0", "end")
        assert "Error" not in result_text, result_text

        payload = json.loads((Path(base_dir) / "calendar_manifest.json").read_text(encoding="utf-8"))
        produced = [
            row for row in payload["entries"]
            if row["delivery_kind"] == "normal" and row["username"] in set(usernames)
        ]

        assert len(produced) == 20
        pools = organizadortg.load_tanda_caption_pools(app.db.get_all_tandas())
        caption_indexes = {}
        for username in usernames:
            rows = [row for row in produced if row["username"] == username]
            assert len(rows) == 2
            assert {row["tanda"] for row in rows} == {"PC_MODE_INDIVIDUAL", "PC_MODE_GENERAL"}
            assert {
                row["caption_mode"] for row in rows if row["tanda"] == "PC_MODE_INDIVIDUAL"
            } == {"individual"}
            assert {
                row["caption_mode"] for row in rows if row["tanda"] == "PC_MODE_GENERAL"
            } == {"general"}
            for row in rows:
                normal_map = app.db.get_normal_source_captions(row["tanda"])
                caption = organizadortg.caption_for_normal_calendar_video(
                    row["telegram_filename"],
                    row["caption_mode"],
                    normal_map,
                    pools,
                    caption_indexes,
                )
                if row["caption_mode"] == "individual":
                    assert caption and caption.startswith("individual ")
                else:
                    assert caption and caption.startswith("general caption")
    finally:
        cleanup()


def test_calendar_view_orders_mixed_posts_and_shows_story_link_and_image(tmp_path, monkeypatch):
    app, cleanup = _make_app()
    try:
        import gui_premium_v7 as gui
        from calendar_manifest import append_scheduled_entries, build_entry, manifest_path
        from PIL import Image

        base_dir = str(tmp_path)
        monkeypatch.setattr(gui, "_BASE_DIR", base_dir)
        app.db.add_category("CAL_VIEW_CAT")
        app.db.add_virtual_account("calendar_view_user", "CAL_VIEW_CAT")

        story_path = tmp_path / "story.png"
        Image.new("RGB", (24, 32), (25, 140, 90)).save(story_path)
        reel_path = tmp_path / "reel.mp4"
        reel_path.write_bytes(b"fake video")
        marketplace_path = tmp_path / "listing.jpg"
        Image.new("RGB", (32, 24), (140, 90, 25)).save(marketplace_path)

        common = {
            "username": "calendar_view_user",
            "account_id": None,
            "delivery_kind": "normal",
            "day": 1,
            "tanda": "CAL_VIEW",
        }
        entries = [
            build_entry(
                **common,
                slot=1,
                source_path=str(reel_path),
                telegram_filename="reel.mp4",
                publication_target="instagram_reel",
                scheduled_date="2030-01-02",
                scheduled_time="10:00",
                timezone="America/Argentina/Buenos_Aires",
                media_kind="video",
            ),
            build_entry(
                **common,
                slot=2,
                source_path=str(story_path),
                telegram_filename="story.png",
                publication_target="instagram_story",
                story_link_url="https://links.example/calendar_view_user",
                story_announcement_text="Visita el enlace",
                scheduled_date="2030-01-02",
                scheduled_time="12:00",
                timezone="America/Argentina/Buenos_Aires",
                media_kind="image",
            ),
            build_entry(
                **common,
                slot=3,
                source_path=str(marketplace_path),
                telegram_filename="listing.jpg",
                publication_target="facebook_marketplace_listing",
                scheduled_date="2030-01-02",
                scheduled_time="13:00",
                timezone="America/Argentina/Buenos_Aires",
                media_kind="image",
            ),
        ]
        append_scheduled_entries(manifest_path(base_dir), entries)

        app.calendar_start.delete(0, "end")
        app.calendar_start.insert(0, "2030-01-02")
        app.calendar_days.delete(0, "end")
        app.calendar_days.insert(0, "5")
        app.calendar_account.set("Todas")
        app._refresh_calendar_view()

        rows = [app.calendar_tree.item(iid, "values") for iid in app.calendar_tree.get_children()]
        assert [row[1] for row in rows] == ["10:00", "12:00", "13:00"]
        assert [row[3] for row in rows] == [
            "instagram_reel", "instagram_story", "facebook_marketplace_listing",
        ]

        app.calendar_tree.selection_set("1")
        app._show_calendar_entry()
        detail = app.calendar_detail.get("1.0", "end")
        assert "https://links.example/calendar_view_user" in detail
        assert "Visita el enlace" in detail
        assert app.calendar_image_ref is not None

        app.calendar_account.set("calendar_view_user")
        app._refresh_calendar_view()
        assert len(app.calendar_tree.get_children()) == 3
    finally:
        cleanup()


def test_photo_forge_gui_generates_neutral_batch(tmp_path, monkeypatch):
    app, cleanup = _make_app()
    try:
        import gui_premium_v7 as gui
        import photo_forge
        from PIL import Image, ImageDraw

        base_dir = str(tmp_path)
        output_root = tmp_path / "photo_outputs"
        monkeypatch.setattr(gui, "_BASE_DIR", base_dir)
        monkeypatch.setattr(gui, "WorkerThread", _SyncWorkerThread)
        monkeypatch.setattr(gui.messagebox, "askyesno", lambda *args, **kwargs: True)
        monkeypatch.setattr(gui.messagebox, "showinfo", lambda *args, **kwargs: None)
        monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kwargs: pytest.fail(str(args)))

        source = tmp_path / "source.png"
        image = Image.new("RGB", (180, 320), (30, 90, 150))
        draw = ImageDraw.Draw(image)
        for y in range(image.height):
            draw.line((0, y, image.width, y), fill=(y % 255, (y * 3) % 255, (y * 7) % 255))
        draw.rectangle((18, 42, 159, 278), outline=(250, 240, 20), width=5)
        image.save(source)
        source_bytes = source.read_bytes()
        app.photo_forge_sources.insert("end", str(source))
        app.photo_forge_sources.selection_set(0)

        app.photo_forge_batch.delete(0, "end")
        app.photo_forge_batch.insert(0, "GUI_PHOTO_BATCH")
        app.photo_forge_output.delete(0, "end")
        app.photo_forge_output.insert(0, str(output_root))
        app.photo_forge_profile.set("Post 4:5")
        app.photo_forge_variant_count.delete(0, "end")
        app.photo_forge_variant_count.insert(0, "2")
        app.photo_forge_strength.set("Estándar")
        assert "photo_forge_accounts" not in app.__dict__
        assert "photo_forge_variant_selection" not in app.__dict__

        app._photo_forge_run()

        batch_dir = output_root / "GUI_PHOTO_BATCH"
        manifest_path = batch_dir / photo_forge.MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        outputs = photo_forge.validated_neutral_outputs(batch_dir)
        assert len(outputs) == 2
        assert source.read_bytes() == source_bytes
        assert manifest["version"] == 3
        assert len(manifest["entries"]) == 2
        assert all("username" not in row for row in manifest["entries"])
        assert all(Path(row["output_path"]).parent == batch_dir for row in manifest["entries"])
        for output in outputs:
            with Image.open(output["output_path"]) as rendered:
                assert abs(rendered.width / rendered.height - (4 / 5)) < 0.01
        assert "2 relaciones registradas" in app.photo_forge_result.get("1.0", "end")
        assert not (tmp_path / "CALENDARIO_POSTEO").exists()
    finally:
        cleanup()


def test_photo_forge_preview_only_requires_source_images(tmp_path, monkeypatch):
    app, cleanup = _make_app()
    try:
        import gui_premium_v7 as gui

        from PIL import Image

        source = tmp_path / "selected.png"
        Image.new("RGB", (40, 50), "red").save(source)
        app.photo_forge_sources.insert("end", str(source))
        preview_calls = []
        warnings = []
        app._photo_forge_show_preview = lambda: preview_calls.append(True)
        monkeypatch.setattr(
            gui.messagebox, "showwarning",
            lambda title, text, **_kwargs: warnings.append((title, text)),
        )

        app._photo_forge_preview()

        assert preview_calls == [True]
        assert warnings == []
        assert "Imágenes: 1 · Finales totales: 3" in app.photo_forge_result.get("1.0", "end")
    finally:
        cleanup()


def test_image_logistics_tab_uses_neutral_batch_and_category(tmp_path, monkeypatch):
    app, cleanup = _make_app()
    try:
        import gui_premium_v7 as gui
        import photo_forge
        from PIL import Image
        from calendar_manifest import load_entries, manifest_path

        monkeypatch.setattr(gui, "_BASE_DIR", str(tmp_path))
        monkeypatch.setattr(gui.messagebox, "showwarning", lambda *args, **kwargs: pytest.fail(str(args)))
        monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kwargs: pytest.fail(str(args)))
        source = tmp_path / "source.png"
        image = Image.new("RGB", (40, 50))
        image.putdata([((x * 5) % 256, (y * 7) % 256, (x + y) % 256)
                       for y in range(50) for x in range(40)])
        image.save(source)
        root = tmp_path / "imagenes_finales"
        plan = photo_forge.plan_neutral_photo_batch([source], root, "GUI_BATCH", finals_per_photo=2)
        photo_forge.create_neutral_photo_batch(plan, root, "GUI_BATCH")
        app.db.add_category("IMAGENES_CAT")
        app.db.add_virtual_account("image_a", "IMAGENES_CAT")
        app.db.add_virtual_account("image_b", "IMAGENES_CAT")

        app._image_refresh_inventory()
        app.image_category_combo.set("IMAGENES_CAT")
        app.image_inventory.selection_set(0)
        app._image_add_source()
        app.image_target.set("instagram_post")
        app._image_target_changed()
        app.image_start_date.delete(0, "end")
        app.image_start_date.insert(0, "2030-01-02")
        app.image_horizon.delete(0, "end")
        app.image_horizon.insert(0, "1")
        app._image_add_block()
        app.image_block_list.selection_set(0)
        app._image_load_block()
        app.image_caption.insert(0, "Caption editado")
        app._image_update_block()
        app._image_preview()
        assert "2 publicaciones" in app.image_result.get("1.0", "end")
        app._image_commit()

        rows = [row for row in load_entries(manifest_path(tmp_path))
                if row.get("photo_batch") == str(root / "GUI_BATCH")]
        assert len(rows) == 2
        assert {row["username"] for row in rows} == {"image_a", "image_b"}
        assert len({row["source_path"] for row in rows}) == 2
        assert {row["caption"] for row in rows} == {"Caption editado"}
        assert not (tmp_path / "CALENDARIO_POSTEO").exists()
        app.calendar_start.delete(0, "end")
        app.calendar_start.insert(0, "2030-01-02")
        app._refresh_calendar_view()
        assert len(app.calendar_tree.get_children()) == 2
        first = app.calendar_tree.get_children()[0]
        assert app.calendar_tree.item(first, "values")[5] == "1"
        app.calendar_tree.selection_set(first)
        app._show_calendar_entry()
        assert app.calendar_media_position.cget("text") == "1 / 1"
    finally:
        cleanup()
