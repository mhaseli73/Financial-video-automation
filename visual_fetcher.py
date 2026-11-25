import io
import os
import random
import time
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw

from common import load_json, save_json
from styles import get_style, image_prefix, visual

HEADERS = {"User-Agent": "MoneyExplainedBot/1.0"}
MAX_TRIES = 3
KEY_EXHAUSTED = False  # becomes True when the key has no balance (HTTP 402), so we stop asking for it

# The anonymous Pollinations endpoint ALWAYS puts its logo in the picture (the old "nologo=true"
# is ignored there). The logo is removed with a free key from https://enter.pollinations.ai
# Put the key in the GitHub secret POLLINATIONS_API_KEY. It is sent in a header, never in the URL.
API_KEY = os.getenv("POLLINATIONS_API_KEY", "").strip()
ALLOW_LOGO_FALLBACK = os.getenv("ALLOW_LOGO_FALLBACK", "1") != "0"
# Anonymous: Pollinations asks for at least 45 s between images. With a key we can go faster.
DELAY_SECONDS = int(os.getenv("IMAGE_DELAY_SECONDS", "5" if API_KEY else "45"))


def is_real_image(data):
    """Pollinations can answer 200 with an error page. Make sure we really got a picture."""
    try:
        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:  # noqa: BLE001
        return False


def build_request(full_prompt, width, height, seed, use_key):
    text = quote(full_prompt)
    if use_key:
        url = (f"https://gen.pollinations.ai/image/{text}"
               f"?width={width}&height={height}&nologo=true&model=flux&seed={seed}")
        return url, {**HEADERS, "Authorization": f"Bearer {API_KEY}"}
    url = (f"https://image.pollinations.ai/prompt/{text}"
           f"?width={width}&height={height}&nologo=true&model=flux&seed={seed}")
    return url, HEADERS


def try_download(url, headers, local_filename, label):
    for attempt in range(1, MAX_TRIES + 1):
        wait = 20 * attempt
        try:
            response = requests.get(url, headers=headers, timeout=120)
            if response.status_code == 402 and label == "key":
                # With a key, 402 = "no balance left". Waiting will not help, so stop using the key
                # for the rest of this run (otherwise every image would waste minutes).
                global KEY_EXHAUSTED
                KEY_EXHAUSTED = True
                print("  The Pollinations key has no balance left. Add credits at enter.pollinations.ai.", flush=True)
                return False
            if response.status_code in (402, 429):
                # Too many requests (or no budget). Respect the server's Retry-After.
                wait = min(int(response.headers.get("Retry-After", wait)), 120)
                raise RuntimeError(f"HTTP {response.status_code} (limit reached)")
            response.raise_for_status()
            if not is_real_image(response.content):
                raise RuntimeError("response is not a valid image")
            local_filename.write_bytes(response.content)
            return True
        except Exception as error:  # noqa: BLE001
            print(f"  [AI Generator/{label}] attempt {attempt}/{MAX_TRIES} failed: {error}", flush=True)
            if attempt < MAX_TRIES:
                time.sleep(wait)
    return False


def fetch_ai_image(prompt, local_filename, is_vertical, accent="red"):
    full_prompt = image_prefix(accent) + prompt
    width, height = (1080, 1920) if is_vertical else (1920, 1080)
    seed = random.randint(1, 10_000_000)

    if API_KEY and not KEY_EXHAUSTED:
        url, headers = build_request(full_prompt, width, height, seed, use_key=True)
        if try_download(url, headers, local_filename, "key"):
            return True
        if not ALLOW_LOGO_FALLBACK:
            return False
        print("  Key request failed. Trying the anonymous endpoint (a small logo may appear).", flush=True)
    elif API_KEY and not ALLOW_LOGO_FALLBACK:
        return False

    url, headers = build_request(full_prompt, width, height, seed, use_key=False)
    return try_download(url, headers, local_filename, "anonymous")


def make_placeholder(local_filename, is_vertical):
    """If the image service fails, draw a simple friendly cartoon so the video never has a hole."""
    width, height = (1080, 1920) if is_vertical else (1920, 1080)
    img = Image.new("RGB", (width, height), (214, 236, 255))
    d = ImageDraw.Draw(img)
    cx, cy, u = width // 2, height // 2, min(width, height) // 6
    lw = max(6, u // 14)
    d.rounded_rectangle([cx - u, cy - u // 4, cx + u, cy + 2 * u], radius=u // 3,
                        fill=(45, 110, 220), outline=(20, 40, 90), width=lw)                  # shirt
    d.ellipse([cx - u * 0.75, cy - 2 * u, cx + u * 0.75, cy - u * 0.1],
              fill=(255, 214, 170), outline=(20, 40, 90), width=lw)                            # head
    d.pieslice([cx - u * 0.75, cy - 2.1 * u, cx + u * 0.75, cy - 0.9 * u], 180, 360,
               fill=(110, 70, 40), outline=(20, 40, 90), width=lw)                             # hair
    for dx in (-u * 0.28, u * 0.28):
        d.ellipse([cx + dx - u * 0.07, cy - 1.1 * u, cx + dx + u * 0.07, cy - 0.93 * u], fill=(20, 40, 90))
    d.arc([cx - u * 0.35, cy - 0.95 * u, cx + u * 0.35, cy - 0.3 * u], 20, 160,
          fill=(20, 40, 90), width=lw)                                                          # smile
    d.ellipse([cx + 1.1 * u, cy, cx + 2.1 * u, cy + u], fill=(255, 205, 50),
              outline=(150, 100, 0), width=lw)                                                  # coin
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
    if not API_KEY:
        print("WARNING: POLLINATIONS_API_KEY is not set. Images come from the anonymous endpoint "
              "and WILL show the Pollinations logo.", flush=True)
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

            prompt = scene.get("visual_description") or "a character thinking about money"
            print(f"  [AI Generator] {video_type} scene {scene_id}: {prompt[:90]}", flush=True)
            if not fetch_ai_image(prompt, local_filename, is_vertical, accent):
                print("  Using placeholder image.", flush=True)
                make_placeholder(local_filename, is_vertical)
            all_image_paths.append(str(local_filename))

            time.sleep(DELAY_SECONDS)

    save_json(output_dir / "video_assets.json", all_image_paths)


if __name__ == "__main__":
    main()
