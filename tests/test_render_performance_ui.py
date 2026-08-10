from pathlib import Path
from types import SimpleNamespace

import gui_premium_v7
from gui_premium_v7 import InstagramAutoPro
from render_performance import RenderPerformance


SOURCE = Path("gui_premium_v7.py")


def extract_method(source: str, method: str) -> str:
    start = source.index(f"    def {method}(")
    next_method = source.find("\n    def ", start + 1)
    return source[start:] if next_method == -1 else source[start:next_method]


def test_all_three_content_screens_build_the_shared_performance_control():
    source = SOURCE.read_text(encoding="utf-8")

    for method in ("_build_mix_frame", "_build_video_editor_frame", "_build_forge_frame"):
        assert "_build_render_performance_control" in extract_method(source, method)


def test_performance_change_persists_and_synchronizes_built_controls(monkeypatch):
    class Widget:
        def __init__(self, *_args, **kwargs):
            self.command = kwargs.get("command")
            self.options = kwargs
            self.value = None
            self.emit_on_set = False

        def configure(self, **kwargs):
            self.options.update(kwargs)

        def set(self, value):
            self.value = value
            if self.emit_on_set and self.command:
                self.command(value)

        def pack(self, **_kwargs):
            pass

    fake_ctk = SimpleNamespace(
        CTkFrame=Widget,
        CTkLabel=Widget,
        CTkSlider=Widget,
        CTkFont=lambda **kwargs: kwargs,
    )
    initial = RenderPerformance(6, 3, 4, 12, None, available_workers=6)
    saved_snapshot = RenderPerformance(6, 5, 2, 12, None, available_workers=6)
    saved = []
    monkeypatch.setattr(gui_premium_v7, "ctk", fake_ctk)
    monkeypatch.setattr(gui_premium_v7.render_performance, "get_render_performance", lambda: initial)
    monkeypatch.setattr(
        gui_premium_v7.render_performance,
        "save_render_workers",
        lambda workers: saved.append(workers) or saved_snapshot,
    )

    class Harness:
        _build_render_performance_control = InstagramAutoPro._build_render_performance_control
        _on_render_workers_changed = InstagramAutoPro._on_render_workers_changed
        _render_performance_value_text = InstagramAutoPro._render_performance_value_text
        _sync_render_worker_controls = InstagramAutoPro._sync_render_worker_controls

        def __init__(self):
            self._render_worker_controls = []
            self._render_worker_syncing = False

    app = Harness()
    app._build_render_performance_control(Widget(), "Tandas")
    app._build_render_performance_control(Widget(), "Forge")
    first_slider, first_label = app._render_worker_controls[0]
    second_slider, second_label = app._render_worker_controls[1]
    first_slider.emit_on_set = True
    second_slider.emit_on_set = True

    first_slider.command(5)

    assert saved == [5]
    assert [slider.value for slider, _label in app._render_worker_controls] == [5, 5]
    assert [slider.options["to"] for slider, _label in app._render_worker_controls] == [6, 6]
    assert [slider.options["number_of_steps"] for slider, _label in app._render_worker_controls] == [5, 5]
    assert [label.options["text"] for label in (first_label, second_label)] == [
        "5 de 6 equipo",
        "5 de 6 equipo",
    ]


def test_performance_change_above_current_memory_limit_warns_and_keeps_safe_value(monkeypatch):
    class Widget:
        def __init__(self, *_args, **kwargs):
            self.command = kwargs.get("command")
            self.options = kwargs
            self.value = None

        def configure(self, **kwargs):
            self.options.update(kwargs)

        def set(self, value):
            self.value = value

        def pack(self, **_kwargs):
            pass

    fake_ctk = SimpleNamespace(
        CTkFrame=Widget,
        CTkLabel=Widget,
        CTkSlider=Widget,
        CTkFont=lambda **kwargs: kwargs,
    )
    limited = RenderPerformance(8, 2, 4, 8, 4 << 30, available_workers=2)
    saved = []
    warnings = []
    monkeypatch.setattr(gui_premium_v7, "ctk", fake_ctk)
    monkeypatch.setattr(gui_premium_v7.render_performance, "get_render_performance", lambda: limited)
    monkeypatch.setattr(
        gui_premium_v7.render_performance,
        "save_render_workers",
        lambda workers: saved.append(workers) or limited,
    )
    monkeypatch.setattr(gui_premium_v7.messagebox, "showwarning", lambda title, text: warnings.append((title, text)))

    class Harness:
        _build_render_performance_control = InstagramAutoPro._build_render_performance_control
        _on_render_workers_changed = InstagramAutoPro._on_render_workers_changed
        _render_performance_value_text = InstagramAutoPro._render_performance_value_text
        _sync_render_worker_controls = InstagramAutoPro._sync_render_worker_controls

        def __init__(self):
            self._render_worker_controls = []
            self._render_worker_syncing = False

    app = Harness()
    app._build_render_performance_control(Widget(), "Edicion")
    slider, label = app._render_worker_controls[0]

    slider.command(3)

    assert saved == []
    assert slider.value == 2
    assert label.options["text"] == "2 de 8 equipo - RAM actual: 2"
    assert len(warnings) == 1
    assert "cerr" in warnings[0][1].lower()
    assert "programas" in warnings[0][1].lower()


def test_single_worker_control_uses_a_disabled_safe_range_and_clamps_callbacks(monkeypatch):
    class Widget:
        def __init__(self, *_args, **kwargs):
            self.options = kwargs
            self.value = None

        def configure(self, **kwargs):
            self.options.update(kwargs)

        def pack(self, **_kwargs):
            pass

    class StrictSlider(Widget):
        def __init__(self, *_args, **kwargs):
            if kwargs["from_"] >= kwargs["to"]:
                raise ZeroDivisionError("CustomTkinter slider endpoints must differ")
            super().__init__(_args, **kwargs)
            self.command = kwargs["command"]

        def configure(self, **kwargs):
            options = self.options | kwargs
            if options["from_"] >= options["to"]:
                raise ZeroDivisionError("CustomTkinter slider endpoints must differ")
            super().configure(**kwargs)

        def set(self, value):
            if value != 1:
                raise AssertionError("one-choice slider may only show 1")
            self.value = value

    fake_ctk = SimpleNamespace(
        CTkFrame=Widget,
        CTkLabel=Widget,
        CTkSlider=StrictSlider,
        CTkFont=lambda **kwargs: kwargs,
    )
    one = RenderPerformance(1, 1, 1, 1, None, available_workers=1)
    saved = []
    monkeypatch.setattr(gui_premium_v7, "ctk", fake_ctk)
    monkeypatch.setattr(gui_premium_v7.render_performance, "get_render_performance", lambda: one)
    monkeypatch.setattr(
        gui_premium_v7.render_performance,
        "save_render_workers",
        lambda workers: saved.append(workers) or one,
    )

    class Harness:
        _build_render_performance_control = InstagramAutoPro._build_render_performance_control
        _on_render_workers_changed = InstagramAutoPro._on_render_workers_changed
        _render_performance_value_text = InstagramAutoPro._render_performance_value_text
        _sync_render_worker_controls = InstagramAutoPro._sync_render_worker_controls

        def __init__(self):
            self._render_worker_controls = []
            self._render_worker_syncing = False

    app = Harness()
    app._build_render_performance_control(Widget(), "Forge")
    slider, label = app._render_worker_controls[0]
    app._sync_render_worker_controls(one)
    slider.command(2)

    assert slider.options["from_"] == 1
    assert slider.options["to"] == 2
    assert slider.options["state"] == "disabled"
    assert slider.value == 1
    assert label.options["text"] == "1 de 1 equipo"
    assert saved == [1]


def test_control_surfaces_a_non_blocking_hardware_reclamp_notice(monkeypatch):
    class Widget:
        def __init__(self, *_args, **kwargs):
            self.options = kwargs
            self.value = None

        def set(self, value):
            self.value = value

        def pack(self, **_kwargs):
            pass

    fake_ctk = SimpleNamespace(
        CTkFrame=Widget,
        CTkLabel=Widget,
        CTkSlider=Widget,
        CTkFont=lambda **kwargs: kwargs,
    )
    reclamped = RenderPerformance(8, 2, 4, 8, 4 << 30, workers_were_reclamped=True, available_workers=2)
    monkeypatch.setattr(gui_premium_v7, "ctk", fake_ctk)
    monkeypatch.setattr(
        gui_premium_v7.render_performance,
        "get_render_performance",
        lambda: reclamped,
    )

    class Harness:
        _build_render_performance_control = InstagramAutoPro._build_render_performance_control
        _on_render_workers_changed = InstagramAutoPro._on_render_workers_changed
        _render_performance_value_text = InstagramAutoPro._render_performance_value_text

        def __init__(self):
            self._render_worker_controls = []
            self._render_worker_syncing = False

    app = Harness()
    app._build_render_performance_control(Widget(), "Edición")

    _slider, value_label = app._render_worker_controls[0]
    text = value_label.options["text"].lower()
    assert "ajustado" in text
    assert "ram actual" in text


def test_render_controls_are_immediately_before_their_primary_actions():
    source = SOURCE.read_text(encoding="utf-8")
    tandas = extract_method(source, "_build_mix_frame")
    editor = extract_method(source, "_build_video_editor_frame")
    forge = extract_method(source, "_build_forge_frame")

    tandas_button_pack = 'self.btn_render.pack(side="right")'
    tandas_control_pack = '_build_render_performance_control(bot_body, "Tandas").pack(side="right"'
    editor_button_pack = 'self.btn_editor_render.pack(side="right")'
    editor_control_pack = '_build_render_performance_control(actions, "Edición").pack(side="right"'

    # Tk packs successive right-side widgets from the edge inward. The button
    # must therefore be packed first, then the adjacent control to its left.
    assert tandas.index(tandas_button_pack) < tandas.index(tandas_control_pack)
    assert editor.index(editor_button_pack) < editor.index(editor_control_pack)
    assert "self.btn_editor_render = PrimaryButton(" in editor
    assert 'actions, text="Renderizar video", command=self.editor_render)' in editor
    assert forge.index('_build_render_performance_control(bot, "Forge")') < forge.index("self.btn_forge_process = PrimaryButton")
    assert 'row=0, column=2' in forge[forge.index('_build_render_performance_control(bot, "Forge")'):]
    assert 'row=0, column=3' in forge[forge.index("self.btn_forge_process = PrimaryButton"):]
