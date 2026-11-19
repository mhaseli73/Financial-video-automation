import os
import json
import re
import random
import requests
from pathlib import Path
from urllib.parse import quote

# --- SOURCE 1: COVERR ---
def fetch_coverr_video(query, scene_id, output_dir):
    """Scrapes Coverr for a free MP4 video without an API key."""
    search_url = f"https://coverr.co/s?q={quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        print(f"  [Coverr] Searching for: {query}")
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()

        # Look for Coverr's direct MP4 CDN links
        pattern = r'https://cdn\.coverr\.co/videos/[a-zA-Z0-9\-]+/[0-9]+p\.mp4'
        matches = list(set(re.findall(pattern, response.text))) # Use set to remove duplicates

        if not matches:
            print(f"  [Coverr] No videos found.")
            return None

        # Pick a RANDOM video from the results to avoid repetition
        video_url = random.choice(matches)
        print(f"  [Coverr] Found video: {video_url}")

        safe_query = quote(query, safe="")
        # Add scene_id to the filename so it NEVER overwrites previous clips
        local_filename = output_dir / f"scene_{scene_id}_clip_{safe_query}.mp4"

        video_data = requests.get(video_url, headers=headers, timeout=30)
        video_data.raise_for_status()

        with open(local_filename, "wb") as f:
            f.write(video_data.content)
        return str(local_filename)

    except Exception as error:
        print(f"  [Coverr] Error: {error}")
        return None

# --- SOURCE 2: MIXKIT ---
def fetch_mixkit_video(query, scene_id, output_dir):
    """Scrapes Mixkit for a free MP4 video without an API key."""
    search_slug = query.lower().replace(" ", "-")
    search_url = f"https://mixkit.co/free-stock-video/{search_slug}/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        print(f"  [Mixkit] Searching for: {query}")
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()

        # Look for Mixkit's direct MP4 links
        pattern = r'https://assets\.mixkit\.co/videos/[0-9]+/[0-9]+-720\.mp4'
        matches = list(set(re.findall(pattern, response.text)))

        if not matches:
            print(f"  [Mixkit] No videos found.")
            return None

        # Pick a RANDOM video from the results to avoid repetition
        video_url = random.choice(matches)
        print(f"  [Mixkit] Found video: {video_url}")

        safe_query = quote(query, safe="")
        # Add scene_id to the filename
        local_filename = output_dir / f"scene_{scene_id}_clip_{safe_query}.mp4"

        video_data = requests.get(video_url, headers=headers, timeout=30)
        video_data.raise_for_status()

        with open(local_filename, "wb") as f:
            f.write(video_data.content)
        return str(local_filename)

    except Exception as error:
        print(f"  [Mixkit] Error: {error}")
        return None

# --- THE FALLBACK MANAGER ---
def fetch_video_with_fallback(query, scene_id, output_dir):
    """Tries multiple sources until one successfully downloads a video."""
    sources = [
        fetch_coverr_video,
        fetch_mixkit_video
    ]
    
    for source_func in sources:
        path = source_func(query, scene_id, output_dir)
        if path:
            return path
            
    print(f"  [FAILED] Could not find video for '{query}' on any source.")
    return None

# --- MAIN EXECUTION ---
def main():
    output_dir = Path("output")
    scene_plans_dir = output_dir / "scene_plans"
    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    scene_plan_files = list(scene_plans_dir.glob("*_scene_plan.json"))
    if not scene_plan_files:
        raise FileNotFoundError("No scene plan files found in output/scene_plans/")

    all_video_paths = []

    for plan_file in scene_plan_files:
        print(f"\nProcessing scene plan: {plan_file.name}")
        with open(plan_file, encoding="utf-8") as f:
            scene_plan = json.load(f)

        for scene in scene_plan.get("scenes", []):
            query = scene.get("pexels_video_query")
            scene_id = scene.get("scene_id", "unknown")
            
            if query:
                path = fetch_video_with_fallback(query, scene_id, clips_dir)
                if path:
                    all_video_paths.append(path)

    # Save the list of downloaded clips for the renderer
    with open(output_dir / "video_assets.json", "w", encoding="utf-8") as f:
        json.dump(all_video_paths, f, indent=4)

    print(f"\nDownloaded {len(all_video_paths)} video clips total.")

if __name__ == "__main__":
    main()
