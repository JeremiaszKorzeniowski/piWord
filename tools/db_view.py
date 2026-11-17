from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from piword.cards import MODE_LABELS, MODES, TOPICS, TOPIC_LABELS, default_database_path


def open_read_only(path: Path) -> sqlite3.Connection:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Nie znaleziono bazy: {path}")
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def print_table(headers: list[str], values: list[list[str]]) -> None:
    if not values:
        print("Brak wyników.")
        return
    widths = [
        min(60, max(len(header), *(len(row[index]) for row in values)))
        for index, header in enumerate(headers)
    ]
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in values:
        print("  ".join(value[:widths[index]].ljust(widths[index]) for index, value in enumerate(row)))


def print_rows(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("Brak wyników.")
        return
    headers = list(rows[0].keys())
    values = [
        [str(row[name] if row[name] is not None else "") for name in headers]
        for row in rows
    ]
    print_table(headers, values)


def active_profile(connection: sqlite3.Connection) -> tuple[int, str]:
    row = connection.execute(
        """SELECT profiles.id, profiles.name FROM profiles
           JOIN settings ON settings.key = 'active_profile_id'
                        AND settings.value = CAST(profiles.id AS TEXT)"""
    ).fetchone()
    if row is None:
        row = connection.execute("SELECT id, name FROM profiles ORDER BY id LIMIT 1").fetchone()
    if row is None:
        raise SystemExit("Brak profilu w bazie. Uruchom najpierw piWord.")
    return int(row["id"]), str(row["name"])


def summary(connection: sqlite3.Connection) -> None:
    profile_id, profile_name = active_profile(connection)
    total = connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    print(f"Profil: {profile_name}; baza: {total} fiszek\n")
    progress = connection.execute(
        """SELECT SUM(COALESCE(progress.learned, 0) != 0
                       OR COALESCE(progress.streak, 0) > 0) AS learned,
                  SUM(COALESCE(progress.difficult, 0) != 0) AS difficult,
                  SUM(progress.introduced_on = date('now', 'localtime')) AS today
           FROM cards
           LEFT JOIN card_progress AS progress
             ON progress.card_id = cards.id AND progress.profile_id = ?""",
        (profile_id,),
    ).fetchone()
    print(
        f"Umiem: {progress['learned'] or 0}; trudne: {progress['difficult'] or 0}; "
        f"nowe dzisiaj: {progress['today'] or 0}/20\n"
    )
    rows = connection.execute(
        """SELECT mode AS jezyk, level AS poziom, COUNT(*) AS fiszki
           FROM cards GROUP BY mode, level
           ORDER BY mode, CASE level
               WHEN 'A1' THEN 1 WHEN 'A2' THEN 2 WHEN 'B1' THEN 3
               WHEN 'B2' THEN 4 WHEN 'C1' THEN 5 WHEN 'C2' THEN 6 ELSE 7 END"""
    ).fetchall()
    print_rows(rows)


def thematic_statistics(
    connection: sqlite3.Connection,
    mode: str | None = None,
    topic: str | None = None,
) -> None:
    profile_id, profile_name = active_profile(connection)
    mode_label = MODE_LABELS.get(mode, "WSZYSTKIE")
    topic_label = TOPIC_LABELS.get(topic, "WSZYSTKIE")
    print(
        f"Statystyki: profil={profile_name}; jezyk={mode_label}; temat={topic_label}\n"
    )

    language_rows = connection.execute(
        """SELECT mode,
                  COUNT(*) AS total,
                  SUM(progress.introduced_on IS NOT NULL) AS introduced,
                  SUM(COALESCE(progress.learned, 0) != 0
                      OR COALESCE(progress.streak, 0) > 0) AS learned,
                  SUM(COALESCE(progress.difficult, 0) != 0) AS difficult,
                  SUM(progress.introduced_on = date('now', 'localtime')) AS today,
                  SUM(COALESCE(progress.learned, 0) = 0
                      AND progress.introduced_on IS NOT NULL
                      AND progress.due_at <= strftime('%s', 'now')) AS due
           FROM cards
           LEFT JOIN card_progress AS progress
             ON progress.card_id = cards.id AND progress.profile_id = ?
           WHERE (? IS NULL OR mode = ?)
             AND (? IS NULL OR EXISTS (
                 SELECT 1 FROM card_topics
                 WHERE card_id = cards.id AND topic = ?
             ))
           GROUP BY mode ORDER BY mode""",
        (profile_id, mode, mode, topic, topic),
    ).fetchall()
    language_values = []
    for row in language_rows:
        total = int(row["total"] or 0)
        learned = int(row["learned"] or 0)
        language_values.append(
            [
                MODE_LABELS.get(row["mode"], row["mode"]),
                str(total),
                str(int(row["introduced"] or 0)),
                str(learned),
                str(int(row["difficult"] or 0)),
                str(int(row["today"] or 0)),
                str(int(row["due"] or 0)),
                f"{(100 * learned / total):.1f}%" if total else "0.0%",
            ]
        )
    print("JEZYKI")
    print_table(
        [
            "jezyk",
            "fiszki",
            "poznane",
            "umiem",
            "trudne",
            "dzisiaj",
            "powtorki",
            "postep",
        ],
        language_values,
    )

    topic_rows = connection.execute(
        """SELECT card_topics.topic,
                  COUNT(*) AS total,
                  SUM(progress.introduced_on IS NOT NULL) AS introduced,
                  SUM(COALESCE(progress.learned, 0) != 0
                      OR COALESCE(progress.streak, 0) > 0) AS learned,
                  SUM(COALESCE(progress.difficult, 0) != 0) AS difficult,
                  SUM(progress.introduced_on = date('now', 'localtime')) AS today,
                  SUM(COALESCE(progress.learned, 0) = 0
                      AND progress.introduced_on IS NOT NULL
                      AND progress.due_at <= strftime('%s', 'now')) AS due
           FROM card_topics
           JOIN cards ON cards.id = card_topics.card_id
           LEFT JOIN card_progress AS progress
             ON progress.card_id = cards.id AND progress.profile_id = ?
           WHERE (? IS NULL OR cards.mode = ?)
             AND (? IS NULL OR card_topics.topic = ?)
           GROUP BY card_topics.topic ORDER BY card_topics.topic""",
        (profile_id, mode, mode, topic, topic),
    ).fetchall()
    topic_by_name = {str(row["topic"]): row for row in topic_rows}
    topic_values = []
    for topic_name in TOPICS:
        row = topic_by_name.get(topic_name)
        if row is None:
            continue
        total = int(row["total"] or 0)
        learned = int(row["learned"] or 0)
        topic_values.append(
            [
                TOPIC_LABELS.get(topic_name, topic_name),
                str(total),
                str(int(row["introduced"] or 0)),
                str(learned),
                str(int(row["difficult"] or 0)),
                str(int(row["today"] or 0)),
                str(int(row["due"] or 0)),
                f"{(100 * learned / total):.1f}%" if total else "0.0%",
            ]
        )
    print("\nTEMATY")
    print_table(
        [
            "temat",
            "fiszki",
            "poznane",
            "umiem",
            "trudne",
            "dzisiaj",
            "powtorki",
            "postep",
        ],
        topic_values,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xdb", description="Podgląd bazy piWord przez SSH")
    parser.add_argument("--database", type=Path, default=default_database_path())
    commands = parser.add_subparsers(dest="command")

    search = commands.add_parser("search", help="szukaj w słowie i tłumaczeniu")
    search.add_argument("text")
    search.add_argument("--limit", type=int, default=30)

    listing = commands.add_parser("list", help="pokaż fiszki z wybranego poziomu")
    listing.add_argument("level", nargs="?", choices=("A1", "A2", "B1", "B2", "C1", "C2", "OTHER"))
    listing.add_argument("--limit", type=int, default=30)

    card = commands.add_parser("card", help="pokaż jeden rekord po ID")
    card.add_argument("id", type=int)

    stats = commands.add_parser("stats", help="statystyki według języka i tematu")
    stats.add_argument("--mode", choices=MODES)
    stats.add_argument("--topic", choices=TOPICS)

    commands.add_parser("profiles", help="lista profili i aktywny profil")

    snapshot = commands.add_parser("snapshot", help="utwórz spójną kopię dla DBeaver")
    snapshot.add_argument("output", nargs="?", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    database = args.database.expanduser().resolve()
    with open_read_only(database) as connection:
        profile_id, _ = active_profile(connection)
        if args.command is None:
            summary(connection)
        elif args.command == "search":
            phrase = f"%{args.text}%"
            rows = connection.execute(
                """SELECT cards.id, cards.mode, cards.level,
                          COALESCE(progress.difficult, 0) AS difficult,
                          cards.front, cards.forms, cards.back FROM cards
                   LEFT JOIN card_progress AS progress
                     ON progress.card_id = cards.id AND progress.profile_id = ?
                   WHERE cards.front LIKE ? OR cards.back LIKE ? OR cards.forms LIKE ?
                   ORDER BY cards.level, cards.front LIMIT ?""",
                (profile_id, phrase, phrase, phrase, max(1, min(args.limit, 500))),
            ).fetchall()
            print_rows(rows)
        elif args.command == "list":
            rows = connection.execute(
                """SELECT cards.id, cards.mode, cards.level,
                          COALESCE(progress.difficult, 0) AS difficult,
                          cards.front, cards.forms, cards.back FROM cards
                   LEFT JOIN card_progress AS progress
                     ON progress.card_id = cards.id AND progress.profile_id = ?
                   WHERE (? IS NULL OR cards.level = ?)
                   ORDER BY cards.front LIMIT ?""",
                (profile_id, args.level, args.level, max(1, min(args.limit, 500))),
            ).fetchall()
            print_rows(rows)
        elif args.command == "card":
            rows = connection.execute(
                """SELECT cards.id, cards.mode, cards.front, cards.back, cards.forms,
                          cards.level, cards.note, cards.source, cards.example,
                          progress.streak, progress.seen_count,
                          progress.correct_count, progress.due_at, progress.learned,
                          progress.difficult, progress.introduced_on
                   FROM cards
                   LEFT JOIN card_progress AS progress
                     ON progress.card_id = cards.id AND progress.profile_id = ?
                   WHERE cards.id = ?""",
                (profile_id, args.id),
            ).fetchall()
            print_rows(rows)
        elif args.command == "stats":
            thematic_statistics(connection, mode=args.mode, topic=args.topic)
        elif args.command == "profiles":
            rows = connection.execute(
                """SELECT profiles.id, profiles.name,
                          CASE WHEN profiles.id = ? THEN 'TAK' ELSE '' END AS aktywny,
                          COUNT(card_progress.card_id) AS rozpoczete
                   FROM profiles
                   LEFT JOIN card_progress ON card_progress.profile_id = profiles.id
                   GROUP BY profiles.id, profiles.name ORDER BY profiles.id""",
                (profile_id,),
            ).fetchall()
            print_rows(rows)
        elif args.command == "snapshot":
            output = args.output or Path.home() / (
                "piword-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".db"
            )
            output = output.expanduser().resolve()
            if output.exists():
                raise SystemExit(f"Plik już istnieje: {output}")
            with sqlite3.connect(output) as destination:
                connection.backup(destination)
            print(output)


if __name__ == "__main__":
    main()
