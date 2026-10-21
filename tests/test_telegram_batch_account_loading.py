from datetime import datetime
from types import SimpleNamespace

import gui_premium_v7
import organizadortg


class _WidgetList:
    def __init__(self):
        self.items = []
        self.selection = None

    def delete(self, *_args):
        self.items.clear()

    def insert(self, _index, value):
        self.items.append(value)

    def select_set(self, *args):
        self.selection = args


def test_telegram_account_loader_uses_batch_counts_and_preserves_video_filter(monkeypatch):
    accounts = [
        {
            "username": "eve",
            "assigned_va": "Leo",
            "account_type": "MAIN",
        },
        {
            "username": "quiet",
            "assigned_va": "Mia",
            "account_type": "TALKING",
        },
    ]
    batch_calls = []
    monkeypatch.setattr(
        organizadortg,
        "count_calendar_videos_by_account",
        lambda: batch_calls.append(True) or {"eve": {"normal": 1, "trial": 2}},
    )
    monkeypatch.setattr(
        organizadortg,
        "count_account_calendar_videos_by_kind",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("per-account recount")
        ),
    )
    monkeypatch.setattr(gui_premium_v7, "_telegram_runtime_diagnostics", lambda _db: [])

    class _Database:
        def get_all_accounts(self):
            return accounts

    app = SimpleNamespace(
        e_date_tg=SimpleNamespace(get=lambda: datetime.now().strftime("%Y-%m-%d")),
        _tg_only_with_videos=SimpleNamespace(get=lambda: True),
        db=_Database(),
        list_tg=_WidgetList(),
        bot_log=lambda *_args, **_kwargs: None,
    )

    gui_premium_v7.InstagramAutoPro.load_organized_accounts(app)

    assert batch_calls == [True]
    assert [account["username"] for account in app._tg_accounts] == ["eve"]
    assert app._tg_accounts[0]["total_videos"] == 3
    assert app._tg_accounts[0]["video_label"] == "3 videos (1 normales, 2 TRIALS)"
    assert len(app.list_tg.items) == 1
    assert app.list_tg.selection == (0, "end")
