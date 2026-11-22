import os
import json
import time
import re
from pathlib import Path
from google import genai
from google.genai import types, errors

PRIMARY_MODEL = "gemini-3.8-flash"
FALLBACK_MODEL = "gemini-3.5-flash-lite"
RETRY_DELAYS = [5, 15, 30]
TEMPORARY_ERRORS = [408, 429, 500, 502, 503, 504]

def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: raise RuntimeError("GEMINI_API_KEY is missing")
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60000))

def generate_with_retry(client, model, prompt):
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            response = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.5, max_output_tokens=12000)
            )
            if not response.text: raise ValueError("Empty response")
            return json.loads(response.text)
        except Exception as error:
            status = getattr(error, "code", None)
            if status in TEMPORARY_ERRORS and attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
            else: raise
    return None

def create_scene_plan(plan, script, client):
    video_type = plan["video_type"]
    duration = int(plan["duration"])
    scene_count = 8 if video_type == "short" else 24
    scene_duration = duration / scene_count

    prompt = f"""
You are an expert director for a Stickman Finance YouTube channel.
Create a scene-by-scene production plan.

TOPIC: {plan['destination']}
VIDEO TYPE: {video_type}
TOTAL DURATION: {duration} seconds
NUMBER OF SCENES: Exactly {scene_count}
DURATION PER SCENE: Exactly {scene_duration} seconds.

VIDEO TITLE: {script['title']}
APPROVED FULL NARRATION: {script['narration']}

IMPORTANT RULES:
1. Create exactly {scene_count} scenes, each {scene_duration} seconds long.
2. Divide the approved narration exactly into consecutive segments.
3. Preserve the original narration exactly. Do not rewrite it.
4. Each scene must have a visual description suitable for a STICKMAN CARTOON about FINANCE.
5. FOCUS ON FINANCE: Visuals should show stickmen interacting with money, credit cards, charts, piggy banks, graphs, or looking stressed/happy about money. DO NOT use travel, beaches, or tourists.

RETURN ONLY VALID JSON:
{{
    "destination": "{plan['destination']}",
    "country": "{plan['country']}",
    "video_type": "{video_type}",
    "total_duration": {duration},
    "scene_count": {scene_count},
    "scenes": [
        {{
            "scene_id": 1,
            "start_time": 0,
            "duration": {scene_duration},
            "narration": "Exact segment",
            "visual_description": "Detailed visual description of the stickman finance scene",
            "pexels_image_query": "unused",
            "camera_movement": "Camera movement",
            "transition": "Transition",
            "sound_effect": "Sound effect"
        }}
    ]
}}
"""

    print(f"\nPlanning scenes for {video_type}...")
    result = generate_with_retry(client, PRIMARY_MODEL, prompt)
    if result is None:
        result = generate_with_retry(client, FALLBACK_MODEL, prompt)

    scenes = result.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != scene_count:
        raise ValueError(f"Expected {scene_count} scenes, received {len(scenes) if scenes else 0}")

    current_time = 0
    for index, scene in enumerate(scenes):
        scene["scene_id"] = index + 1
        scene["start_time"] = current_time
        scene["duration"] = scene_duration
        current_time += scene_duration

    print(f"{video_type.capitalize()} scene plan validated successfully!")
    return result

def main():
    output = Path("output")
    scripts_folder = output / "scripts"
    scene_folder = output / "scene_plans"
    scene_folder.mkdir(parents=True, exist_ok=True)

    with open(output / "video_plan.json", encoding="utf-8") as file:
        plans = json.load(file)

    client = get_client()
    for plan in plans:
        video_type = plan["video_type"]
        script_path = scripts_folder / f"{video_type}_script.json"
        if not script_path.exists():
            raise FileNotFoundError(f"Missing script: {script_path}")
        with open(script_path, encoding="utf-8") as file:
            script = json.load(file)
        
        result = create_scene_plan(plan, script, client)
        filename = scene_folder / f"{video_type}_scene_plan.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        print(f"Saved: {filename}")

if __name__ == "__main__":
    main()
