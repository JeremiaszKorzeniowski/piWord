from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .cards import Card, MODE_LABELS, REVERSE_MODE_LABELS, TOPIC_LABELS


WIDTH = 250
HEIGHT = 122


def _font_candidates(bold: bool = False) -> tuple[Path, ...]:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    windows_name = "arialbd.ttf" if bold else "arial.ttf"
    waveshare_pic = (
        Path.home()
        / "e-Paper"
        / "RaspberryPi_JetsonNano"
        / "python"
        / "pic"
        / "Font.ttc"
    )
    return (
        Path("/usr/share/fonts/truetype/dejavu") / name,
        Path("/usr/share/fonts/dejavu") / name,
        waveshare_pic,
        Path("C:/Windows/Fonts") / name,
        Path("C:/Windows/Fonts") / windows_name,
    )


def _font(size: int, bold: bool = False):
    for candidate in _font_candidates(bold):
        if not candidate.is_file():
            continue
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            continue
    # Awaryjny font Pillow nie ma pelnego zestawu polskich znakow, ale pozwala
    # pokazac komunikat i nie wpadać usludze w petle restartow.
    return ImageFont.load_default()


def _fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_size: int, min_size: int = 14):
    for size in range(max_size, min_size - 1, -1):
        font = _font(size, bold=True)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_width:
            return font
    return _font(min_size, bold=True)


def card_header(
    card: Card, reversed_direction: bool = False, topic: str | None = None
) -> str:
    mode_label = (
        REVERSE_MODE_LABELS.get(card.mode, MODE_LABELS.get(card.mode, card.mode.upper()))
        if reversed_direction
        else MODE_LABELS.get(card.mode, card.mode.upper())
    )
    level_label = "INNE" if card.level == "OTHER" else card.level
    topic_label = TOPIC_LABELS.get(topic, "WSZYSTKIE")
    return f"{mode_label}  {level_label}  {topic_label}"


def render_card(
    card: Card,
    revealed: bool,
    message: str = "",
    reversed_direction: bool = False,
    topic: str | None = None,
) -> Image.Image:
    image = Image.new("1", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(image)
    header = card_header(card, reversed_direction, topic)
    header_font = _fit_font(draw, header, WIDTH - 12, 11, 8)
    draw.text((6, 3), header, font=header_font, fill=0)
    draw.line((5, 18, WIDTH - 6, 18), fill=0, width=1)

    front = card.back if reversed_direction else card.front
    answer = card.front if reversed_direction else card.back
    forms = card.forms if (not reversed_direction or revealed) else ""
    front_max_size = 31 if forms else 37
    front_y = 22 if forms else 24
    front_font = _fit_font(draw, front, WIDTH - 16, front_max_size)
    front_box = draw.textbbox((0, 0), front, font=front_font)
    front_width = front_box[2] - front_box[0]
    draw.text(((WIDTH - front_width) // 2, front_y), front, font=front_font, fill=0)

    if forms:
        forms_font = _fit_font(draw, forms, WIDTH - 16, 20, 11)
        forms_box = draw.textbbox((0, 0), forms, font=forms_font)
        forms_width = forms_box[2] - forms_box[0]
        draw.text(((WIDTH - forms_width) // 2, 55), forms, font=forms_font, fill=0)

    if revealed:
        answer_font = _fit_font(draw, answer, WIDTH - 16, 19 if forms else 23, 11)
        answer_box = draw.textbbox((0, 0), answer, font=answer_font)
        answer_width = answer_box[2] - answer_box[0]
        answer_y = 82 if forms else 70
        draw.text(((WIDTH - answer_width) // 2, answer_y), answer, font=answer_font, fill=0)
    else:
        hint = "nacisnij B1"
        hint_font = _font(12 if forms else 14)
        hint_box = draw.textbbox((0, 0), hint, font=hint_font)
        hint_y = 84 if forms else 76
        draw.text(((WIDTH - (hint_box[2] - hint_box[0])) // 2, hint_y), hint, font=hint_font, fill=0)

    footer = card.example if revealed and card.example else message
    if footer:
        footer_font = _font(9)
        short_message = textwrap.shorten(footer, width=42, placeholder="...")
        draw.text((5, HEIGHT - 13), short_message, font=footer_font, fill=0)
    return image


def render_status(title: str, lines: list[str]) -> Image.Image:
    image = Image.new("1", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(image)
    draw.text((6, 4), title, font=_font(15, bold=True), fill=0)
    draw.line((5, 23, WIDTH - 6, 23), fill=0, width=1)
    for index, line in enumerate(lines[:5]):
        draw.text((8, 29 + index * 18), line, font=_font(13), fill=0)
    return image


class PreviewDisplay:
    def __init__(self, output: Path):
        self.output = Path(output)

    def show_card(
        self,
        card: Card,
        revealed: bool,
        message: str = "",
        reversed_direction: bool = False,
        topic: str | None = None,
    ) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        render_card(card, revealed, message, reversed_direction, topic).save(self.output)

    def show_status(self, title: str, lines: list[str]) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        render_status(title, lines).save(self.output)

    def close(self) -> None:
        return


class WaveshareDisplay:
    def __init__(self):
        default_lib = Path.home() / "e-Paper" / "RaspberryPi_JetsonNano" / "python" / "lib"
        library_path = Path(os.environ.get("WAVESHARE_PYTHON_LIB", default_lib)).expanduser()
        if str(library_path) not in sys.path:
            sys.path.insert(0, str(library_path))
        try:
            from waveshare_epd import epd2in13_V2
        except ImportError as error:
            raise RuntimeError(f"Nie znaleziono biblioteki Waveshare w {library_path}") from error
        self.module = epd2in13_V2
        self.epd = epd2in13_V2.EPD()
        self.update_count = 0

    def _show_image(self, image: Image.Image) -> None:
        if self.update_count and self.update_count % 10 != 0:
            self.epd.init(self.epd.PART_UPDATE)
            self.epd.displayPartial(self.epd.getbuffer(image))
        else:
            self.epd.init(self.epd.FULL_UPDATE)
            # V2 potrzebuje obrazu bazowego w obu pamięciach kontrolera,
            # zanim kolejne klatki będą odświeżane częściowo.
            self.epd.displayPartBaseImage(self.epd.getbuffer(image))
        self.update_count += 1

    def show_card(
        self,
        card: Card,
        revealed: bool,
        message: str = "",
        reversed_direction: bool = False,
        topic: str | None = None,
    ) -> None:
        self._show_image(render_card(card, revealed, message, reversed_direction, topic))

    def show_status(self, title: str, lines: list[str]) -> None:
        self._show_image(render_status(title, lines))

    def close(self) -> None:
        self.epd.sleep()

