from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from piword.cards import CardStore, MODE_EN_PL, default_database_path


TEI = "{http://www.tei-c.org/ns/1.0}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def load_word_list(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    return {
        line.strip().casefold()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def xml_files(source: Path) -> list[Path]:
    source = source.expanduser()
    if source.is_file():
        return [source]
    letters = source / "letters"
    directory = letters if letters.is_dir() else source
    return sorted(directory.glob("*.xml"))


def parse_file(path: Path, allowed: set[str] | None):
    for _, entry in ET.iterparse(path, events=("end",)):
        if entry.tag != f"{TEI}entry":
            continue
        headword = ""
        for form in entry.findall(f"{TEI}form"):
            if form.get(XML_LANG) in (None, "en"):
                headword = text(form.find(f"{TEI}orth"))
                if headword:
                    break
        if not headword or (allowed is not None and headword.casefold() not in allowed):
            entry.clear()
            continue
        translations: list[str] = []
        for citation in entry.findall(f".//{TEI}cit[@type='trans']"):
            value = text(citation.find(f"{TEI}quote"))
            if value and value not in translations:
                translations.append(value)
        pos = text(entry.find(f".//{TEI}pos"))
        if translations:
            yield (
                MODE_EN_PL,
                headword,
                "; ".join(translations[:4]),
                "",
                pos,
                "FreeDict eng-pol",
            )
        entry.clear()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import FreeDict EN-PL do piWord")
    parser.add_argument("source", type=Path, help="katalog eng-pol, letters albo pojedynczy XML")
    parser.add_argument("--database", type=Path, default=default_database_path())
    parser.add_argument("--word-list", type=Path)
    args = parser.parse_args()

    allowed = load_word_list(args.word_list)
    files = xml_files(args.source)
    if not files:
        raise SystemExit(f"Nie znaleziono plików XML w {args.source}")

    store = CardStore(args.database)
    store.initialize()
    added = 0
    for path in files:
        added += store.add_cards(parse_file(path, allowed))
    print(f"Dodano {added} fiszek z {len(files)} plików XML")


if __name__ == "__main__":
    main()

