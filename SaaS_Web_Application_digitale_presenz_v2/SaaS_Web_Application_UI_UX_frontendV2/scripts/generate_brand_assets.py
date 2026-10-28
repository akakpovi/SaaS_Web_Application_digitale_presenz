#!/usr/bin/env python3
"""Génère les images PNG de marque (Open Graph + icônes PWA).

Les réseaux sociaux (LinkedIn, X, Facebook, Slack) n'acceptent pas le SVG :
sans PNG 1200x630, aucun aperçu n'est affiché.  Les icônes PWA doivent aussi
être en PNG 192/512 pour être installables sur Android et iOS.

Usage:  python3 scripts/generate_brand_assets.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
ICONS = PUBLIC / "icons"

INDIGO = (79, 70, 229)
INDIGO_DARK = (49, 46, 129)
WHITE = (255, 255, 255)
SLATE_200 = (226, 232, 240)
SLATE_400 = (148, 163, 184)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:  # pragma: no cover - fallback for minimal images
        return ImageFont.load_default()


def draw_mark(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int) -> None:
    """Draw the Presence concentric-ring mark."""
    for ratio, width in ((1.0, max(2, radius // 12)), (0.55, max(2, radius // 14))):
        r = int(radius * ratio)
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=WHITE,
            width=width,
        )
    core = max(3, radius // 4)
    draw.ellipse([cx - core, cy - core, cx + core, cy + core], fill=WHITE)


def make_icon(size: int, path: Path, maskable: bool = False) -> None:
    image = Image.new("RGBA", (size, size), INDIGO)
    draw = ImageDraw.Draw(image)
    # Maskable icons need the mark inside the 80% safe zone.
    radius = int(size * (0.26 if maskable else 0.34))
    draw_mark(draw, size // 2, size // 2, radius)
    image.save(path, "PNG")


def make_og_image(path: Path) -> None:
    width, height = 1200, 630
    image = Image.new("RGB", (width, height), INDIGO_DARK)
    draw = ImageDraw.Draw(image)

    # Diagonal indigo gradient.
    for y in range(height):
        ratio = y / height
        color = tuple(
            int(INDIGO_DARK[i] + (INDIGO[i] - INDIGO_DARK[i]) * ratio)
            for i in range(3)
        )
        draw.line([(0, y), (width, y)], fill=color)

    # Decorative rings on the right.
    draw.ellipse([860, -160, 1380, 360], outline=(99, 102, 241), width=3)
    draw.ellipse([930, -90, 1310, 290], outline=(129, 140, 248), width=2)

    draw_mark(draw, 128, 120, 46)

    title_font = font(FONT_BOLD, 64)
    body_font = font(FONT_REGULAR, 30)
    small_font = font(FONT_BOLD, 26)

    draw.text((110, 210), "Website monitoring", font=title_font, fill=WHITE)
    draw.text((110, 290), "for small businesses", font=title_font, fill=WHITE)
    draw.text(
        (112, 392),
        "Uptime · SSL · DNS · Email security · Reputation",
        font=body_font,
        fill=SLATE_200,
    )

    # Price badge.
    draw.rounded_rectangle([112, 470, 470, 540], radius=18, fill=WHITE)
    draw.text((138, 490), "From €9 / month", font=small_font, fill=INDIGO_DARK)

    draw.text((112, 575), "presence", font=small_font, fill=SLATE_400)
    image.save(path, "PNG", optimize=True)


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    ICONS.mkdir(parents=True, exist_ok=True)

    make_og_image(PUBLIC / "og-image.png")
    make_icon(192, ICONS / "icon-192.png")
    make_icon(512, ICONS / "icon-512.png")
    make_icon(512, ICONS / "icon-maskable-512.png", maskable=True)
    make_icon(180, PUBLIC / "apple-touch-icon.png")

    for path in (
        PUBLIC / "og-image.png",
        ICONS / "icon-192.png",
        ICONS / "icon-512.png",
        ICONS / "icon-maskable-512.png",
        PUBLIC / "apple-touch-icon.png",
    ):
        print(f"{path.relative_to(ROOT)}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
