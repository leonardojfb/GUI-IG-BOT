import customtkinter as ctk
import pytest

from gui_premium_v7 import InstagramAutoPro


class TelegramLayoutHarness:
    _build_tg_frame = InstagramAutoPro._build_tg_frame
    _toggle_tg_options = InstagramAutoPro._toggle_tg_options
    _toggle_schedule_panel = InstagramAutoPro._toggle_schedule_panel
    themed = InstagramAutoPro.themed

    def __init__(self, root):
        self._frames = {"Telegram": ctk.CTkFrame(root)}
        self._frames["Telegram"].pack(fill="both", expand=True)

    def load_organized_accounts(self):
        pass

    def start_tg_bot(self):
        pass

    def pause_tg_bot(self):
        pass

    def stop_tg_bot(self):
        pass

    def delete_selected_calendarizations(self):
        pass

    def _sync_tg_airtable_toggle(self):
        pass

    def _refresh_schedule_panel(self):
        pass


def test_telegram_tab_scrolls_and_switches_expand_without_resetting_values():
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("no display available")
    try:
        root.geometry("610x520")
        ui = TelegramLayoutHarness(root)
        ui._build_tg_frame()
        root.update()

        scroll = ui.tg_scroll
        assert isinstance(scroll, ctk.CTkScrollableFrame)
        assert scroll._parent_canvas.yview()[1] < 1
        scroll._parent_canvas.yview_moveto(1)
        assert scroll._parent_canvas.yview()[1] == 1
        assert not ui.tg_options_panel.winfo_ismapped()
        assert not ui.sched_panel.winfo_ismapped()

        ui._toggle_tg_options()
        root.update()
        assert ui.tg_options_panel.winfo_ismapped()
        assert len(ui.tg_options_panel.winfo_children()) == 6
        ui._tg_express_mode.set(True)
        ui._toggle_tg_options()
        root.update()
        assert not ui.tg_options_panel.winfo_ismapped()
        assert ui._tg_express_mode.get() is True
        ui._toggle_tg_options()
        assert ui._tg_express_mode.get() is True
        ui._toggle_schedule_panel()
        root.update()
        assert ui.sched_panel.winfo_ismapped()
        assert ui.sched_panel.grid_info()["row"] == 5
    finally:
        root.destroy()
