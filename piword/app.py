from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

from .cards import MODE_LABELS, Card, CardStore
from .display import WaveshareDisplay


LEARNED_HOLD_SECONDS = 3.0
RESET_HOLD_SECONDS = 10.0


class ButtonEvents:
    def __init__(self):
        from gpiozero import Button

        self.events: queue.Queue[str] = queue.Queue()
        self.pressed_at: dict[str, float] = {}
        self.suppressed_releases: set[str] = set()
        self.combo_timer: threading.Timer | None = None
        self.lock = threading.Lock()
        self.button1 = Button(5, pull_up=True, bounce_time=0.05)
        self.button2 = Button(6, pull_up=True, bounce_time=0.05)
        self.button3 = Button(13, pull_up=True, bounce_time=0.05)
        self.buttons = {
            "button1": self.button1,
            "button2": self.button2,
            "button3": self.button3,
        }
        for name, button in self.buttons.items():
            button.when_pressed = lambda name=name: self._pressed(name)
            button.when_released = lambda name=name: self._released(name)

    def _pressed(self, name: str) -> None:
        with self.lock:
            self.pressed_at[name] = time.monotonic()
            if (
                self.combo_timer is None
                and "button2" in self.pressed_at
                and "button3" in self.pressed_at
            ):
                self.suppressed_releases.update(("button2", "button3"))
                self.combo_timer = threading.Timer(RESET_HOLD_SECONDS, self._reset_combo)
                self.combo_timer.daemon = True
                self.combo_timer.start()
                self.events.put("reset_arming")

    def _released(self, name: str) -> None:
        with self.lock:
            started = self.pressed_at.pop(name, time.monotonic())
            if name in ("button2", "button3") and self.combo_timer is not None:
                self.combo_timer.cancel()
                self.combo_timer = None
            if name in self.suppressed_releases:
                self.suppressed_releases.discard(name)
                return
        duration = time.monotonic() - started
        if name == "button1" and duration >= LEARNED_HOLD_SECONDS:
            self.events.put("button1_long")
        else:
            self.events.put(f"{name}_short")

    def _reset_combo(self) -> None:
        with self.lock:
            self.combo_timer = None
            if "button2" in self.pressed_at and "button3" in self.pressed_at:
                self.events.put("reset_progress")

    def close(self) -> None:
        with self.lock:
            if self.combo_timer is not None:
                self.combo_timer.cancel()
        for button in self.buttons.values():
            button.close()


def _next_for_mode(
    store: CardStore,
    mode: str,
    level: str | None,
    exclude_id: int | None = None,
) -> tuple[Card, str | None]:
    try:
        return store.next_card(mode=mode, level=level, exclude_id=exclude_id), level
    except RuntimeError:
        if level is not None:
            return store.next_card(mode=mode, level=None, exclude_id=exclude_id), None
        raise


def run_hardware(database_path: Path) -> None:
    store = CardStore(database_path)
    store.initialize()
    display = WaveshareDisplay()
    buttons = ButtonEvents()
    mode = store.available_modes()[0]
    level: str | None = None
    card, level = _next_for_mode(store, mode, level)
    revealed = False
    display.show_card(card, revealed, "B1: pokaz  B2: jezyk  B3: poziom")

    try:
        while True:
            event = buttons.events.get()
            if event == "button1_short":
                if not revealed:
                    revealed = True
                else:
                    store.mark_again(card.id)
                    card, level = _next_for_mode(store, mode, level, card.id)
                    revealed = False
                display.show_card(card, revealed, "B1: dalej  przytrzymaj 3s: umiem")
            elif event == "button1_long":
                store.mark_learned(card.id)
                try:
                    card, level = _next_for_mode(store, mode, level, card.id)
                    message = "ukryto: umiem"
                except RuntimeError:
                    for candidate in store.available_modes():
                        try:
                            card, level = _next_for_mode(store, candidate, None)
                            mode = candidate
                            break
                        except RuntimeError:
                            continue
                    message = "ukryto; brak kolejnych w grupie"
                revealed = False
                display.show_card(card, revealed, message)
            elif event == "button2_short":
                modes = store.available_modes()
                start = modes.index(mode) if mode in modes else -1
                for offset in range(1, len(modes) + 1):
                    candidate = modes[(start + offset) % len(modes)]
                    try:
                        candidate_card, _ = _next_for_mode(store, candidate, None)
                    except RuntimeError:
                        continue
                    mode, level, card = candidate, None, candidate_card
                    break
                revealed = False
                display.show_card(card, revealed, f"jezyk: {MODE_LABELS[mode]}")
            elif event == "button3_short":
                choices: list[str | None] = [None, *store.available_levels(mode)]
                current = choices.index(level) if level in choices else 0
                level = choices[(current + 1) % len(choices)]
                card, level = _next_for_mode(store, mode, level)
                revealed = False
                display.show_card(card, revealed, f"poziom: {level or 'ALL'}")
            elif event == "reset_arming":
                display.show_card(card, revealed, "B2+B3: trzymaj 10 sekund")
            elif event == "reset_progress":
                reset_count = store.reset_progress()
                card, level = _next_for_mode(store, mode, level)
                revealed = False
                display.show_card(card, revealed, f"reset: przywrocono {reset_count}")
    except KeyboardInterrupt:
        pass
    finally:
        buttons.close()
        display.close()
