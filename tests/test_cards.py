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


if __name__ == "__main__":
    unittest.main()

