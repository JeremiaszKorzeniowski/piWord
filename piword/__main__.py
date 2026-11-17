from __future__ import annotations

import argparse
from pathlib import Path

from .app import run_hardware
from .cards import LEVELS, MODES, TOPICS, CardStore, default_database_path
from .display import PreviewDisplay


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="piword")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="uruchom aplikację na Raspberry Pi")
    run_parser.add_argument("--database", type=Path, default=default_database_path())

    preview_parser = subparsers.add_parser("preview", help="zapisz przykładowy ekran PNG")
    preview_parser.add_argument("--output", type=Path, default=Path("preview.png"))
    preview_parser.add_argument("--database", type=Path, default=default_database_path())
    preview_parser.add_argument("--mode", choices=MODES, default="en_pl")
    preview_parser.add_argument("--level", choices=LEVELS)
    preview_parser.add_argument("--topic", choices=TOPICS)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        run_hardware(args.database)
        return

    store = CardStore(args.database)
    store.initialize()
    card = store.next_card(mode=args.mode, level=args.level, topic=args.topic)
    display = PreviewDisplay(args.output)
    display.show_card(
        card,
        revealed=True,
        message="B1: dalej  B2: poziom  B3: jezyk",
        topic=args.topic,
    )
    print(args.output.resolve())


if __name__ == "__main__":
    main()

