import os
import tempfile

import pytest

ctk = pytest.importorskip("customtkinter")

import database


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
        app.destroy()
        database.DB_PATH = original_db_path
        if os.path.exists(path):
            os.remove(path)

    return app, _cleanup


def test_refresh_dashboard_never_schedules_a_background_timer():
    """Dashboard auto-refresh was removed entirely: the user refreshes via the
    'Actualizar' button or by taking an action (reassign VA, delete, etc.),
    never on a timer. refresh_dashboard() must not call self.after() to
    reschedule itself, no matter how many times it runs.
    """
    app, cleanup = _make_app()
    try:
        scheduled_ids = []
        original_after = app.after

        def spy_after(delay, func=None, *args):
            if func == app.refresh_dashboard:
                scheduled_ids.append(delay)
            return original_after(delay, func, *args) if func is not None else original_after(delay)

        app.after = spy_after

        for _ in range(5):
            app.refresh_dashboard()

        assert scheduled_ids == [], (
            f"refresh_dashboard() scheduled itself via self.after() {len(scheduled_ids)} "
            "time(s) — dashboard auto-refresh must be fully removed, not just "
            "deduplicated; refresh only happens on explicit user action."
        )
    finally:
        cleanup()


def test_refresh_dashboard_preserves_row_selection():
    """Selecting rows, then having refresh_dashboard() run (e.g. because the
    user edited a different account) must not clear the selection — the
    table is fully torn down and rebuilt, which used to drop it since new
    rows get fresh iids unrelated to the previously selected ones.
    """
    app, cleanup = _make_app()
    try:
        app.db.add_virtual_account("alpha", "GENERAL")
        app.db.add_virtual_account("bravo", "GENERAL")
        app.db.add_virtual_account("charlie", "GENERAL")
        app.refresh_dashboard()

        target_iids = [
            iid for iid in app.tree.get_children()
            if app.tree.item(iid)["values"][2].lstrip("@") in {"alpha", "charlie"}
        ]
        app.tree.selection_set(target_iids)

        app.refresh_dashboard()

        selected_usernames = {
            app.tree.item(iid)["values"][2].lstrip("@")
            for iid in app.tree.selection()
        }
        assert selected_usernames == {"alpha", "charlie"}
    finally:
        cleanup()


def test_switching_tabs_does_not_rebuild_cuentas_rows():
    """Switching to the 'Cuentas' tab used to unconditionally rebuild every
    account row (multiple CTkOptionMenu/CTkEntry widgets each) via
    show_frame(), even when nothing changed — that's the lag felt on every
    tab switch. Navigating there and back must not trigger a rebuild.
    """
    app, cleanup = _make_app()
    try:
        app.db.add_virtual_account("alpha", "GENERAL")
        app._admin_load_accounts()

        calls = []
        app._admin_load_accounts = lambda: calls.append(1)

        app.show_frame("Cuentas")
        app.show_frame("Dashboard")
        app.show_frame("Cuentas")

        assert calls == [], (
            f"show_frame() triggered _admin_load_accounts() {len(calls)} time(s) "
            "just from navigating tabs — it should only rebuild after an actual "
            "data-changing action or the panel's own 'Actualizar' button."
        )
    finally:
        cleanup()
