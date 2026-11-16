from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from piword.cards import default_database_path


def open_read_only(path: Path) -> sqlite3.Connection:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Nie znaleziono bazy: {path}")
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def print_rows(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("Brak wyników.")
        return
    headers = list(rows[0].keys())
    values = [[str(row[name] if row[name] is not None else "") for name in headers] for row in rows]
    widths = [
        min(60, max(len(header), *(len(row[index]) for row in values)))
        for index, header in enumerate(headers)
    ]
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in values:
        print("  ".join(value[:widths[index]].ljust(widths[index]) for index, value in enumerate(row)))


def summary(connection: sqlite3.Connection) -> None:
    total = connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    print(f"Baza: {total} fiszek\n")
    rows = connection.execute(
        """SELECT mode AS jezyk, level AS poziom, COUNT(*) AS fiszki
           FROM cards GROUP BY mode, level
           ORDER BY mode, CASE level
               WHEN 'A1' THEN 1 WHEN 'A2' THEN 2 WHEN 'B1' THEN 3
               WHEN 'B2' THEN 4 WHEN 'C1' THEN 5 WHEN 'C2' THEN 6 ELSE 7 END"""
    ).fetchall()
    print_rows(rows)


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

    snapshot = commands.add_parser("snapshot", help="utwórz spójną kopię dla DBeaver")
    snapshot.add_argument("output", nargs="?", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    database = args.database.expanduser().resolve()
    with open_read_only(database) as connection:
        if args.command is None:
            summary(connection)
        elif args.command == "search":
            phrase = f"%{args.text}%"
            rows = connection.execute(
                """SELECT id, mode, level, front, forms, back FROM cards
                   WHERE front LIKE ? OR back LIKE ? OR forms LIKE ?
                   ORDER BY level, front LIMIT ?""",
                (phrase, phrase, phrase, max(1, min(args.limit, 500))),
            ).fetchall()
            print_rows(rows)
        elif args.command == "list":
            rows = connection.execute(
                """SELECT id, mode, level, front, forms, back FROM cards
                   WHERE (? IS NULL OR level = ?)
                   ORDER BY front LIMIT ?""",
                (args.level, args.level, max(1, min(args.limit, 500))),
            ).fetchall()
            print_rows(rows)
        elif args.command == "card":
            rows = connection.execute(
                "SELECT * FROM cards WHERE id = ?", (args.id,)
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
