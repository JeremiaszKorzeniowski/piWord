from __future__ import annotations

import csv
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


MODE_EN_PL = "en_pl"
MODE_RU_PL = "ru_pl"
MODE_ES_PL = "es_pl"
MODES = (MODE_EN_PL, MODE_RU_PL, MODE_ES_PL)
MODE_LABELS = {
    MODE_EN_PL: "EN -> PL",
    MODE_RU_PL: "RU -> PL",
    MODE_ES_PL: "ES -> PL",
}
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2", "OTHER")


@dataclass(frozen=True)
class Card:
    id: int
    mode: str
    front: str
    back: str
    forms: str = ""
    level: str = "OTHER"
    note: str = ""
    source: str = ""


def default_database_path() -> Path:
    return Path.home() / ".local" / "share" / "piword" / "piword.db"


def default_seed_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "seed_en_pl.csv"


def default_irregular_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "irregular_verbs_en_pl.csv"


class CardStore:
    def __init__(self, path: Path):
        self.path = Path(path).expanduser()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self, seed_path: Path | None = None) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY,
                    mode TEXT NOT NULL,
                    front TEXT NOT NULL,
                    back TEXT NOT NULL,
                    forms TEXT NOT NULL DEFAULT '',
                    level TEXT NOT NULL DEFAULT 'OTHER',
                    note TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    streak INTEGER NOT NULL DEFAULT 0,
                    seen_count INTEGER NOT NULL DEFAULT 0,
                    correct_count INTEGER NOT NULL DEFAULT 0,
                    due_at INTEGER NOT NULL DEFAULT 0,
                    learned INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(mode, front, back)
                );
                CREATE INDEX IF NOT EXISTS cards_due_idx ON cards(mode, due_at);
                """
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(cards)").fetchall()
            }
            if "forms" not in columns:
                connection.execute(
                    "ALTER TABLE cards ADD COLUMN forms TEXT NOT NULL DEFAULT ''"
                )
            if "level" not in columns:
                connection.execute(
                    "ALTER TABLE cards ADD COLUMN level TEXT NOT NULL DEFAULT 'OTHER'"
                )
            if "learned" not in columns:
                connection.execute(
                    "ALTER TABLE cards ADD COLUMN learned INTEGER NOT NULL DEFAULT 0"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS cards_level_due_idx ON cards(mode, level, due_at)"
            )
            count = connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        if count == 0:
            self.import_csv(seed_path or default_seed_path(), source="piWord seed v1")
        self.import_irregular_csv(default_irregular_path())

    def import_csv(self, path: Path, source: str) -> int:
        rows: list[tuple[str, str, str, str, str, str, str]] = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                front = row.get("front", "").strip()
                back = row.get("back", "").strip()
                if front and back:
                    rows.append(
                        (
                            MODE_EN_PL,
                            front,
                            back,
                            row.get("forms", "").strip(),
                            row.get("level", "OTHER").strip().upper() or "OTHER",
                            row.get("note", "").strip(),
                            source,
                        )
                    )
        return self.add_cards(rows)

    def import_irregular_csv(self, path: Path) -> int:
        rows: list[tuple[str, str, str, str, str, str, str]] = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                front = row.get("front", "").strip()
                back = row.get("back", "").strip()
                forms = row.get("forms", "").strip()
                if front and back and forms:
                    rows.append(
                        (
                            MODE_EN_PL,
                            front,
                            back,
                            forms,
                            "OTHER",
                            "irregular verb",
                            "piWord irregular verbs",
                        )
                    )
        with self.connect() as connection:
            before = connection.total_changes
            connection.executemany(
                """
                INSERT INTO cards(mode, front, back, forms, level, note, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mode, front, back) DO UPDATE SET
                    forms = excluded.forms,
                    note = excluded.note
                """,
                rows,
            )
            return connection.total_changes - before

    def add_cards(self, rows: Iterable[tuple[str, str, str, str, str, str, str]]) -> int:
        with self.connect() as connection:
            before = connection.total_changes
            connection.executemany(
                """
                INSERT OR IGNORE INTO cards(mode, front, back, forms, level, note, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            return connection.total_changes - before

    def assign_levels(self, levels: dict[str, str], mode: str = MODE_EN_PL) -> int:
        rows = [(level, mode, headword.casefold()) for headword, level in levels.items()]
        with self.connect() as connection:
            before = connection.total_changes
            connection.executemany(
                "UPDATE cards SET level = ? WHERE mode = ? AND lower(front) = ?",
                rows,
            )
            return connection.total_changes - before

    def level_counts(self, mode: str = MODE_EN_PL) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT level, COUNT(*) AS count FROM cards WHERE mode = ? GROUP BY level",
                (mode,),
            ).fetchall()
        return {str(row["level"]): int(row["count"]) for row in rows}

    def next_card(
        self,
        mode: str = MODE_EN_PL,
        exclude_id: int | None = None,
        level: str | None = None,
    ) -> Card:
        now = int(time.time())
        query = """
            SELECT id, mode, front, back, forms, level, note, source
            FROM cards
            WHERE mode = ? AND learned = 0
              AND (? IS NULL OR level = ?) AND (? IS NULL OR id != ?)
            ORDER BY CASE WHEN due_at <= ? THEN 0 ELSE 1 END,
                     due_at,
                     RANDOM()
            LIMIT 1
        """
        with self.connect() as connection:
            row = connection.execute(
                query, (mode, level, level, exclude_id, exclude_id, now)
            ).fetchone()
            if row is None and exclude_id is not None:
                row = connection.execute(
                    """SELECT id, mode, front, back, forms, level, note, source
                       FROM cards
                       WHERE mode = ? AND learned = 0 AND (? IS NULL OR level = ?)
                       LIMIT 1""",
                    (mode, level, level),
                ).fetchone()
        if row is None:
            raise RuntimeError(f"Brak fiszek dla trybu {mode}")
        return Card(**dict(row))

    def mark_known(self, card_id: int) -> None:
        now = int(time.time())
        with self.connect() as connection:
            row = connection.execute("SELECT streak FROM cards WHERE id = ?", (card_id,)).fetchone()
            if row is None:
                return
            streak = min(int(row[0]) + 1, 7)
            intervals = (1, 2, 4, 7, 14, 30, 60)
            due_at = now + intervals[streak - 1] * 86400
            connection.execute(
                """UPDATE cards
                   SET streak = ?, seen_count = seen_count + 1,
                       correct_count = correct_count + 1, due_at = ?
                   WHERE id = ?""",
                (streak, due_at, card_id),
            )

    def mark_learned(self, card_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """UPDATE cards
                   SET learned = 1, seen_count = seen_count + 1,
                       correct_count = correct_count + 1
                   WHERE id = ?""",
                (card_id,),
            )

    def available_modes(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT mode FROM cards ORDER BY mode"
            ).fetchall()
        present = {str(row[0]) for row in rows}
        return [mode for mode in MODES if mode in present]

    def available_levels(self, mode: str) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT DISTINCT level FROM cards
                   WHERE mode = ? AND learned = 0""",
                (mode,),
            ).fetchall()
        present = {str(row[0]) for row in rows}
        return [level for level in LEVELS if level in present]

    def reset_progress(self) -> int:
        with self.connect() as connection:
            learned = connection.execute(
                "SELECT COUNT(*) FROM cards WHERE learned != 0"
            ).fetchone()[0]
            connection.execute(
                """UPDATE cards SET learned = 0, streak = 0, seen_count = 0,
                   correct_count = 0, due_at = 0"""
            )
        return int(learned)

    def mark_again(self, card_id: int) -> None:
        due_at = int(time.time()) + 600
        with self.connect() as connection:
            connection.execute(
                """UPDATE cards
                   SET streak = 0, seen_count = seen_count + 1, due_at = ?
                   WHERE id = ?""",
                (due_at, card_id),
            )

