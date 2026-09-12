import os
import tempfile
import time
from pathlib import Path

import pytest

ctk = pytest.importorskip("customtkinter")
ImageGrab = pytest.importorskip("PIL.ImageGrab")
ImageStat = pytest.importorskip("PIL.ImageStat")

import database
import gui_premium_v7 as gui


def test_main_window_renders_nonblank_screenshot():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(db_path)
    original_db_path = database.DB_PATH
    database.DB_PATH = db_path
    app = None
    screenshot_path = None
    try:
        app = gui.InstagramAutoPro()
        app.geometry("1200x760+40+40")
        app.attributes("-topmost", True)
        app.deiconify()
        app.lift()
        app.focus_force()
        app.update_idletasks()
        app.update()
        time.sleep(0.8)
        app.update()

        x = app.winfo_rootx()
        y = app.winfo_rooty()
        width = app.winfo_width()
        height = app.winfo_height()
        assert width >= 860
        assert height >= 520

        screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        screenshot_path = Path(tempfile.gettempdir()) / "metodoig_r00_ui_visual.png"
        screenshot.save(screenshot_path)

        extrema = screenshot.convert("RGB").getextrema()
        assert any(low != high for low, high in extrema)
        stat = ImageStat.Stat(screenshot.convert("L"))
        assert stat.stddev[0] > 5

        colors = screenshot.convert("RGB").getcolors(width * height) or []
        warm_black_pixels = sum(
            count
            for count, (red, green, blue) in colors
            if red <= 24 and green <= 24 and blue <= 28
        )
        assert warm_black_pixels > width * height * 0.05
    except Exception as exc:
        if app is None:
            pytest.skip(f"no display available: {exc}")
        raise
    finally:
        if app is not None:
            app.db.conn.close()
            app.destroy()
        database.DB_PATH = original_db_path
        if os.path.exists(db_path):
            os.remove(db_path)
