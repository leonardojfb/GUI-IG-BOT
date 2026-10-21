from pathlib import Path
import json
from types import SimpleNamespace

from trial_content import build_trial_account_plan, reused_trial_tanda_warnings, trial_preview_path


def test_duplicate_tanda_uses_each_output_only_once():
    plan = build_trial_account_plan(
        {"eve": "T1", "luna": "T1"},
        {"T1": ["a.mp4", "b.mp4", "c.mp4"]},
        videos_per_day=2,
        days=1,
    )
    assert len(plan.assigned["eve"]) == 2
    assert len(plan.assigned["luna"]) == 1
    assert set(plan.assigned["eve"] + plan.assigned["luna"]) == {"a.mp4", "b.mp4", "c.mp4"}
    assert plan.shortfalls == {"luna": 1}
    assert "T1" in reused_trial_tanda_warnings(plan)[0]


def test_max_days_uses_all_available_files_without_shortfall():
    files = [f"clip_{index:03d}.mp4" for index in range(125)]
    plan = build_trial_account_plan(
        {"evebloom.xo": "evebloom.xo"},
        {"evebloom.xo": files},
        videos_per_day=3,
        days="MAX",
    )
    assert plan.assigned["evebloom.xo"] == files
    assert plan.shortfalls == {}


def test_max_duplicate_tanda_balances_all_copies_without_shortfall():
    files = [f"clip_{index:03d}.mp4" for index in range(5)]
    plan = build_trial_account_plan(
        {"eve": "T1", "luna": "T1", "sol": "T1"},
        {"T1": files},
        videos_per_day=2,
        days="MAX",
    )

    assert [len(plan.assigned[user]) for user in ("eve", "luna", "sol")] == [2, 2, 1]
    assert set(sum(plan.assigned.values(), [])) == set(files)
    assert plan.shortfalls == {}
    assert plan.tanda_stats["T1"]["requested"] == 5
    assert plan.tanda_stats["T1"]["shortfall"] == 0


def test_max_40_copies_across_10_accounts_is_four_each():
    files = [f"clip_{index:03d}.mp4" for index in range(40)]
    accounts = {f"account_{index:02d}": "T1" for index in range(10)}
    plan = build_trial_account_plan(accounts, {"T1": files}, 3, "MAX")
    assert [len(plan.assigned[user]) for user in accounts] == [4] * 10
    assert set(sum(plan.assigned.values(), [])) == set(files)
    assert plan.shortfalls == {}


def test_max_remainder_and_fewer_copies_than_accounts():
    accounts = {f"account_{index:02d}": "T1" for index in range(10)}
    forty_one = build_trial_account_plan(
        accounts, {"T1": [f"clip_{index:03d}.mp4" for index in range(41)]}, 2, "MAX"
    )
    assert [len(forty_one.assigned[user]) for user in accounts] == [5] + [4] * 9
    three = build_trial_account_plan(accounts, {"T1": ["a.mp4", "b.mp4", "c.mp4"]}, 1, "MAX")
    assert [len(three.assigned[user]) for user in accounts] == [1] * 3 + [0] * 7
    assert three.shortfalls == {}


def test_max_balances_each_tanda_independently():
    plan = build_trial_account_plan(
        {"a": "A", "b": "A", "c": "B", "d": "B"},
        {"A": [f"a{index}.mp4" for index in range(5)],
         "B": [f"b{index}.mp4" for index in range(4)]},
        2, "MAX",
    )
    assert [len(plan.assigned[user]) for user in ("a", "b", "c", "d")] == [3, 2, 2, 2]
    assert plan.shortfalls == {}


def test_trial_plan_interleaves_sources_before_repeating_copies():
    plan = build_trial_account_plan(
        {"eve": "T1"},
        {
            "T1": [
                "vid1__c01.mp4",
                "vid1__c02.mp4",
                "vid1__c03.mp4",
                "vid2__c01.mp4",
                "vid2__c02.mp4",
                "vid2__c03.mp4",
                "vid3__c01.mp4",
                "vid3__c02.mp4",
            ],
        },
        videos_per_day=8,
        days=1,
    )
    assert plan.assigned["eve"] == [
        "vid1__c01.mp4",
        "vid2__c01.mp4",
        "vid3__c01.mp4",
        "vid1__c02.mp4",
        "vid2__c02.mp4",
        "vid3__c02.mp4",
        "vid1__c03.mp4",
        "vid2__c03.mp4",
    ]


def test_trial_plan_continues_interleaved_tanda_pool_per_individual_account():
    plan = build_trial_account_plan(
        {"eve": "T1", "luna": "T1"},
        {
            "T1": [
                "vid1__c01.mp4",
                "vid1__c02.mp4",
                "vid2__c01.mp4",
                "vid2__c02.mp4",
                "vid3__c01.mp4",
                "vid3__c02.mp4",
            ],
        },
        videos_per_day=3,
        days=1,
    )
    assert len(plan.assigned["eve"]) == len(plan.assigned["luna"]) == 3
    assert len(set(plan.assigned["eve"] + plan.assigned["luna"])) == 6
    assert plan.daily_repeats == {1: 3}


def test_trial_plan_spreads_origins_between_accounts_on_same_day():
    plan = build_trial_account_plan(
        {"eve": "T1", "luna": "T1"},
        {"T1": ["x__c01.mp4", "x__c02.mp4", "y__c01.mp4", "y__c02.mp4"]},
        videos_per_day=1,
        days=2,
    )
    for day in range(2):
        assert {plan.assigned[user][day].split("__")[0] for user in ("eve", "luna")} == {"x", "y"}


def test_trial_plan_avoids_existing_other_account_origin_but_replaces_selected_account():
    plan = build_trial_account_plan(
        {"eve": "T1"},
        {"T1": ["x__c01.mp4", "y__c01.mp4"]},
        videos_per_day=1,
        days=1,
        existing_entries=[
            {"username": "other", "delivery_kind": "trial", "day": 1,
             "tanda": "T1", "source_path": "x__c99.mp4"},
            {"username": "eve", "delivery_kind": "trial", "day": 1,
             "tanda": "T1", "source_path": "y__c99.mp4"},
        ],
    )
    assert plan.assigned["eve"] == ["y__c01.mp4"]


def test_trial_plan_uses_verified_origin_across_tandas_and_ignores_normal_entries():
    plan = build_trial_account_plan(
        {"eve": "NEW"},
        {"NEW": ["a.mp4", "b.mp4"]},
        1, 1,
        origin_by_file={("NEW", "a.mp4"): "same", ("NEW", "b.mp4"): "other"},
        existing_entries=[
            {"username": "old", "delivery_kind": "trial", "day": 1,
             "tanda": "OLD", "source_path": "different-name.mp4", "origin_identity": "same"},
            {"username": "normal", "delivery_kind": "normal", "day": 1,
             "tanda": "NEW", "source_path": "b.mp4", "origin_identity": "other"},
        ],
    )
    assert plan.assigned["eve"] == ["b.mp4"]
    assert plan.daily_repeats == {}


def test_trial_repeat_report_counts_collisions_between_accounts_only():
    plan = build_trial_account_plan(
        {"eve": "T1"},
        {"T1": ["x__c01.mp4", "x__c02.mp4"]},
        videos_per_day=2, days=1,
    )
    assert len(plan.assigned["eve"]) == 2
    assert plan.daily_repeats == {}


def test_trial_max_balances_verified_origins_across_tandas_deterministically():
    args = (
        {"eve": "A", "luna": "B"},
        {"A": ["a1.mp4", "a2.mp4"], "B": ["b1.mp4", "b2.mp4"]},
        1, "MAX",
    )
    origins = {
        ("A", "a1.mp4"): "x", ("A", "a2.mp4"): "y",
        ("B", "b1.mp4"): "x", ("B", "b2.mp4"): "y",
    }
    first = build_trial_account_plan(*args, origin_by_file=origins)
    second = build_trial_account_plan(*args, origin_by_file=origins)
    assert first == second
    assert first.daily_repeats == {}
    for day in range(2):
        assert {origins[("A", first.assigned["eve"][day])],
                origins[("B", first.assigned["luna"][day])]} == {"x", "y"}


def test_trial_plan_reserves_scarce_origin_for_account_without_alternative():
    plan = build_trial_account_plan(
        {"flexible": "A", "only_x": "B"},
        {"A": ["x.mp4", "y.mp4"], "B": ["x_copy.mp4"]},
        1, 1,
        origin_by_file={("A", "x.mp4"): "x", ("A", "y.mp4"): "y",
                        ("B", "x_copy.mp4"): "x"},
    )
    assert plan.assigned == {"flexible": ["y.mp4"], "only_x": ["x_copy.mp4"]}
    assert plan.daily_repeats == {}


def test_trial_preview_accounts_for_existing_manifest(tmp_path, monkeypatch):
    import gui_premium_v7

    monkeypatch.setattr(gui_premium_v7, "_BASE_DIR", str(tmp_path))
    folder = tmp_path / "videos_finales" / "T1"
    folder.mkdir(parents=True)
    for name in ("x__c01.mp4", "y__c01.mp4"):
        (folder / name).write_bytes(b"video")
    (tmp_path / "calendar_manifest.json").write_text(json.dumps({
        "version": 1,
        "entries": [{"username": "other", "delivery_kind": "trial", "day": 1,
                     "tanda": "T1", "source_path": str(folder / "x__c99.mp4")}],
    }), encoding="utf-8")

    class Textbox:
        value = ""

        def delete(self, *_args):
            self.value = ""

        def insert(self, *_args):
            self.value = _args[-1]

    textbox = Textbox()
    fake = SimpleNamespace(
        _trial_selected_assignments=lambda: {"eve": "T1"},
        _save_trial_captions=lambda: None,
        _trial_missing_caption_sources=lambda _tanda: [],
        trial_dist_vpd=SimpleNamespace(get=lambda: "1"),
        trial_dist_days=SimpleNamespace(get=lambda: "1"),
        _trial_tanda_files=lambda _tanda: ["x__c01.mp4", "y__c01.mp4"],
        db=SimpleNamespace(
            get_video_transform_source_identity=lambda _path: None,
            get_trials_active_accounts=lambda: [{"username": "eve", "id": 1}],
            get_video_transform_log_id=lambda _path: None,
        ),
        trial_dist_result=textbox,
    )
    gui_premium_v7.InstagramAutoPro._trial_dist_run_per_account(fake, True)
    assert "y__c01.mp4" in textbox.value
    assert "x__c01.mp4" not in textbox.value

    class SyncWorker:
        def __init__(self, _owner, done, task):
            self.done = done
            self.task = task

        def start(self):
            self.done(True, self.task())

    monkeypatch.setattr(gui_premium_v7, "WorkerThread", SyncWorker)
    monkeypatch.setattr(gui_premium_v7.messagebox, "askyesno", lambda *_args: True)
    gui_premium_v7.InstagramAutoPro._trial_dist_run_per_account(fake, False)
    rows = json.loads((tmp_path / "calendar_manifest.json").read_text(encoding="utf-8"))["entries"]
    assert len(rows) == 2
    assert {(row["username"], Path(row["source_path"]).name) for row in rows} == {
        ("other", "x__c99.mp4"), ("eve", "y__c01.mp4"),
    }


def test_trial_preview_stops_on_invalid_manifest(tmp_path, monkeypatch):
    import gui_premium_v7

    monkeypatch.setattr(gui_premium_v7, "_BASE_DIR", str(tmp_path))
    (tmp_path / "calendar_manifest.json").write_text("{invalid", encoding="utf-8")
    errors = []
    monkeypatch.setattr(gui_premium_v7.messagebox, "showerror", lambda *args: errors.append(args))
    fake = SimpleNamespace(
        _trial_selected_assignments=lambda: {"eve": "T1"},
        _save_trial_captions=lambda: None,
        _trial_missing_caption_sources=lambda _tanda: [],
        trial_dist_vpd=SimpleNamespace(get=lambda: "1"),
        trial_dist_days=SimpleNamespace(get=lambda: "1"),
        _trial_tanda_files=lambda _tanda: ["x__c01.mp4"],
        db=SimpleNamespace(get_video_transform_source_identity=lambda _path: None),
    )
    gui_premium_v7.InstagramAutoPro._trial_dist_run_per_account(fake, True)
    assert errors and "ocupación TRIAL" in errors[0][1]


def test_trial_max_preview_and_manifest_split_40_copies_across_10_accounts(tmp_path, monkeypatch):
    import gui_premium_v7

    monkeypatch.setattr(gui_premium_v7, "_BASE_DIR", str(tmp_path))
    folder = tmp_path / "videos_finales" / "T1"
    folder.mkdir(parents=True)
    files = [f"clip_{index:03d}.mp4" for index in range(40)]
    for name in files:
        (folder / name).write_bytes(b"video")
    accounts = [f"account_{index:02d}" for index in range(10)]

    class Textbox:
        value = ""

        def delete(self, *_args):
            self.value = ""

        def insert(self, *_args):
            self.value = _args[-1]

    class SyncWorker:
        def __init__(self, _owner, done, task):
            self.done = done
            self.task = task

        def start(self):
            self.done(True, self.task())

    monkeypatch.setattr(gui_premium_v7, "WorkerThread", SyncWorker)
    monkeypatch.setattr(gui_premium_v7.messagebox, "askyesno", lambda *_args: True)
    textbox = Textbox()
    fake = SimpleNamespace(
        _trial_selected_assignments=lambda: {user: "T1" for user in accounts},
        _save_trial_captions=lambda: None,
        _trial_missing_caption_sources=lambda _tanda: [],
        trial_dist_vpd=SimpleNamespace(get=lambda: "3"),
        trial_dist_days=SimpleNamespace(get=lambda: "MAX"),
        _trial_tanda_files=lambda _tanda: files,
        db=SimpleNamespace(
            get_video_transform_source_identity=lambda _path: None,
            get_trials_active_accounts=lambda: [
                {"username": user, "id": index + 1} for index, user in enumerate(accounts)
            ],
            get_video_transform_log_id=lambda _path: None,
        ),
        trial_dist_result=textbox,
    )
    gui_premium_v7.InstagramAutoPro._trial_dist_run_per_account(fake, True)
    assert all(f"@{user}: 4 videos" in textbox.value for user in accounts)
    assert "faltan" not in textbox.value
    gui_premium_v7.InstagramAutoPro._trial_dist_run_per_account(fake, False)
    rows = json.loads((tmp_path / "calendar_manifest.json").read_text(encoding="utf-8"))["entries"]
    assert len(rows) == len({row["source_path"] for row in rows}) == 40
    assert all(sum(row["username"] == user for row in rows) == 4 for user in accounts)
    assert {row["caption_mode"] for row in rows} == {"individual"}


def test_trial_general_preview_and_manifest_bind_captions_per_copy(tmp_path, monkeypatch):
    import gui_premium_v7

    monkeypatch.setattr(gui_premium_v7, "_BASE_DIR", str(tmp_path))
    folder = tmp_path / "videos_finales" / "T"
    folder.mkdir(parents=True)
    files = ["clip__c01.mp4", "clip__c02.mp4"]
    for name in files:
        (folder / name).write_bytes(b"video")
    caption_txt = tmp_path / "captions.txt"
    caption_txt.write_text("Caption A\n#one\n\nCaption B\n#two\n", encoding="utf-8")

    class Textbox:
        value = ""

        def delete(self, *_args):
            self.value = ""

        def insert(self, *_args):
            self.value = _args[-1]

    class SyncWorker:
        def __init__(self, _owner, done, task):
            self.done, self.task = done, task

        def start(self):
            self.done(True, self.task())

    monkeypatch.setattr(gui_premium_v7, "WorkerThread", SyncWorker)
    monkeypatch.setattr(gui_premium_v7.messagebox, "askyesno", lambda *_args: True)
    textbox = Textbox()
    fake = SimpleNamespace(
        _trial_selected_assignments=lambda: {"a": "T", "b": "T"},
        _save_trial_captions=lambda: None,
        _trial_missing_caption_sources=lambda _tanda: ["clip"],
        trial_caption_mode=SimpleNamespace(get=lambda: "General"),
        trial_general_txt_path=SimpleNamespace(get=lambda: str(caption_txt)),
        trial_dist_vpd=SimpleNamespace(get=lambda: "1"),
        trial_dist_days=SimpleNamespace(get=lambda: "MAX"),
        _trial_tanda_files=lambda _tanda: files,
        db=SimpleNamespace(
            get_video_transform_source_identity=lambda _path: None,
            get_trials_active_accounts=lambda: [{"username": "a", "id": 1},
                                                {"username": "b", "id": 2}],
            get_video_transform_log_id=lambda _path: None,
        ),
        trial_dist_result=textbox,
    )
    gui_premium_v7.InstagramAutoPro._trial_dist_run_per_account(fake, True)
    assert "Caption A" in textbox.value and "Caption B" in textbox.value
    gui_premium_v7.InstagramAutoPro._trial_dist_run_per_account(fake, False)
    rows = json.loads((tmp_path / "calendar_manifest.json").read_text(encoding="utf-8"))["entries"]
    assert {row["caption"] for row in rows} == {"Caption A\n#one", "Caption B\n#two"}
    assert {row["caption_mode"] for row in rows} == {"general"}


def test_trial_general_missing_txt_blocks_before_manifest_write(tmp_path, monkeypatch):
    import gui_premium_v7

    monkeypatch.setattr(gui_premium_v7, "_BASE_DIR", str(tmp_path))
    warnings = []
    monkeypatch.setattr(gui_premium_v7.messagebox, "showwarning", lambda *args: warnings.append(args))
    fake = SimpleNamespace(
        _trial_selected_assignments=lambda: {"a": "T"},
        _save_trial_captions=lambda: None,
        trial_caption_mode=SimpleNamespace(get=lambda: "General"),
        trial_general_txt_path=SimpleNamespace(get=lambda: ""),
    )
    gui_premium_v7.InstagramAutoPro._trial_dist_run_per_account(fake, False)
    assert warnings and "TXT" in warnings[0][1]
    assert not (tmp_path / "calendar_manifest.json").exists()


def test_trial_caption_mode_and_txt_are_global_controls(monkeypatch):
    import gui_premium_v7

    widgets = []

    class Widget:
        def __init__(self, parent=None, **kwargs):
            self.parent = parent
            self.kwargs = kwargs
            self.children = []
            widgets.append(self)
            if parent is not None:
                parent.children.append(self)

        def pack(self, **_kwargs):
            return self

        def grid(self, **_kwargs):
            return self

        def grid_columnconfigure(self, *_args, **_kwargs):
            return None

        def grid_rowconfigure(self, *_args, **_kwargs):
            return None

        def insert(self, *_args):
            return None

        def winfo_children(self):
            return self.children

        def destroy(self):
            return None

        def configure(self, **kwargs):
            self.kwargs.update(kwargs)

    class StringVar:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

    monkeypatch.setattr(gui_premium_v7.ctk, "CTkFrame", Widget)
    monkeypatch.setattr(gui_premium_v7.ctk, "CTkLabel", Widget)
    monkeypatch.setattr(gui_premium_v7.ctk, "CTkComboBox", Widget)
    monkeypatch.setattr(gui_premium_v7.ctk, "CTkEntry", Widget)
    monkeypatch.setattr(gui_premium_v7.ctk, "CTkScrollableFrame", Widget)
    monkeypatch.setattr(gui_premium_v7.ctk, "CTkTextbox", Widget)
    monkeypatch.setattr(gui_premium_v7, "GhostButton", Widget)
    monkeypatch.setattr(gui_premium_v7, "DangerButton", Widget)
    monkeypatch.setattr(gui_premium_v7, "PrimaryButton", Widget)
    monkeypatch.setattr(gui_premium_v7, "Stepper", Widget)
    monkeypatch.setattr(gui_premium_v7.tk, "StringVar", StringVar)
    fake = SimpleNamespace(
        _save_trial_captions=lambda: None,
        _trial_dist_run_per_account=lambda _preview: None,
        _trial_on_global_caption_mode_changed=lambda _value=None: None,
        _trial_choose_general_txt=lambda: None,
        _trial_clear_general_txt=lambda: None,
        _trial_toggle_account_panel=lambda _username: None,
        _trial_on_account_tanda_changed=lambda _username: None,
        db=SimpleNamespace(get_trials_active_accounts=lambda: [{"username": "eve", "account_type": "MAIN"}],
                           get_trial_tandas=lambda: ["T"]),
    )
    gui_premium_v7.InstagramAutoPro._build_dist_trials_tab(fake, Widget())
    gui_premium_v7.InstagramAutoPro._trial_refresh_account_rows(fake)
    assert fake.trial_caption_mode.get() == "Individual"
    assert sum(w.kwargs.get("values") == ["Individual", "General"] for w in widgets) == 1
    assert any("Modo captions TRIAL" in w.kwargs.get("text", "") for w in widgets)
    assert any("Elegir TXT" in w.kwargs.get("text", "") for w in widgets)
    assert not hasattr(fake, "trial_account_modes")


def test_trial_global_general_hides_individual_panels_and_switches_back():
    import gui_premium_v7

    class Control:
        def __init__(self):
            self.state = "normal"
            self.visible = True

        def configure(self, **kwargs):
            self.state = kwargs.get("state", self.state)

        def pack_forget(self):
            self.visible = False

        def pack(self, **_kwargs):
            self.visible = True

    mode = SimpleNamespace(value="General", get=lambda: mode.value)
    panel, edit, txt, clear, save = (Control() for _ in range(5))
    writes, renders = [], []
    fake = SimpleNamespace(
        trial_caption_mode=mode,
        trial_caption_editors={("eve", "T", "clip"): object()},
        _save_trial_captions=lambda: writes.append("saved"),
        trial_account_panel_frames={"eve": panel},
        trial_panel_buttons={"eve": edit},
        trial_expanded_accounts={"eve"},
        trial_general_txt_btn=txt,
        trial_general_txt_clear_btn=clear,
        trial_save_individual_btn=save,
        _trial_render_account_panel=lambda username: renders.append(username),
    )
    gui_premium_v7.InstagramAutoPro._trial_on_global_caption_mode_changed(fake)
    assert writes == ["saved"]
    assert not panel.visible and edit.state == "disabled" and txt.state == "normal"
    assert clear.state == "normal" and save.state == "disabled"
    mode.value = "Individual"
    gui_premium_v7.InstagramAutoPro._trial_on_global_caption_mode_changed(fake)
    assert panel.visible and edit.state == "normal" and txt.state == "disabled"
    assert clear.state == "disabled" and save.state == "normal"
    assert renders == ["eve"]


def test_trial_tanda_change_does_not_render_hidden_individual_panel_in_general():
    import gui_premium_v7

    rendered = []
    mode = SimpleNamespace(get=lambda: "General")
    fake = SimpleNamespace(
        trial_caption_mode=mode,
        trial_caption_editors={("eve", "OLD", "clip"): object()},
        trial_expanded_accounts={"eve"},
        _trial_render_account_panel=lambda username: rendered.append(username),
    )
    gui_premium_v7.InstagramAutoPro._trial_on_account_tanda_changed(fake, "eve")
    assert rendered == []
    assert fake.trial_caption_editors == {}


def test_preview_cache_path_is_stable_and_png(tmp_path):
    video = tmp_path / "vid1__c01.mp4"
    video.write_bytes(b"video")
    assert trial_preview_path(video) == trial_preview_path(video)
    assert trial_preview_path(video).suffix == ".png"


def test_trial_distribution_does_not_fall_back_to_all_active_trials():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    start = source.index("    def _trial_dist_run_per_account")
    end = source.index("    def _build_dist_cuentas_tab", start)
    body = source[start:end]
    assert "selected_trial_usernames(" not in body
    assert "Faltan videos: se necesitan" not in body


def test_trial_distribution_confirmation_says_calendarize_not_create():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    start = source.index("    def _trial_dist_run_per_account")
    end = source.index("    def _build_dist_cuentas_tab", start)
    body = source[start:end]
    assert "Crear {sum(map(len, plan.assigned.values()))} videos" not in body
    assert "Calendarizar {sum(map(len, plan.assigned.values()))} videos" in body


def test_trial_distribution_writes_manifest_not_calendar_copies():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    start = source.index("    def _trial_dist_run_per_account")
    end = source.index("    def _build_dist_cuentas_tab", start)
    body = source[start:end]
    assert "_copy_calendar_file(" not in body
    assert "replace_entries(" in body
    assert 'delivery_kind="trial"' in body


def test_trial_distribution_replaces_all_assigned_accounts_even_when_zero_videos():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    start = source.index("    def _trial_dist_run_per_account")
    end = source.index("    def _build_dist_cuentas_tab", start)
    body = source[start:end]
    assert "affected = set(plan.assigned)" in body
    assert "affected.add(user)" not in body


def test_trial_distribution_blocks_incomplete_calendarization():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    start = source.index("    def _trial_dist_run_per_account")
    end = source.index("    def _build_dist_cuentas_tab", start)
    body = source[start:end]
    assert "if plan.shortfalls and not preview_only:" in body
    assert "No se calendariza incompleto" in body


def test_trial_logistica_has_no_global_tanda_selector_and_uses_account_panels():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")
    start = source.index("    def _build_dist_trials_tab")
    end = source.index("    def _build_dist_cuentas_tab", start)
    body = source[start:end]
    assert "self.trial_dist_tanda" not in body
    assert "Tanda Trial:" not in body
    assert "_trial_toggle_account_panel" in body

