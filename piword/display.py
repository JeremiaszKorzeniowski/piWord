from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .cards import Card


WIDTH = 250
HEIGHT = 122


def _font_candidates(bold: bool = False) -> tuple[Path, ...]:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
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


def render_card(card: Card, revealed: bool, message: str = "") -> Image.Image:
    image = Image.new("1", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(image)
    draw.text((6, 3), "EN -> PL", font=_font(11, bold=True), fill=0)
    draw.line((5, 18, WIDTH - 6, 18), fill=0, width=1)

    front_font = _fit_font(draw, card.front, WIDTH - 16, 37)
    front_box = draw.textbbox((0, 0), card.front, font=front_font)
    front_width = front_box[2] - front_box[0]
    draw.text(((WIDTH - front_width) // 2, 24), card.front, font=front_font, fill=0)

    if revealed:
        answer = card.back
        answer_font = _fit_font(draw, answer, WIDTH - 16, 23, 12)
        answer_box = draw.textbbox((0, 0), answer, font=answer_font)
        answer_width = answer_box[2] - answer_box[0]
        draw.text(((WIDTH - answer_width) // 2, 70), answer, font=answer_font, fill=0)
    else:
        hint = "nacisnij B1"
        hint_font = _font(14)
        hint_box = draw.textbbox((0, 0), hint, font=hint_font)
        draw.text(((WIDTH - (hint_box[2] - hint_box[0])) // 2, 76), hint, font=hint_font, fill=0)

    if message:
        footer_font = _font(9)
        short_message = textwrap.shorten(message, width=42, placeholder="...")
        draw.text((5, HEIGHT - 13), short_message, font=footer_font, fill=0)
    return image


class PreviewDisplay:
    def __init__(self, output: Path):
        self.output = Path(output)

    def show_card(self, card: Card, revealed: bool, message: str = "") -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        render_card(card, revealed, message).save(self.output)

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

    def show_card(self, card: Card, revealed: bool, message: str = "") -> None:
        image = render_card(card, revealed, message)
        if self.update_count and self.update_count % 10 != 0:
            self.epd.init(self.epd.PART_UPDATE)
            self.epd.displayPartial(self.epd.getbuffer(image))
        else:
            self.epd.init(self.epd.FULL_UPDATE)
            # V2 potrzebuje obrazu bazowego w obu pamięciach kontrolera,
            # zanim kolejne klatki będą odświeżane częściowo.
            self.epd.displayPartBaseImage(self.epd.getbuffer(image))
        self.update_count += 1

    def close(self) -> None:
        self.epd.sleep()

