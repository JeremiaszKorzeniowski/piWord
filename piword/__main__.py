from __future__ import annotations

import argparse
from pathlib import Path

from .app import run_hardware
from .cards import CardStore, default_database_path
from .display import PreviewDisplay


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="piword")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="uruchom aplikację na Raspberry Pi")
    run_parser.add_argument("--database", type=Path, default=default_database_path())

    preview_parser = subparsers.add_parser("preview", help="zapisz przykładowy ekran PNG")
    preview_parser.add_argument("--output", type=Path, default=Path("preview.png"))
    preview_parser.add_argument("--database", type=Path, default=default_database_path())
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        run_hardware(args.database)
        return

    store = CardStore(args.database)
    store.initialize()
    card = store.next_card()
    display = PreviewDisplay(args.output)
    display.show_card(card, revealed=True, message="B1: dalej   B2: umiem")
    print(args.output.resolve())


if __name__ == "__main__":
    main()

