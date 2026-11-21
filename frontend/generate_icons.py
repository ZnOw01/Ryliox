"""
generate_icons.py
Generates all PWA PNG icons for Ryliox from a programmatic source.
Requires: Pillow  (pip install Pillow)
Run from: e:\\Projects\\Ryliox\frontend\\public\
"""

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("Pillow not found. Run: pip install Pillow")


SIZES = [72, 96, 128, 144, 152, 192, 384, 512]

# Brand colors matching the OKLCH palette  (crimson-red gradient)
COLOR_TOP = (190, 26, 26)  # #be1a1a
COLOR_BOTTOM = (127, 13, 13)  # #7f0d0d
COLOR_WHITE = (255, 255, 255)


def draw_icon(size: int) -> Image.Image:
    """Draw the Ryliox icon at the given pixel size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded-rect radius (≈20% of size)
    radius = max(4, int(size * 0.20))

    # Draw gradient background by blending row by row
    for y in range(size):
        t = y / max(size - 1, 1)
        r = int(COLOR_TOP[0] + (COLOR_BOTTOM[0] - COLOR_TOP[0]) * t)
        g = int(COLOR_TOP[1] + (COLOR_BOTTOM[1] - COLOR_TOP[1]) * t)
        b = int(COLOR_TOP[2] + (COLOR_BOTTOM[2] - COLOR_TOP[2]) * t)
        draw.line([(0, y), (size - 1, y)], fill=(r, g, b, 255))

    # Mask to rounded rectangle
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img.putalpha(mask)

    # Draw "R" letter — use default font scaled to ~55% of size
    font_size = max(12, int(size * 0.55))
    try:
        # Try to load a bold system font
        import os

        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        font = None
        for fp in font_paths:
            if os.path.exists(fp):
                font = ImageFont.truetype(fp, font_size)
                break
        if font is None:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # Centre the letter
    bbox = draw.textbbox((0, 0), "R", font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2 - bbox[0]
    y = (size - text_h) // 2 - bbox[1] + int(size * 0.02)  # tiny baseline nudge

    draw.text((x, y), "R", fill=(*COLOR_WHITE, 255), font=font)

    return img


def main():
    icons_dir = Path(__file__).parent / "icons"
    icons_dir.mkdir(exist_ok=True)

    for size in SIZES:
        img = draw_icon(size)
        out_path = icons_dir / f"icon-{size}x{size}.png"
        img.save(out_path, "PNG", optimize=True)
        print(f"  [OK] {out_path.name}  ({size}x{size})")

    # Also write favicon.png (32x32) to public root
    favicon_img = draw_icon(32)
    favicon_path = Path(__file__).parent / "favicon.png"
    favicon_img.save(favicon_path, "PNG", optimize=True)
    print("  [OK] favicon.png  (32x32)")

    # Apple touch icon (180x180) used by index.astro
    # icon-192x192.png already generated above
    print(f"\nDone! Generated {len(SIZES) + 1} PNG files.")


if __name__ == "__main__":
    main()
