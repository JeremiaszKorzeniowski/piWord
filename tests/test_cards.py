from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import queue
import threading
import time
from tempfile import TemporaryDirectory
import unittest

from piword.app import ButtonEvents, StudySession
from piword.cards import (
    REVIEW_ALGORITHM_LEGACY,
    REVIEW_ALGORITHM_LOOP,
    SESSION_SIZE,
    TOPICS,
    Card,
    CardStore,
)
from piword.display import card_header
from tools.db_view import thematic_statistics


class CardStoreTests(unittest.TestCase):
    def test_header_always_includes_card_collection(self):
        other = Card(id=1, mode="en_pl", front="go", back="iść", level="OTHER")
        beginner = Card(id=2, mode="en_pl", front="cat", back="kot", level="A1")

        self.assertEqual(card_header(other), "EN -> PL  INNE  WSZYSTKIE")
        self.assertEqual(card_header(beginner), "EN -> PL  A1  WSZYSTKIE")
        self.assertEqual(
            card_header(beginner, reversed_direction=True, topic="COLORS"),
            "PL -> EN  A1  KOLORY",
        )

    def test_initialize_and_progress(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()
            first = store.next_card()
            self.assertTrue(first.front)
            self.assertTrue(first.back)
            store.mark_known(first.id)
            second = store.next_card(exclude_id=first.id)
            self.assertNotEqual(first.id, second.id)
            store.mark_again(second.id)

    def test_irregular_verbs_include_three_forms(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()
            with store.connect() as connection:
                row = connection.execute(
                    "SELECT front, forms FROM cards WHERE front = 'go'"
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[1], "went - gone")

    def test_levels_can_be_assigned_and_filtered(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()
            changed = store.assign_levels({"go": "C2"})
            self.assertGreaterEqual(changed, 1)
            card = store.next_card(level="C2")
            self.assertEqual(card.front, "go")
            self.assertEqual(card.level, "C2")

    def test_learned_cards_are_hidden_and_reset_restores_them(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()
            card = store.next_card()
            store.mark_learned(card.id)
            following = store.next_card(exclude_id=card.id)
            self.assertNotEqual(card.id, following.id)
            self.assertEqual(store.reset_progress(), 1)
            with store.connect() as connection:
                progress = connection.execute(
                    "SELECT learned FROM card_progress WHERE card_id = ?", (card.id,)
                ).fetchone()
            self.assertIsNone(progress)

    def test_polish_modes_examples_and_daily_statistics(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()
            self.assertIn("pl_dict", store.available_modes())
            card = store.next_card(mode="pl_dict")
            self.assertTrue(card.example)
            self.assertTrue(store.mark_seen(card.id))
            self.assertFalse(store.mark_seen(card.id))
            self.assertTrue(store.toggle_difficult(card.id))
            stats = store.statistics()
            self.assertEqual(stats["today"], 1)
            self.assertEqual(stats["difficult"], 1)

    def test_thematic_sets_exist_for_each_foreign_language(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()

            for mode in ("en_pl", "ru_pl", "es_pl"):
                self.assertEqual(store.available_topics(mode), list(TOPICS))
                days = store.next_card(mode=mode, topic="DAYS")
                self.assertEqual(days.level, "A1")
                with store.connect() as connection:
                    counts = {
                        row[0]: row[1]
                        for row in connection.execute(
                            """SELECT card_topics.topic, COUNT(*)
                               FROM card_topics
                               JOIN cards ON cards.id = card_topics.card_id
                               WHERE cards.mode = ?
                               GROUP BY card_topics.topic""",
                            (mode,),
                        )
                    }
                for topic in TOPICS:
                    self.assertGreaterEqual(counts[topic], 7)

    def test_topic_and_level_filters_work_together(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()

            card = store.next_card(mode="en_pl", level="A1", topic="COLORS")
            self.assertEqual(card.level, "A1")
            with store.connect() as connection:
                topics = {
                    row[0]
                    for row in connection.execute(
                        "SELECT topic FROM card_topics WHERE card_id = ?", (card.id,)
                    )
                }
            self.assertIn("COLORS", topics)
            self.assertEqual(store.available_levels("en_pl", "DAYS"), ["A1"])

    def test_statistics_can_be_filtered_by_language_level_and_topic(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()
            card = store.next_card(mode="en_pl", level="A1", topic="COLORS")
            store.mark_seen(card.id)
            store.mark_learned(card.id)

            stats = store.statistics(mode="en_pl", level="A1", topic="COLORS")
            self.assertGreater(stats["total"], 0)
            self.assertEqual(stats["learned"], 1)
            self.assertEqual(stats["today"], 1)

            output = StringIO()
            with store.connect() as connection, redirect_stdout(output):
                thematic_statistics(connection, mode="en_pl", topic="COLORS")
            report = output.getvalue()
            self.assertIn("EN -> PL", report)
            self.assertIn("KOLORY", report)
            self.assertIn("postep", report)

    def test_review_algorithm_is_stored_but_hidden_from_the_ui(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()
            self.assertEqual(store.review_algorithm(), REVIEW_ALGORITHM_LOOP)
            store.set_review_algorithm(REVIEW_ALGORITHM_LEGACY)
            store.initialize()
            self.assertEqual(store.review_algorithm(), REVIEW_ALGORITHM_LEGACY)
            with self.assertRaises(ValueError):
                store.set_review_algorithm("unknown")

    def test_session_prioritizes_due_cards_and_limits_new_words(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()
            cards = store.session_cards(limit=SESSION_SIZE)
            self.assertEqual(len(cards), SESSION_SIZE)

            for card in cards:
                store.mark_seen(card.id)
                store.mark_known(card.id)

            self.assertEqual(store.session_cards(limit=SESSION_SIZE), [])

    def test_known_word_gets_spaced_review_instead_of_permanent_hiding(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()
            card = store.session_cards(limit=1)[0]
            store.mark_seen(card.id)
            before = int(time.time())
            store.mark_known(card.id)

            with store.connect() as connection:
                row = connection.execute(
                    """SELECT streak, due_at, learned FROM card_progress
                       WHERE profile_id = ? AND card_id = ?""",
                    (store.active_profile().id, card.id),
                ).fetchone()
            self.assertEqual(row[0], 1)
            self.assertGreaterEqual(row[1], before + 86400)
            self.assertLessEqual(row[1], before + 86405)
            self.assertEqual(row[2], 0)

    def test_profiles_keep_progress_statistics_and_algorithm_separate(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()
            default = store.active_profile()
            card = store.next_card(mode="en_pl", topic="COLORS")
            store.mark_seen(card.id)
            store.mark_known(card.id)
            store.toggle_difficult(card.id)
            store.set_review_algorithm(REVIEW_ALGORITHM_LEGACY)

            second = store.create_profile("Ania")
            store.set_active_profile(second.id)
            self.assertEqual(store.active_profile(), second)
            self.assertEqual(store.statistics()["learned"], 0)
            self.assertEqual(store.statistics()["difficult"], 0)
            self.assertEqual(store.review_algorithm(), REVIEW_ALGORITHM_LOOP)

            store.mark_learned(card.id)
            self.assertEqual(store.statistics()["learned"], 1)
            store.set_active_profile(default.id)
            self.assertEqual(store.review_algorithm(), REVIEW_ALGORITHM_LEGACY)
            self.assertEqual(store.statistics()["difficult"], 1)

    def test_reset_clears_only_active_profile(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()
            default = store.active_profile()
            card = store.next_card()
            store.mark_learned(card.id)

            second = store.create_profile("Bartek")
            store.set_active_profile(second.id)
            store.mark_learned(card.id)
            self.assertEqual(store.reset_progress(), 1)
            self.assertEqual(store.statistics()["learned"], 0)

            store.set_active_profile(default.id)
            self.assertEqual(store.statistics()["learned"], 1)

    def test_existing_single_user_progress_is_migrated_to_default_profile(self):
        with TemporaryDirectory() as directory:
            store = CardStore(Path(directory) / "cards.db")
            store.initialize()
            card = store.next_card()
            with store.connect() as connection:
                connection.execute(
                    """UPDATE cards SET streak = 2, seen_count = 3,
                       correct_count = 2, learned = 1, difficult = 1,
                       introduced_on = '2026-11-17' WHERE id = ?""",
                    (card.id,),
                )
                connection.execute("DELETE FROM card_progress")
                connection.execute(
                    "DELETE FROM settings WHERE key = 'profile_progress_migrated'"
                )

            store.initialize()
            with store.connect() as connection:
                row = connection.execute(
                    """SELECT streak, seen_count, learned, difficult, introduced_on
                       FROM card_progress WHERE profile_id = 1 AND card_id = ?""",
                    (card.id,),
                ).fetchone()
            self.assertEqual(tuple(row), (2, 3, 1, 1, "2026-11-17"))


class StudySessionTests(unittest.TestCase):
    def test_again_reinserts_word_after_three_other_cards(self):
        cards = [Card(id=index, mode="en_pl", front=str(index), back=str(index)) for index in range(1, 6)]
        session = StudySession(cards)

        self.assertEqual(session.current.id, 1)
        session.repeat(3)
        self.assertEqual(session.current.id, 2)
        session.known()
        self.assertEqual(session.current.id, 3)
        session.known()
        self.assertEqual(session.current.id, 4)
        session.known()
        self.assertEqual(session.current.id, 1)
        self.assertEqual(session.remaining, 2)


class ButtonEventTests(unittest.TestCase):
    def make_events(self):
        events = ButtonEvents.__new__(ButtonEvents)
        events.events = queue.Queue()
        events.pressed_at = {}
        events.suppressed_releases = set()
        events.combo_timer = None
        events.button1_click_timer = None
        events.lock = threading.Lock()
        return events

    def test_short_button2_button3_combo_emits_topic_change_only(self):
        events = self.make_events()
        events._pressed("button2")
        events._pressed("button3")
        events._released("button2")
        events._released("button3")

        self.assertEqual(events.events.get_nowait(), "button23_short")
        self.assertTrue(events.events.empty())

    def test_each_physical_button_emits_its_own_short_event(self):
        for name in ("button1", "button2", "button3"):
            with self.subTest(name=name):
                events = self.make_events()
                events._pressed(name)
                events._released(name)
                if name == "button1":
                    events._cancel_button1_click()
                    events._emit_button1_short()
                self.assertEqual(events.events.get_nowait(), f"{name}_short")
                self.assertTrue(events.events.empty())

    def test_each_physical_button_emits_its_own_long_event(self):
        for name in ("button1", "button2", "button3"):
            with self.subTest(name=name):
                events = self.make_events()
                events.pressed_at[name] = time.monotonic() - 3.1
                events._released(name)
                self.assertEqual(events.events.get_nowait(), f"{name}_long")
                self.assertTrue(events.events.empty())

    def test_ten_second_combo_emits_reset_only(self):
        events = self.make_events()
        events._pressed("button2")
        events._pressed("button3")
        events.combo_timer.cancel()
        events._reset_combo()
        events._released("button2")
        events._released("button3")

        self.assertEqual(events.events.get_nowait(), "reset_progress")
        self.assertTrue(events.events.empty())


if __name__ == "__main__":
    unittest.main()

