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
MODE_PL_DICT = "pl_dict"
MODE_PL_FOREIGN = "pl_foreign"
MODES = (MODE_EN_PL, MODE_RU_PL, MODE_ES_PL, MODE_PL_DICT, MODE_PL_FOREIGN)
MODE_LABELS = {
    MODE_EN_PL: "EN -> PL",
    MODE_RU_PL: "RU -> PL",
    MODE_ES_PL: "ES -> PL",
    MODE_PL_DICT: "SJP",
    MODE_PL_FOREIGN: "OBCE",
}
REVERSE_MODE_LABELS = {
    MODE_EN_PL: "PL -> EN",
    MODE_RU_PL: "PL -> RU",
    MODE_ES_PL: "PL -> ES",
}
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2", "TRUDNE", "OBCE", "OTHER")
TOPICS = (
    "DAYS",
    "MONTHS",
    "NUMBERS",
    "COLORS",
    "ADJECTIVES",
    "IRREGULAR",
    "FAMILY",
    "FOOD",
    "HOME",
    "BODY",
    "CLOTHES",
    "ANIMALS",
    "WEATHER",
    "TRAVEL",
    "VERBS",
    "GREETINGS",
    "TIME",
    "SCHOOL",
    "WORK",
    "SHOPPING",
    "HEALTH",
    "CHILDHOOD",
    "POLITICS",
    "RELIGION",
    "GEOGRAPHY",
    "WAR",
    "MIGRATION",
    "ECOLOGY",
    "RELATIONSHIPS",
    "MEDIA",
    "TECHNOLOGY",
    "BUSINESS",
    "AGRICULTURE",
    "INDUSTRY",
    "SPORT",
    "SCIENCE",
    "CULTURE",
    "OPINIONS",
)
TOPIC_LABELS = {
    "DAYS": "DNI",
    "MONTHS": "MIESIĄCE",
    "NUMBERS": "LICZBY",
    "COLORS": "KOLORY",
    "ADJECTIVES": "PRZYMIOTNIKI",
    "IRREGULAR": "NIEREGULARNE",
    "FAMILY": "RODZINA",
    "FOOD": "JEDZENIE",
    "HOME": "DOM",
    "BODY": "CIAŁO",
    "CLOTHES": "UBRANIA",
    "ANIMALS": "ZWIERZĘTA",
    "WEATHER": "POGODA",
    "TRAVEL": "PODRÓŻE",
    "VERBS": "CZASOWNIKI",
    "GREETINGS": "ZWROTY",
    "TIME": "CZAS",
    "SCHOOL": "SZKOŁA",
    "WORK": "PRACA",
    "SHOPPING": "ZAKUPY",
    "HEALTH": "ZDROWIE",
    "CHILDHOOD": "DZIECIŃSTWO",
    "POLITICS": "POLITYKA",
    "RELIGION": "RELIGIA",
    "GEOGRAPHY": "GEOGRAFIA",
    "WAR": "WOJNA",
    "MIGRATION": "MIGRACJA",
    "ECOLOGY": "EKOLOGIA",
    "RELATIONSHIPS": "RELACJE",
    "MEDIA": "MEDIA",
    "TECHNOLOGY": "TECHNOLOGIA",
    "BUSINESS": "BIZNES",
    "AGRICULTURE": "ROLNICTWO",
    "INDUSTRY": "PRZEMYSŁ",
    "SPORT": "SPORT",
    "SCIENCE": "NAUKA",
    "CULTURE": "KULTURA",
    "OPINIONS": "OPINIE",
}
DAILY_GOAL = 20
SESSION_SIZE = 20
REVIEW_ALGORITHM_LOOP = "loop"
REVIEW_ALGORITHM_LEGACY = "legacy"
REVIEW_ALGORITHMS = (REVIEW_ALGORITHM_LOOP, REVIEW_ALGORITHM_LEGACY)


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
    example: str = ""


@dataclass(frozen=True)
class Profile:
    id: int
    name: str


def default_database_path() -> Path:
    return Path.home() / ".local" / "share" / "piword" / "piword.db"


def default_seed_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "seed_en_pl.csv"


def default_irregular_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "irregular_verbs_en_pl.csv"


def default_polish_paths() -> tuple[tuple[Path, str, str], ...]:
    data = Path(__file__).resolve().parent.parent / "data"
    return (
        (data / "polish_dictionary.csv", MODE_PL_DICT, "piWord słownik polski"),
        (data / "polish_foreign.csv", MODE_PL_FOREIGN, "piWord wyrazy obce"),
    )


def default_thematic_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "thematic_cards.csv"


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
                    difficult INTEGER NOT NULL DEFAULT 0,
                    introduced_on TEXT,
                    example TEXT NOT NULL DEFAULT '',
                    UNIQUE(mode, front, back)
                );
                CREATE INDEX IF NOT EXISTS cards_due_idx ON cards(mode, due_at);
                CREATE TABLE IF NOT EXISTS card_topics (
                    card_id INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    PRIMARY KEY(card_id, topic),
                    FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS card_topics_topic_idx
                    ON card_topics(topic, card_id);
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT OR IGNORE INTO settings(key, value)
                    VALUES ('review_algorithm', 'loop');
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT OR IGNORE INTO profiles(id, name) VALUES (1, 'Domyślny');
                INSERT OR IGNORE INTO settings(key, value)
                    VALUES ('active_profile_id', '1');
                CREATE TABLE IF NOT EXISTS card_progress (
                    profile_id INTEGER NOT NULL,
                    card_id INTEGER NOT NULL,
                    streak INTEGER NOT NULL DEFAULT 0,
                    seen_count INTEGER NOT NULL DEFAULT 0,
                    correct_count INTEGER NOT NULL DEFAULT 0,
                    due_at INTEGER NOT NULL DEFAULT 0,
                    learned INTEGER NOT NULL DEFAULT 0,
                    difficult INTEGER NOT NULL DEFAULT 0,
                    introduced_on TEXT,
                    PRIMARY KEY(profile_id, card_id),
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                    FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS card_progress_due_idx
                    ON card_progress(profile_id, due_at, difficult);
                CREATE TABLE IF NOT EXISTS profile_settings (
                    profile_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    PRIMARY KEY(profile_id, key),
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );
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
            if "difficult" not in columns:
                connection.execute(
                    "ALTER TABLE cards ADD COLUMN difficult INTEGER NOT NULL DEFAULT 0"
                )
            if "introduced_on" not in columns:
                connection.execute("ALTER TABLE cards ADD COLUMN introduced_on TEXT")
            if "example" not in columns:
                connection.execute(
                    "ALTER TABLE cards ADD COLUMN example TEXT NOT NULL DEFAULT ''"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS cards_level_due_idx ON cards(mode, level, due_at)"
            )
            migrated = connection.execute(
                "SELECT value FROM settings WHERE key = 'profile_progress_migrated'"
            ).fetchone()
            if migrated is None:
                connection.execute(
                    """INSERT OR IGNORE INTO card_progress(
                           profile_id, card_id, streak, seen_count, correct_count,
                           due_at, learned, difficult, introduced_on
                       )
                       SELECT 1, id, streak, seen_count, correct_count,
                              due_at, learned, difficult, introduced_on
                       FROM cards
                       WHERE streak != 0 OR seen_count != 0 OR correct_count != 0
                          OR due_at != 0 OR learned != 0 OR difficult != 0
                          OR introduced_on IS NOT NULL"""
                )
                connection.execute(
                    "INSERT INTO settings(key, value) VALUES ('profile_progress_migrated', '1')"
                )
            connection.execute(
                """INSERT OR IGNORE INTO profile_settings(profile_id, key, value)
                   SELECT 1, 'review_algorithm', value FROM settings
                   WHERE key = 'review_algorithm'"""
            )
            count = connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        if count == 0:
            self.import_csv(seed_path or default_seed_path(), source="piWord seed v1")
        self.import_irregular_csv(default_irregular_path())
        self.import_thematic_csv(default_thematic_path())
        for path, mode, source in default_polish_paths():
            self.import_csv(path, source=source, mode=mode)

    @staticmethod
    def _active_profile_id(connection: sqlite3.Connection) -> int:
        row = connection.execute(
            """SELECT profiles.id FROM profiles
               JOIN settings ON settings.key = 'active_profile_id'
                            AND settings.value = CAST(profiles.id AS TEXT)"""
        ).fetchone()
        if row is not None:
            return int(row[0])
        fallback = connection.execute("SELECT id FROM profiles ORDER BY id LIMIT 1").fetchone()
        if fallback is None:
            connection.execute("INSERT INTO profiles(name) VALUES ('Domyślny')")
            profile_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        else:
            profile_id = int(fallback[0])
        connection.execute(
            """INSERT INTO settings(key, value) VALUES ('active_profile_id', ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (str(profile_id),),
        )
        return profile_id

    @staticmethod
    def _ensure_progress(
        connection: sqlite3.Connection, profile_id: int, card_id: int
    ) -> None:
        connection.execute(
            """INSERT OR IGNORE INTO card_progress(profile_id, card_id)
               SELECT ?, id FROM cards WHERE id = ?""",
            (profile_id, card_id),
        )

    def profiles(self) -> list[Profile]:
        with self.connect() as connection:
            rows = connection.execute("SELECT id, name FROM profiles ORDER BY id").fetchall()
        return [Profile(id=int(row["id"]), name=str(row["name"])) for row in rows]

    def active_profile(self) -> Profile:
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            row = connection.execute(
                "SELECT id, name FROM profiles WHERE id = ?", (profile_id,)
            ).fetchone()
        return Profile(id=int(row["id"]), name=str(row["name"]))

    def create_profile(self, name: str) -> Profile:
        name = name.strip()
        if not name:
            raise ValueError("Nazwa profilu nie moze byc pusta")
        with self.connect() as connection:
            cursor = connection.execute("INSERT INTO profiles(name) VALUES (?)", (name,))
            profile_id = int(cursor.lastrowid)
            connection.execute(
                """INSERT INTO profile_settings(profile_id, key, value)
                   VALUES (?, 'review_algorithm', ?)""",
                (profile_id, REVIEW_ALGORITHM_LOOP),
            )
        return Profile(id=profile_id, name=name)

    def set_active_profile(self, profile_id: int) -> Profile:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, name FROM profiles WHERE id = ?", (profile_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Nieznany profil: {profile_id}")
            connection.execute(
                """INSERT INTO settings(key, value) VALUES ('active_profile_id', ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (str(profile_id),),
            )
        return Profile(id=int(row["id"]), name=str(row["name"]))

    def import_csv(self, path: Path, source: str, mode: str = MODE_EN_PL) -> int:
        rows: list[tuple[str, str, str, str, str, str, str, str]] = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                front = row.get("front", "").strip()
                back = row.get("back", "").strip()
                if front and back:
                    rows.append(
                        (
                            mode,
                            front,
                            back,
                            row.get("forms", "").strip(),
                            row.get("level", "OTHER").strip().upper() or "OTHER",
                            row.get("note", "").strip(),
                            source,
                            row.get("example", "").strip(),
                        )
                    )
        return self.add_cards(rows)

    def import_irregular_csv(self, path: Path) -> int:
        rows: list[tuple[str, str, str, str, str, str, str, str]] = []
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
                            row.get("level", "OTHER").strip().upper() or "OTHER",
                            "irregular verb",
                            "piWord irregular verbs",
                            "",
                        )
                    )
        with self.connect() as connection:
            before = connection.total_changes
            connection.executemany(
                """
                INSERT INTO cards(mode, front, back, forms, level, note, source, example)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mode, front, back) DO UPDATE SET
                    forms = excluded.forms,
                    level = CASE
                        WHEN cards.level = 'OTHER' THEN excluded.level
                        ELSE cards.level
                    END,
                    note = excluded.note
                """,
                rows,
            )
            connection.execute(
                """INSERT OR IGNORE INTO card_topics(card_id, topic)
                   SELECT id, 'IRREGULAR' FROM cards
                   WHERE mode = ? AND note = 'irregular verb'""",
                (MODE_EN_PL,),
            )
            return connection.total_changes - before

    def import_thematic_csv(self, path: Path) -> int:
        rows: list[tuple[str, str, str, str, str, str, str, str, str]] = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                mode = row.get("mode", "").strip()
                front = row.get("front", "").strip()
                back = row.get("back", "").strip()
                topic = row.get("topic", "").strip().upper()
                if mode in MODES and front and back and topic in TOPICS:
                    rows.append(
                        (
                            mode,
                            front,
                            back,
                            row.get("forms", "").strip(),
                            row.get("level", "OTHER").strip().upper() or "OTHER",
                            row.get("note", "").strip(),
                            "piWord thematic sets",
                            row.get("example", "").strip(),
                            topic,
                        )
                    )
        with self.connect() as connection:
            before = connection.total_changes
            for mode, front, back, forms, level, note, source, example, topic in rows:
                connection.execute(
                    """INSERT INTO cards(
                           mode, front, back, forms, level, note, source, example
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(mode, front, back) DO UPDATE SET
                           forms = CASE
                               WHEN excluded.forms != '' THEN excluded.forms
                               ELSE cards.forms
                           END,
                           level = CASE
                               WHEN cards.level = 'OTHER' THEN excluded.level
                               ELSE cards.level
                           END,
                           note = CASE
                               WHEN excluded.note != '' THEN excluded.note
                               ELSE cards.note
                           END,
                           example = CASE
                               WHEN excluded.example != '' THEN excluded.example
                               ELSE cards.example
                           END""",
                    (mode, front, back, forms, level, note, source, example),
                )
                connection.execute(
                    """INSERT OR IGNORE INTO card_topics(card_id, topic)
                       SELECT id, ? FROM cards
                       WHERE mode = ? AND front = ? AND back = ?""",
                    (topic, mode, front, back),
                )
            return connection.total_changes - before

    def add_cards(
        self, rows: Iterable[tuple[str, str, str, str, str, str, str, str]]
    ) -> int:
        with self.connect() as connection:
            before = connection.total_changes
            connection.executemany(
                """
                INSERT INTO cards(mode, front, back, forms, level, note, source, example)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mode, front, back) DO UPDATE SET
                    forms = CASE WHEN excluded.forms != '' THEN excluded.forms ELSE cards.forms END,
                    level = excluded.level,
                    note = CASE WHEN excluded.note != '' THEN excluded.note ELSE cards.note END,
                    source = excluded.source,
                    example = CASE WHEN excluded.example != '' THEN excluded.example ELSE cards.example END
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
        topic: str | None = None,
    ) -> Card:
        now = int(time.time())
        query = """
            SELECT cards.id, cards.mode, cards.front, cards.back, cards.forms,
                   cards.level, cards.note, cards.source, cards.example
            FROM cards
            LEFT JOIN card_progress AS progress
              ON progress.card_id = cards.id AND progress.profile_id = ?
            WHERE cards.mode = ? AND COALESCE(progress.learned, 0) = 0
              AND (? IS NULL OR cards.level = ?)
              AND (? IS NULL OR EXISTS (
                  SELECT 1 FROM card_topics
                  WHERE card_id = cards.id AND topic = ?
              ))
              AND (? IS NULL OR cards.id != ?)
            ORDER BY CASE WHEN COALESCE(progress.due_at, 0) <= ? THEN 0 ELSE 1 END,
                     COALESCE(progress.difficult, 0) DESC,
                     COALESCE(progress.due_at, 0),
                     RANDOM()
            LIMIT 1
        """
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            row = connection.execute(
                query,
                (
                    profile_id,
                    mode,
                    level,
                    level,
                    topic,
                    topic,
                    exclude_id,
                    exclude_id,
                    now,
                ),
            ).fetchone()
            if row is None and exclude_id is not None:
                row = connection.execute(
                    """SELECT cards.id, cards.mode, cards.front, cards.back, cards.forms,
                              cards.level, cards.note, cards.source, cards.example
                       FROM cards
                       LEFT JOIN card_progress AS progress
                         ON progress.card_id = cards.id AND progress.profile_id = ?
                       WHERE cards.mode = ? AND COALESCE(progress.learned, 0) = 0
                         AND (? IS NULL OR cards.level = ?)
                         AND (? IS NULL OR EXISTS (
                             SELECT 1 FROM card_topics
                             WHERE card_id = cards.id AND topic = ?
                         ))
                       LIMIT 1""",
                    (profile_id, mode, level, level, topic, topic),
                ).fetchone()
        if row is None:
            raise RuntimeError(f"Brak fiszek dla trybu {mode}")
        return Card(**dict(row))

    def session_cards(
        self,
        mode: str = MODE_EN_PL,
        level: str | None = None,
        topic: str | None = None,
        limit: int = SESSION_SIZE,
        daily_new_goal: int = DAILY_GOAL,
    ) -> list[Card]:
        now = int(time.time())
        today = time.strftime("%Y-%m-%d")
        limit = max(1, limit)
        filter_sql = """
            cards.mode = ? AND COALESCE(progress.learned, 0) = 0
            AND (? IS NULL OR cards.level = ?)
            AND (? IS NULL OR EXISTS (
                SELECT 1 FROM card_topics
                WHERE card_id = cards.id AND topic = ?
            ))
        """
        filter_params = (mode, level, level, topic, topic)
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            due_rows = connection.execute(
                f"""SELECT cards.id, cards.mode, cards.front, cards.back, cards.forms,
                           cards.level, cards.note, cards.source, cards.example
                    FROM cards
                    LEFT JOIN card_progress AS progress
                      ON progress.card_id = cards.id AND progress.profile_id = ?
                    WHERE {filter_sql}
                      AND progress.introduced_on IS NOT NULL AND progress.due_at <= ?
                    ORDER BY progress.difficult DESC, progress.due_at, RANDOM()
                    LIMIT ?""",
                (profile_id, *filter_params, now, limit),
            ).fetchall()
            remaining = limit - len(due_rows)
            introduced_today = connection.execute(
                """SELECT COUNT(*) FROM card_progress
                   WHERE profile_id = ? AND introduced_on = ?""",
                (profile_id, today),
            ).fetchone()[0]
            new_limit = min(remaining, max(0, daily_new_goal - int(introduced_today)))
            new_rows = []
            if new_limit:
                new_rows = connection.execute(
                    f"""SELECT cards.id, cards.mode, cards.front, cards.back, cards.forms,
                               cards.level, cards.note, cards.source, cards.example
                        FROM cards
                        LEFT JOIN card_progress AS progress
                          ON progress.card_id = cards.id AND progress.profile_id = ?
                        WHERE {filter_sql} AND progress.introduced_on IS NULL
                        ORDER BY COALESCE(progress.difficult, 0) DESC, RANDOM()
                        LIMIT ?""",
                    (profile_id, *filter_params, new_limit),
                ).fetchall()
        return [Card(**dict(row)) for row in (*due_rows, *new_rows)]

    def review_algorithm(self) -> str:
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            row = connection.execute(
                """SELECT value FROM profile_settings
                   WHERE profile_id = ? AND key = 'review_algorithm'""",
                (profile_id,),
            ).fetchone()
        value = str(row[0]) if row else REVIEW_ALGORITHM_LOOP
        return value if value in REVIEW_ALGORITHMS else REVIEW_ALGORITHM_LOOP

    def set_review_algorithm(self, algorithm: str) -> None:
        if algorithm not in REVIEW_ALGORITHMS:
            raise ValueError(f"Nieznany algorytm powtorek: {algorithm}")
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            connection.execute(
                """INSERT INTO profile_settings(profile_id, key, value)
                   VALUES (?, 'review_algorithm', ?)
                   ON CONFLICT(profile_id, key) DO UPDATE SET value = excluded.value""",
                (profile_id, algorithm),
            )

    def mark_known(self, card_id: int) -> None:
        now = int(time.time())
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            self._ensure_progress(connection, profile_id, card_id)
            row = connection.execute(
                """SELECT streak, difficult FROM card_progress
                   WHERE profile_id = ? AND card_id = ?""",
                (profile_id, card_id),
            ).fetchone()
            if row is None:
                return
            streak = min(int(row[0]) + 1, 6)
            intervals = (1, 3, 7, 14, 30, 60)
            interval_days = intervals[streak - 1]
            if bool(row[1]):
                interval_days = max(1, interval_days // 2)
            due_at = now + interval_days * 86400
            connection.execute(
                """UPDATE card_progress
                   SET streak = ?, seen_count = seen_count + 1,
                       correct_count = correct_count + 1, due_at = ?, learned = 0
                   WHERE profile_id = ? AND card_id = ?""",
                (streak, due_at, profile_id, card_id),
            )

    def mark_learned(self, card_id: int) -> None:
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            self._ensure_progress(connection, profile_id, card_id)
            connection.execute(
                """UPDATE card_progress
                   SET learned = 1, seen_count = seen_count + 1,
                       correct_count = correct_count + 1
                   WHERE profile_id = ? AND card_id = ?""",
                (profile_id, card_id),
            )

    def mark_seen(self, card_id: int) -> bool:
        today = time.strftime("%Y-%m-%d")
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            self._ensure_progress(connection, profile_id, card_id)
            row = connection.execute(
                """SELECT introduced_on FROM card_progress
                   WHERE profile_id = ? AND card_id = ?""",
                (profile_id, card_id),
            ).fetchone()
            if row is None or row[0] is not None:
                return False
            connection.execute(
                """UPDATE card_progress SET introduced_on = ?
                   WHERE profile_id = ? AND card_id = ?""",
                (today, profile_id, card_id),
            )
        return True

    def toggle_difficult(self, card_id: int) -> bool:
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            self._ensure_progress(connection, profile_id, card_id)
            connection.execute(
                """UPDATE card_progress
                   SET difficult = CASE difficult WHEN 0 THEN 1 ELSE 0 END
                   WHERE profile_id = ? AND card_id = ?""",
                (profile_id, card_id),
            )
            row = connection.execute(
                """SELECT difficult FROM card_progress
                   WHERE profile_id = ? AND card_id = ?""",
                (profile_id, card_id),
            ).fetchone()
        return bool(row and row[0])

    def statistics(
        self,
        mode: str | None = None,
        level: str | None = None,
        topic: str | None = None,
    ) -> dict[str, int]:
        today = time.strftime("%Y-%m-%d")
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            row = connection.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN COALESCE(progress.learned, 0) != 0
                                        OR COALESCE(progress.streak, 0) > 0
                                   THEN 1 ELSE 0 END) AS learned,
                          SUM(CASE WHEN COALESCE(progress.difficult, 0) != 0
                                   THEN 1 ELSE 0 END) AS difficult,
                          SUM(CASE WHEN progress.introduced_on = ? THEN 1 ELSE 0 END) AS today
                   FROM cards
                   LEFT JOIN card_progress AS progress
                     ON progress.card_id = cards.id AND progress.profile_id = ?
                   WHERE (? IS NULL OR cards.mode = ?)
                     AND (? IS NULL OR cards.level = ?)
                     AND (? IS NULL OR EXISTS (
                         SELECT 1 FROM card_topics
                         WHERE card_id = cards.id AND topic = ?
                     ))""",
                (today, profile_id, mode, mode, level, level, topic, topic),
            ).fetchone()
        return {name: int(row[name] or 0) for name in ("total", "learned", "difficult", "today")}

    def available_modes(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT mode FROM cards ORDER BY mode"
            ).fetchall()
        present = {str(row[0]) for row in rows}
        return [mode for mode in MODES if mode in present]

    def available_levels(self, mode: str, topic: str | None = None) -> list[str]:
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            rows = connection.execute(
                """SELECT DISTINCT cards.level FROM cards
                   LEFT JOIN card_progress AS progress
                     ON progress.card_id = cards.id AND progress.profile_id = ?
                   WHERE cards.mode = ? AND COALESCE(progress.learned, 0) = 0
                     AND (? IS NULL OR EXISTS (
                         SELECT 1 FROM card_topics
                         WHERE card_id = cards.id AND topic = ?
                     ))""",
                (profile_id, mode, topic, topic),
            ).fetchall()
        present = {str(row[0]) for row in rows}
        return [level for level in LEVELS if level in present]

    def available_topics(self, mode: str) -> list[str]:
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            rows = connection.execute(
                """SELECT DISTINCT card_topics.topic
                   FROM card_topics
                   JOIN cards ON cards.id = card_topics.card_id
                   LEFT JOIN card_progress AS progress
                     ON progress.card_id = cards.id AND progress.profile_id = ?
                   WHERE cards.mode = ? AND COALESCE(progress.learned, 0) = 0""",
                (profile_id, mode),
            ).fetchall()
        present = {str(row[0]) for row in rows}
        return [topic for topic in TOPICS if topic in present]

    def reset_progress(self) -> int:
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            progressed = connection.execute(
                "SELECT COUNT(*) FROM card_progress WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()[0]
            connection.execute(
                "DELETE FROM card_progress WHERE profile_id = ?", (profile_id,)
            )
        return int(progressed)

    def mark_again(self, card_id: int) -> None:
        due_at = int(time.time()) + 600
        with self.connect() as connection:
            profile_id = self._active_profile_id(connection)
            self._ensure_progress(connection, profile_id, card_id)
            connection.execute(
                """UPDATE card_progress
                   SET streak = 0, seen_count = seen_count + 1, due_at = ?
                   WHERE profile_id = ? AND card_id = ?""",
                (due_at, profile_id, card_id),
            )

