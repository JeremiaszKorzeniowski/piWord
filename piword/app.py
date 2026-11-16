from __future__ import annotations

import queue
import time
from pathlib import Path

from .cards import Card, CardStore
from .display import WaveshareDisplay


SHORT_PRESS_LIMIT = 1.5


class ButtonEvents:
    def __init__(self):
        from gpiozero import Button

        self.events: queue.Queue[str] = queue.Queue()
        self.pressed_at: dict[str, float] = {}
        self.button1 = Button(5, pull_up=True, bounce_time=0.05)
        self.button2 = Button(6, pull_up=True, bounce_time=0.05)

        self.button1.when_pressed = lambda: self._pressed("button1")
        self.button1.when_released = lambda: self._released("button1")
        self.button2.when_pressed = lambda: self._pressed("button2")
        self.button2.when_released = lambda: self._released("button2")

    def _pressed(self, name: str) -> None:
        self.pressed_at[name] = time.monotonic()

    def _released(self, name: str) -> None:
        started = self.pressed_at.pop(name, time.monotonic())
        duration = time.monotonic() - started
        suffix = "long" if duration >= SHORT_PRESS_LIMIT else "short"
        self.events.put(f"{name}_{suffix}")

    def close(self) -> None:
        self.button1.close()
        self.button2.close()


def run_hardware(database_path: Path) -> None:
    store = CardStore(database_path)
    store.initialize()
    display = WaveshareDisplay()
    buttons = ButtonEvents()
    card: Card = store.next_card()
    revealed = False
    display.show_card(card, revealed, "B1: pokaz   B2: umiem")

    try:
        while True:
            event = buttons.events.get()
            if event == "button1_short":
                if not revealed:
                    revealed = True
                else:
                    store.mark_again(card.id)
                    card = store.next_card(exclude_id=card.id)
                    revealed = False
                display.show_card(card, revealed, "B1: dalej   B2: umiem")
            elif event == "button2_short":
                store.mark_known(card.id)
                card = store.next_card(exclude_id=card.id)
                revealed = False
                display.show_card(card, revealed, "zapisano: umiem")
            elif event == "button1_long":
                display.show_card(card, revealed, "PL -> EN: kolejna wersja")
            elif event == "button2_long":
                display.show_card(card, revealed, "tryby 2 i 3: kolejna wersja")
    except KeyboardInterrupt:
        pass
    finally:
        buttons.close()
        display.close()

