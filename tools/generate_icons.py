"""Generate the plugin's PNG icons with Pillow.

Run from the plugin root:
    python tools/generate_icons.py

The generated files are committed with the plugin so runtime has no Pillow
dependency.  Shapes are drawn at 512 px and downsampled to 128 px for clean
edges.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "assets" / "icons"
SIZE = 128
CANVAS = 512


def canvas() -> Image.Image:
    return Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))


def save(image: Image.Image, name: str) -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    # Trim transparent margins so every glyph has a consistent optical size.
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    max_side = int(SIZE * 0.92)
    width, height = image.size
    factor = min(max_side / max(1, width), max_side / max(1, height))
    scaled = image.resize(
        (max(1, int(width * factor)), max(1, int(height * factor))),
        Image.Resampling.LANCZOS,
    )
    output = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    output.alpha_composite(
        scaled,
        ((SIZE - scaled.width) // 2, (SIZE - scaled.height) // 2),
    )
    output.save(ICON_DIR / f"{name}.png")


def ellipse(draw: ImageDraw.ImageDraw, box, fill, outline=None, width=1):
    draw.ellipse(box, fill=fill, outline=outline, width=width)


def polygon(draw: ImageDraw.ImageDraw, points, fill):
    draw.polygon(points, fill=fill)


def sun(draw: ImageDraw.ImageDraw, cx: float, cy: float, radius: float, color="#FFC83D", rays=True):
    if rays:
        for index in range(12):
            angle = math.radians(index * 30)
            r1 = radius * 1.18
            r2 = radius * 1.52
            draw.line(
                (
                    cx + math.cos(angle) * r1,
                    cy + math.sin(angle) * r1,
                    cx + math.cos(angle) * r2,
                    cy + math.sin(angle) * r2,
                ),
                fill="#FFB000",
                width=max(8, int(radius * 0.14)),
            )
    ellipse(draw, (cx - radius, cy - radius, cx + radius, cy + radius), color)


def moon(draw: ImageDraw.ImageDraw, cx: float, cy: float, radius: float):
    ellipse(draw, (cx - radius, cy - radius, cx + radius, cy + radius), "#F5E7B0")
    ellipse(
        draw,
        (cx - radius * 0.45, cy - radius * 0.48, cx - radius * 0.05, cy - radius * 0.08),
        "#E4D28C",
    )
    ellipse(
        draw,
        (cx + radius * 0.12, cy + radius * 0.15, cx + radius * 0.48, cy + radius * 0.51),
        "#E4D28C",
    )
    ellipse(
        draw,
        (cx + radius * 0.2, cy - radius * 0.55, cx + radius * 0.42, cy - radius * 0.33),
        "#E4D28C",
    )


def cloud(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float = 1.0, color="#F2F5FA", shadow="#C9D3E0"):
    # A soft shadow under the white body.
    ellipse(
        draw,
        (cx - 112 * scale, cy + 22 * scale, cx + 80 * scale, cy + 70 * scale),
        shadow,
    )
    ellipse(draw, (cx - 78 * scale, cy - 10 * scale, cx + 18 * scale, cy + 72 * scale), color)
    ellipse(draw, (cx - 32 * scale, cy - 42 * scale, cx + 68 * scale, cy + 58 * scale), color)
    ellipse(draw, (cx + 16 * scale, cy - 6 * scale, cx + 112 * scale, cy + 64 * scale), color)
    draw.rounded_rectangle(
        (cx - 96 * scale, cy + 30 * scale, cx + 96 * scale, cy + 66 * scale),
        radius=18 * scale,
        fill=color,
    )


def rain(draw: ImageDraw.ImageDraw, cx: float, cy: float, count: int, color="#2E8BFF", heavy=False):
    width = 16 if heavy else 11
    length = 60 if heavy else 48
    for index in range(count):
        offset = (index - (count - 1) / 2) * 42
        draw.line(
            (
                cx + offset,
                cy + 55,
                cx + offset - 12,
                cy + 55 + length,
            ),
            fill=color,
            width=width,
        )


def snowflake(draw: ImageDraw.ImageDraw, cx: float, cy: float, radius: float, color="#9AD9FF"):
    for angle in (0, 60, 120):
        rad = math.radians(angle)
        dx = math.cos(rad) * radius
        dy = math.sin(rad) * radius
        draw.line(
            (cx - dx, cy - dy, cx + dx, cy + dy),
            fill=color,
            width=11,
        )
    ellipse(draw, (cx - 9, cy - 9, cx + 9, cy + 9), color)


def bolt(draw: ImageDraw.ImageDraw, cx: float, cy: float):
    polygon(
        draw,
        [
            (cx + 4, cy - 48),
            (cx + 52, cy - 48),
            (cx + 12, cy + 2),
            (cx + 44, cy + 2),
            (cx - 26, cy + 88),
            (cx + 2, cy + 16),
            (cx - 34, cy + 16),
        ],
        "#FFD43B",
    )


def lines(draw: ImageDraw.ImageDraw, cx: float, cy: float, count: int, color="#AFC6E9", width=18):
    for index in range(count):
        y = cy + index * 38
        draw.rounded_rectangle(
            (70 + index * 8, y - width / 2, 440 - index * 10, y + width / 2),
            radius=width / 2,
            fill=color,
        )


def make_weather(name: str) -> None:
    image = canvas()
    draw = ImageDraw.Draw(image)
    cx = cy = 256

    if name == "sunny_day":
        sun(draw, cx, cy, 104)
    elif name == "sunny_night":
        moon(draw, cx, cy, 112)
    elif name in ("cloudy", "overcast"):
        dark = "#AEBACB" if name == "overcast" else "#C9D3E0"
        cloud(draw, 235, 270, 0.92, color="#EDF2F9", shadow=dark)
        if name == "overcast":
            cloud(draw, 295, 205, 0.68, color="#DCE4EF", shadow="#B6C2D2")
    elif name in ("partly_cloudy_day", "partly_cloudy_night"):
        if name.endswith("day"):
            sun(draw, 175, 190, 76)
        else:
            moon(draw, 175, 185, 82)
        cloud(draw, 285, 315, 0.78)
    elif name in ("rain_light", "rain", "rain_heavy"):
        cloud(draw, 256, 245, 0.95)
        count = {"rain_light": 3, "rain": 4, "rain_heavy": 5}[name]
        rain(draw, 256, 252, count, heavy=name == "rain_heavy")
    elif name == "thunder":
        cloud(draw, 256, 235, 0.95)
        bolt(draw, 256, 310)
    elif name == "snow":
        cloud(draw, 256, 240, 0.95)
        snowflake(draw, 175, 335, 28)
        snowflake(draw, 256, 360, 34)
        snowflake(draw, 337, 335, 26)
    elif name == "sleet":
        cloud(draw, 256, 235, 0.95)
        rain(draw, 205, 245, 2, heavy=False)
        snowflake(draw, 315, 345, 32)
    elif name == "fog":
        cloud(draw, 256, 225, 0.9, color="#DCE4EF", shadow="#B6C2D2")
        lines(draw, 256, 315, 4, color="#C9D3E0", width=18)
    elif name == "haze":
        sun(draw, 220, 190, 82, color="#F4C76B", rays=False)
        lines(draw, 265, 300, 4, color="#D8B77A", width=16)
    elif name == "wind":
        draw.arc((70, 90, 420, 330), 200, 335, fill="#AFC6E9", width=22)
        draw.arc((120, 180, 450, 400), 190, 320, fill="#D5E4F7", width=18)
        draw.arc((80, 260, 360, 450), 200, 340, fill="#AFC6E9", width=16)
    elif name == "dust":
        ellipse(draw, (110, 150, 402, 360), "#D8B77A")
        for x, y, r in ((165, 210, 14), (265, 185, 18), (345, 245, 12), (220, 305, 17), (315, 325, 11)):
            ellipse(draw, (x - r, y - r, x + r, y + r), "#B28D4E")
    elif name == "typhoon":
        for index, r in enumerate((190, 132, 76)):
            draw.arc(
                (256 - r, 256 - r, 256 + r, 256 + r),
                30 + index * 45,
                300 + index * 45,
                fill="#AFC6E9" if index % 2 == 0 else "#D5E4F7",
                width=20,
            )
    else:  # unknown
        ellipse(draw, (66, 66, 446, 446), "#C9D3E0")
        draw.rounded_rectangle((205, 150, 307, 300), radius=26, fill="#F2F5FA")
        ellipse(draw, (207, 315, 305, 413), "#F2F5FA")
    save(image, name)


def make_alert(name: str) -> None:
    image = canvas()
    draw = ImageDraw.Draw(image)
    color = "#FFFFFF"
    cx = cy = 256

    if name == "alert_rain":
        cloud(draw, 256, 205, 1.02, color=color, shadow=color)
        rain(draw, 256, 225, 4, color=color, heavy=True)
    elif name == "alert_wind":
        for index, y in enumerate((175, 255, 335)):
            draw.arc(
                (60 - index * 10, y - 58, 420 + index * 10, y + 58),
                200,
                340,
                fill=color,
                width=20,
            )
            ellipse(
                draw,
                (400 + index * 10 - 17, y - 17, 400 + index * 10 + 17, y + 17),
                color,
            )
    elif name == "alert_snow":
        for x, y, r in ((185, 165, 55), (330, 215, 44), (225, 345, 52), (350, 370, 32)):
            snowflake(draw, x, y, r, color=color)
    elif name == "alert_temp":
        draw.rounded_rectangle((200, 60, 312, 330), radius=52, fill=color)
        ellipse(draw, (160, 280, 352, 472), color)
        draw.rounded_rectangle((228, 100, 284, 330), radius=28, fill="#E81123")
        for y in (160, 215, 270):
            draw.rounded_rectangle((120, y, 195, y + 20), radius=10, fill=color)
    elif name == "alert_fog":
        for index, y in enumerate((130, 210, 290, 370)):
            draw.rounded_rectangle(
                (70 + index * 12, y - 18, 442 - index * 14, y + 18),
                radius=18,
                fill=color,
            )
    elif name == "alert_thunder":
        bolt(draw, 256, 230)
    elif name == "alert_dust":
        cloud(draw, 256, 210, 0.98, color=color, shadow=color)
        for x, y, r in ((135, 330, 18), (215, 365, 13), (305, 340, 21), (380, 375, 12)):
            ellipse(draw, (x - r, y - r, x + r, y + r), color)
    elif name == "alert_typhoon":
        for index, r in enumerate((200, 145, 90)):
            draw.arc(
                (cx - r, cy - r, cx + r, cy + r),
                15 + index * 40,
                300 + index * 40,
                fill=color,
                width=22,
            )
    elif name == "alert_drought":
        draw.rounded_rectangle((50, 245, 462, 305), radius=16, fill=color)
        polygon(
            draw,
            [
                (70, 305), (150, 305), (190, 380), (235, 315), (300, 315),
                (335, 405), (380, 315), (450, 315), (450, 405), (70, 405),
            ],
            color,
        )
    else:  # generic triangle + exclamation
        polygon(draw, [(256, 55), (475, 435), (37, 435)], color)
        draw.rounded_rectangle((232, 165, 280, 330), radius=24, fill="#E81123")
        ellipse(draw, (230, 355, 282, 407), "#E81123")
    save(image, name)


def make_plugin_icon() -> None:
    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        ratio = y / size
        color = (
            int(24 + 30 * ratio),
            int(119 + 45 * ratio),
            int(242 - 20 * ratio),
            255,
        )
        draw.line((0, y, size, y), fill=color)
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=58, fill=255)
    image.putalpha(mask)

    overlay = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    sun(od, 170, 155, 76, rays=True)
    cloud(od, 300, 280, 0.74, color="#FFFFFF", shadow="#D9E6F7")
    overlay = overlay.resize((size, size), Image.Resampling.LANCZOS)
    image.alpha_composite(overlay)
    image.save(ROOT / "icon.png")


WEATHER_ICONS = [
    "sunny_day",
    "sunny_night",
    "partly_cloudy_day",
    "partly_cloudy_night",
    "cloudy",
    "overcast",
    "rain_light",
    "rain",
    "rain_heavy",
    "thunder",
    "snow",
    "sleet",
    "fog",
    "haze",
    "wind",
    "dust",
    "typhoon",
    "unknown",
]

ALERT_ICONS = [
    "alert_generic",
    "alert_rain",
    "alert_wind",
    "alert_snow",
    "alert_temp",
    "alert_fog",
    "alert_thunder",
    "alert_dust",
    "alert_typhoon",
    "alert_drought",
]


def main() -> None:
    for name in WEATHER_ICONS:
        make_weather(name)
    for name in ALERT_ICONS:
        make_alert(name)
    make_plugin_icon()
    print(f"Generated {len(WEATHER_ICONS) + len(ALERT_ICONS)} icons and icon.png in {ROOT}")


if __name__ == "__main__":
    main()
