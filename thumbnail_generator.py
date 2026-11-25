from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from common import draw_centered_lines, fit_text_block, headline, load_json
from styles import get_style

MAX_BYTES = 1_900_000  # YouTube limit for thumbnails is 2 MB


def generate_thumbnail(topic_name, image_path, output_path, is_vertical=False, color=(255, 235, 0)):
    print(f"Generating thumbnail for {output_path.name}...")
    size = (1080, 1920) if is_vertical else (1280, 720)

    try:
        img = Image.open(image_path).convert("RGB")
        img = ImageOps.fit(img, size, Image.Resampling.LANCZOS)  # no stretching
    except Exception as error:  # noqa: BLE001
        print(f"Error opening image: {error}")
        img = Image.new("RGB", size, color=(20, 20, 20))

    # The old code used font 'arialbd.ttf' (not on Linux) -> tiny default font, and it cut
    # the title at 30 characters on ONE line, which went outside the picture.
    text = headline(topic_name, max_chars=60).upper()
    img = img.convert("RGBA")
    probe = ImageDraw.Draw(img)
    font, lines, line_h = fit_text_block(
        probe, text, int(size[0] * 0.88), int(size[1] * 0.55),
        start_size=130 if not is_vertical else 110, max_lines=4,
    )

    # dark band behind the text, so it is readable on a bright picture
    block_h = line_h * len(lines)
    cy = size[1] // 2
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle(
        [0, cy - block_h // 2 - 30, size[0], cy + block_h // 2 + 30], fill=(0, 0, 0, 170))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    draw_centered_lines(draw, lines, font, size[0] / 2, cy, line_h,
                        fill=(*color, 255), stroke_width=6, stroke_fill=(0, 0, 0, 255))

    img = img.convert("RGB")  # JPEG cannot store alpha
    for quality in (92, 85, 75, 65):
        img.save(output_path, "JPEG", quality=quality)
        if output_path.stat().st_size <= MAX_BYTES:
            break
    print(f"Saved: {output_path}")


def main():
    output_dir = Path("output")
    plans = load_json(output_dir / "video_plan.json")
    topic = plans[0]["destination"]
    color = get_style(plans[0].get("style"))["title_color"]

    image_paths = []
    assets_file = output_dir / "video_assets.json"
    if assets_file.exists():
        image_paths = load_json(assets_file)

    # First picture of each video. (Names are 'long_scene_1.jpg' / 'short_scene_1.jpg'.)
    long_img = next((p for p in image_paths if Path(p).name.startswith("long_")), None)
    short_img = next((p for p in image_paths if Path(p).name.startswith("short_")), None)

    if long_img:
        generate_thumbnail(topic, long_img, output_dir / "long_thumbnail.jpg", is_vertical=False, color=color)
    if short_img:
        generate_thumbnail(topic, short_img, output_dir / "short_thumbnail.jpg", is_vertical=True, color=color)


if __name__ == "__main__":
    main()
