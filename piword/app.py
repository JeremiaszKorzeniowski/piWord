from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

from .cards import (
    DAILY_GOAL,
    MODE_LABELS,
    REVIEW_ALGORITHM_LOOP,
    REVERSE_MODE_LABELS,
    SESSION_SIZE,
    TOPIC_LABELS,
    Card,
    CardStore,
)
from .display import WaveshareDisplay


LEARNED_HOLD_SECONDS = 3.0
RESET_HOLD_SECONDS = 10.0
DOUBLE_CLICK_SECONDS = 0.45
REPEAT_GAP_AGAIN = 3
REPEAT_GAP_DIFFICULT = 1


class StudySession:
    def __init__(self, cards: list[Card]):
        self.queue = list(cards)
        self.total = len(cards)
        self.completed = 0
        self.current = self._take_next()

    def _take_next(self) -> Card | None:
        return self.queue.pop(0) if self.queue else None

    @property
    def remaining(self) -> int:
        return len(self.queue) + (1 if self.current is not None else 0)

    def repeat(self, gap: int) -> Card | None:
        if self.current is None:
            return None
        self.queue.insert(min(max(0, gap), len(self.queue)), self.current)
        self.current = self._take_next()
        return self.current

    def known(self) -> Card | None:
        if self.current is None:
            return None
        self.completed += 1
        self.current = self._take_next()
        return self.current


class ButtonEvents:
    def __init__(self):
        from gpiozero import Button

        self.events: queue.Queue[str] = queue.Queue()
        self.pressed_at: dict[str, float] = {}
        self.suppressed_releases: set[str] = set()
        self.combo_timer: threading.Timer | None = None
        self.button1_click_timer: threading.Timer | None = None
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

    def _released(self, name: str) -> None:
        combo_short = False
        suppressed_release = False
        with self.lock:
            started = self.pressed_at.pop(name, time.monotonic())
            if name in self.suppressed_releases:
                suppressed_release = True
                if self.combo_timer is not None:
                    self.combo_timer.cancel()
                    self.combo_timer = None
                    combo_short = True
                self.suppressed_releases.discard(name)
            elif name in ("button2", "button3") and self.combo_timer is not None:
                self.combo_timer.cancel()
                self.combo_timer = None
        if suppressed_release:
            if combo_short:
                self.events.put("button23_short")
            return
        duration = time.monotonic() - started
        if duration >= LEARNED_HOLD_SECONDS:
            if name == "button1":
                self._cancel_button1_click()
            self.events.put(f"{name}_long")
        elif name == "button1":
            self._button1_click()
        else:
            self.events.put(f"{name}_short")

    def _button1_click(self) -> None:
        with self.lock:
            if self.button1_click_timer is not None:
                self.button1_click_timer.cancel()
                self.button1_click_timer = None
                self.events.put("button1_double")
                return
            self.button1_click_timer = threading.Timer(
                DOUBLE_CLICK_SECONDS, self._emit_button1_short
            )
            self.button1_click_timer.daemon = True
            self.button1_click_timer.start()

    def _emit_button1_short(self) -> None:
        with self.lock:
            self.button1_click_timer = None
        self.events.put("button1_short")

    def _cancel_button1_click(self) -> None:
        with self.lock:
            if self.button1_click_timer is not None:
                self.button1_click_timer.cancel()
                self.button1_click_timer = None

    def _reset_combo(self) -> None:
        with self.lock:
            self.combo_timer = None
            if "button2" in self.pressed_at and "button3" in self.pressed_at:
                self.events.put("reset_progress")

    def close(self) -> None:
        with self.lock:
            if self.combo_timer is not None:
                self.combo_timer.cancel()
            if self.button1_click_timer is not None:
                self.button1_click_timer.cancel()
        for button in self.buttons.values():
            button.close()


def _next_for_mode(
    store: CardStore,
    mode: str,
    level: str | None,
    topic: str | None,
    exclude_id: int | None = None,
) -> tuple[Card, str | None]:
    try:
        return (
            store.next_card(
                mode=mode, level=level, topic=topic, exclude_id=exclude_id
            ),
            level,
        )
    except RuntimeError:
        if level is not None:
            return (
                store.next_card(
                    mode=mode, level=None, topic=topic, exclude_id=exclude_id
                ),
                None,
            )
        raise


def run_hardware(database_path: Path) -> None:
    store = CardStore(database_path)
    store.initialize()
    display = WaveshareDisplay()
    buttons = ButtonEvents()
    algorithm = store.review_algorithm()
    mode = store.available_modes()[0]
    level: str | None = None
    topic: str | None = None
    reversed_direction = False
    session: StudySession | None = None
    if algorithm == REVIEW_ALGORITHM_LOOP:
        session = StudySession(
            store.session_cards(mode=mode, level=level, topic=topic, limit=SESSION_SIZE)
        )
        card = session.current
    else:
        card, level = _next_for_mode(store, mode, level, topic)
    revealed = False

    def show_empty(title: str = "BRAK POWTOREK") -> None:
        display.show_status(
            title,
            [
                f"Jezyk: {MODE_LABELS[mode]}",
                f"Poziom: {level or 'ALL'}",
                f"Temat: {TOPIC_LABELS.get(topic, 'WSZYSTKIE')}",
                "Brak kart na teraz",
                "B1: sprawdz ponownie",
            ],
        )

    def show_current(message: str = "") -> None:
        if card is None:
            show_empty()
        else:
            display.show_card(card, revealed, message, reversed_direction, topic)

    def restart_selection(message: str) -> None:
        nonlocal card, level, session, revealed
        revealed = False
        if algorithm == REVIEW_ALGORITHM_LOOP:
            session = StudySession(
                store.session_cards(
                    mode=mode, level=level, topic=topic, limit=SESSION_SIZE
                )
            )
            card = session.current
        else:
            card, level = _next_for_mode(store, mode, level, topic)
        show_current(message)

    if card is None:
        show_empty()
    else:
        initial_message = (
            f"sesja: {session.remaining}/{session.total}"
            if session is not None
            else "B1: pokaz  B2: poziom  B3: jezyk"
        )
        show_current(initial_message)

    try:
        while True:
            event = buttons.events.get()
            if event == "button1_short":
                if card is None:
                    restart_selection("nowa sesja")
                    continue
                if not revealed:
                    store.mark_seen(card.id)
                    revealed = True
                    message = (
                        f"sesja: {session.remaining}/{session.total}"
                        if session is not None
                        else ""
                    )
                else:
                    store.mark_again(card.id)
                    if session is not None:
                        card = session.repeat(REPEAT_GAP_AGAIN)
                        message = f"jeszcze raz; zostalo {session.remaining}"
                    else:
                        card, level = _next_for_mode(
                            store, mode, level, topic, card.id
                        )
                        stats = store.statistics()
                        message = f"dzis: {stats['today']}/{DAILY_GOAL}"
                    revealed = False
                show_current(message)
            elif event == "button1_double":
                if card is None:
                    show_empty()
                    continue
                difficult = store.toggle_difficult(card.id)
                if session is not None and revealed and difficult:
                    store.mark_again(card.id)
                    card = session.repeat(REPEAT_GAP_DIFFICULT)
                    revealed = False
                    message = f"trudne; zostalo {session.remaining}"
                else:
                    message = (
                        "oznaczono: trudne"
                        if difficult
                        else "usunieto oznaczenie: trudne"
                    )
                show_current(message)
            elif event == "button1_long":
                if card is None:
                    show_empty()
                    continue
                if session is not None:
                    store.mark_seen(card.id)
                    store.mark_known(card.id)
                    card = session.known()
                    if card is None:
                        revealed = False
                        display.show_status(
                            "SESJA UKONCZONA",
                            [
                                f"Opanowane: {session.completed}/{session.total}",
                                "Powtorki zaplanowane",
                                "B1: sprawdz nowa sesje",
                            ],
                        )
                        continue
                    message = f"umiem; zostalo {session.remaining}"
                else:
                    store.mark_learned(card.id)
                    try:
                        card, level = _next_for_mode(
                            store, mode, level, topic, card.id
                        )
                        message = "ukryto: umiem"
                    except RuntimeError:
                        for candidate in store.available_modes():
                            try:
                                candidate_topic = (
                                    topic
                                    if topic in store.available_topics(candidate)
                                    else None
                                )
                                card, level = _next_for_mode(
                                    store, candidate, None, candidate_topic
                                )
                                mode = candidate
                                topic = candidate_topic
                                break
                            except RuntimeError:
                                continue
                        message = "ukryto; brak kolejnych w grupie"
                revealed = False
                show_current(message)
            elif event == "button3_short":
                modes = store.available_modes()
                start = modes.index(mode) if mode in modes else -1
                candidate = modes[(start + 1) % len(modes)]
                candidate_topic = (
                    topic if topic in store.available_topics(candidate) else None
                )
                mode, level, topic = candidate, None, candidate_topic
                if mode not in REVERSE_MODE_LABELS:
                    reversed_direction = False
                restart_selection(f"jezyk: {MODE_LABELS[mode]}")
            elif event == "button3_long":
                if mode in REVERSE_MODE_LABELS:
                    reversed_direction = not reversed_direction
                    revealed = False
                    direction = (
                        REVERSE_MODE_LABELS[mode]
                        if reversed_direction
                        else MODE_LABELS[mode]
                    )
                    message = f"kierunek: {direction}"
                else:
                    message = "ten tryb ma jeden kierunek"
                show_current(message)
            elif event == "button2_short":
                choices: list[str | None] = [
                    None,
                    *store.available_levels(mode, topic),
                ]
                current = choices.index(level) if level in choices else 0
                level = choices[(current + 1) % len(choices)]
                restart_selection(f"poziom: {level or 'ALL'}")
            elif event == "button23_short":
                choices = [None, *store.available_topics(mode)]
                current = choices.index(topic) if topic in choices else 0
                topic = choices[(current + 1) % len(choices)]
                restart_selection(
                    f"zbior: {TOPIC_LABELS.get(topic, 'WSZYSTKIE')}"
                )
            elif event == "button2_long":
                stats = store.statistics(mode=mode, level=level, topic=topic)
                display.show_status(
                    "STATYSTYKI",
                    [
                        f"Jezyk: {MODE_LABELS[mode]}",
                        f"Poziom: {level or 'ALL'}",
                        f"Temat: {TOPIC_LABELS.get(topic, 'WSZYSTKIE')}",
                        f"Dzisiaj w zakresie: {stats['today']}",
                        f"Umiem: {stats['learned']}  Trudne: {stats['difficult']}",
                        f"W zbiorze: {stats['total']}",
                    ],
                )
            elif event == "reset_progress":
                reset_count = store.reset_progress()
                restart_selection(f"reset: przywrocono {reset_count}")
    except KeyboardInterrupt:
        pass
    finally:
        buttons.close()
        display.close()
