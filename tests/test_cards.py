from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from piword.cards import CardStore


class CardStoreTests(unittest.TestCase):
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
            changed = store.assign_levels({"go": "A1"})
            self.assertGreaterEqual(changed, 1)
            card = store.next_card(level="A1")
            self.assertEqual(card.front, "go")
            self.assertEqual(card.level, "A1")


if __name__ == "__main__":
    unittest.main()

