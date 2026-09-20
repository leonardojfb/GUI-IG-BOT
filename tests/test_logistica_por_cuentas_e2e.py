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
            with open(os.path.join(tanda_dir, f"PC_SRC__SRC{i:02d}__P2.mp4"), "wb") as fh:
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
        for username in ("pc_mix_a", "pc_mix_b"):
            app.db.add_virtual_account(username, "PC_MIX_CAT")
            app.db.update_account(username, assigned_va="PC_MIX_VA")

        for tanda_name in ("PC_MIX_ONE", "PC_MIX_TWO"):
            tanda_dir = os.path.join(base_dir, "videos_finales", tanda_name)
            os.makedirs(tanda_dir, exist_ok=True)
            for i in range(1, 3):
                with open(os.path.join(tanda_dir, f"{tanda_name}__SRC{i:02d}__P2.mp4"), "wb") as fh:
                    fh.write(f"fake-video-{tanda_name}-{i}".encode())
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
        assert sum(1 for row in produced if row["username"] == "pc_mix_a") == 2
        assert sum(1 for row in produced if row["username"] == "pc_mix_b") == 2
    finally:
        cleanup()


def test_por_cuentas_rejects_same_origin_across_accounts_on_same_day(tmp_path, monkeypatch):
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

        app.db.add_category("PC_DAILY_CAT")
        app.db.add_va("PC_DAILY_VA")
        for username in ("pc_daily_a", "pc_daily_b"):
            app.db.add_virtual_account(username, "PC_DAILY_CAT")
            app.db.update_account(username, assigned_va="PC_DAILY_VA")

        tanda_name = "PC_DAILY_ORIGIN"
        tanda_dir = os.path.join(base_dir, "videos_finales", tanda_name)
        os.makedirs(tanda_dir, exist_ok=True)
        for copy_number in (1, 2):
            with open(
                os.path.join(tanda_dir, f"PC_DAILY__ORIGIN_A__P2__c{copy_number:02d}.mp4"),
                "wb",
            ) as fh:
                fh.write(f"same-origin-copy-{copy_number}".encode())
        app.db.add_tanda(tanda_name, tanda_name, tanda_name, "")

        app.reload_dist_lists()
        app.acct_dist_tanda.set(tanda_name)
        app.acct_dist_list.delete("1.0", "end")
        app.acct_dist_list.insert("end", "pc_daily_a\npc_daily_b\n")
        app.acct_dist_vpd.set(1)
        app.acct_dist_period.set("MAX")

        app._acct_dist_run(preview_only=False)

        result_text = app.acct_dist_result.get("1.0", "end")
        assert "Sin candidatos" in result_text
        assert not (Path(base_dir) / "calendar_manifest.json").exists()
    finally:
        cleanup()
