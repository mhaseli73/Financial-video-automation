import io
import os
import random
import time
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw

from common import load_json, save_json
from styles import get_style

def style_prefix(accent):
    """The daily style adds one accent color, so each video looks a little different."""
    return (f"Stickman drawing, thick black marker, white background, minimalist cartoon, "
            f"with {accent} marker accents, no text, no letters, of: ")
HEADERS = {"User-Agent": "MoneyExplainedBot/1.0"}
DELAY_SECONDS = int(os.getenv("IMAGE_DELAY_SECONDS", "45"))  # pause between image requests
MAX_TRIES = 3


def is_real_image(data):
    """Pollinations can answer 200 with an error page. Make sure we really got a picture."""
    try:
        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:  # noqa: BLE001
        return False


def fetch_ai_image(prompt, local_filename, is_vertical, accent="red"):
    width, height = (1080, 1920) if is_vertical else (1920, 1080)
    seed = random.randint(1, 10_000_000)
    url = (f"https://image.pollinations.ai/prompt/{quote(style_prefix(accent) + prompt)}"
           f"?width={width}&height={height}&nologo=true&model=flux&seed={seed}")

    for attempt in range(1, MAX_TRIES + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=120)
            if response.status_code == 429:
                raise RuntimeError("rate limited (429)")
            response.raise_for_status()
            if not is_real_image(response.content):
                raise RuntimeError("response is not a valid image")
            local_filename.write_bytes(response.content)
            return True
        except Exception as error:  # noqa: BLE001
            print(f"  [AI Generator] attempt {attempt}/{MAX_TRIES} failed: {error}", flush=True)
            if attempt < MAX_TRIES:
                time.sleep(20 * attempt)
    return False


def make_placeholder(local_filename, is_vertical):
    """If the image service fails, draw a simple stickman so the video never has a hole."""
    width, height = (1080, 1920) if is_vertical else (1920, 1080)
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    cx, cy, u = width // 2, height // 2, min(width, height) // 6
    lw = max(6, u // 10)
    d.ellipse([cx - u // 2, cy - 2 * u, cx + u // 2, cy - u], outline="black", width=lw)       # head
    d.line([cx, cy - u, cx, cy + u // 2], fill="black", width=lw)                               # body
    d.line([cx, cy - u // 2, cx - u, cy], fill="black", width=lw)                               # arms
    d.line([cx, cy - u // 2, cx + u, cy - u], fill="black", width=lw)
    d.line([cx, cy + u // 2, cx - u // 2, cy + 2 * u], fill="black", width=lw)                  # legs
    d.line([cx, cy + u // 2, cx + u // 2, cy + 2 * u], fill="black", width=lw)
    d.ellipse([cx + u, cy - 2 * u, cx + 2 * u, cy - u], outline="black", width=lw)              # coin
    img.save(local_filename, "JPEG", quality=90)


def main():
    output_dir = Path("output")
    scene_plans_dir = output_dir / "scene_plans"
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    plan_files = sorted(scene_plans_dir.glob("*_scene_plan.json"))
    if not plan_files:
        raise FileNotFoundError("No scene plans found in output/scene_plans/")

    accent = get_style(load_json(output_dir / "video_plan.json")[0].get("style"))["accent"]
    all_image_paths = []
    for plan_file in plan_files:
        print(f"\nProcessing: {plan_file.name}")
        video_type = plan_file.name.replace("_scene_plan.json", "")
        is_vertical = video_type == "short"
        scenes = load_json(plan_file).get("scenes", [])

        for scene in scenes:
            scene_id = scene.get("scene_id", 1)
            local_filename = images_dir / f"{video_type}_scene_{scene_id}.jpg"

            # Resume: after a retry we do not pay the long wait again for finished images.
            if local_filename.exists() and local_filename.stat().st_size > 0:
                print(f"  Scene {scene_id}: already exists, skipping")
                all_image_paths.append(str(local_filename))
                continue

            prompt = scene.get("visual_description") or "a stickman thinking about money"
            print(f"  [AI Generator] {video_type} scene {scene_id}: {prompt[:90]}", flush=True)
            if not fetch_ai_image(prompt, local_filename, is_vertical, accent):
                print("  Using placeholder image.", flush=True)
                make_placeholder(local_filename, is_vertical)
            all_image_paths.append(str(local_filename))

            time.sleep(DELAY_SECONDS)

    save_json(output_dir / "video_assets.json", all_image_paths)


if __name__ == "__main__":
    main()
