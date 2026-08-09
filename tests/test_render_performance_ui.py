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
    initial = RenderPerformance(6, 3, 4, 12, None)
    reclamped = RenderPerformance(2, 2, 6, 12, None)
    saved = []
    monkeypatch.setattr(gui_premium_v7, "ctk", fake_ctk)
    monkeypatch.setattr(gui_premium_v7.render_performance, "get_render_performance", lambda: initial)
    monkeypatch.setattr(
        gui_premium_v7.render_performance,
        "save_render_workers",
        lambda workers: saved.append(workers) or reclamped,
    )

    class Harness:
        _build_render_performance_control = InstagramAutoPro._build_render_performance_control
        _on_render_workers_changed = InstagramAutoPro._on_render_workers_changed
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

    first_slider.command(99)

    assert saved == [99]
    assert [slider.value for slider, _label in app._render_worker_controls] == [2, 2]
    assert [slider.options["to"] for slider, _label in app._render_worker_controls] == [2, 2]
    assert [slider.options["number_of_steps"] for slider, _label in app._render_worker_controls] == [1, 1]
    assert [label.options["text"] for label in (first_label, second_label)] == ["2 de 2", "2 de 2"]
