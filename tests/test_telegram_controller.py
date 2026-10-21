import threading
import organizadortg

from organizadortg import TelegramBotController


def test_stopping_paused_controller_releases_worker_waiting_to_resume():
    controller = TelegramBotController("2026-10-11")
    controller.pause()
    waiting = threading.Event()

    def wait_for_resume():
        waiting.set()
        controller.paused.wait()

    worker = threading.Thread(target=wait_for_resume, daemon=True)
    worker.start()
    assert waiting.wait(timeout=1)

    controller.stop()
    worker.join(timeout=1)

    assert controller.stopped is True
    assert not worker.is_alive()


def test_controller_passes_published_repeat_choice_to_sender(monkeypatch):
    captured = {}

    def fake_execute(_date, _accounts, _controller, **kwargs):
        captured.update(kwargs)
        return "planned"

    monkeypatch.setattr(organizadortg, "execute_telegram_plan", fake_execute)
    controller = TelegramBotController(
        "2026-10-14", selected_accounts=["alpha"], allow_published_repeats=True,
    )
    controller.start()

    assert captured["allow_published_repeats"] is True
