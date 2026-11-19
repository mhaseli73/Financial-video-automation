import os
import json
import time
from pathlib import Path

from google import genai
from google.genai import types, errors

PRIMARY_MODEL = "gemini-3.8-flash"
FALLBACK_MODEL = "gemini-3.5-flash-lite"
RETRY_DELAYS = [5, 15, 30]
TEMPORARY_ERRORS = [408, 429, 500, 502, 503, 504]

def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")
    return genai.Client(api_key=api_key)

def generate_with_retry(client, model, prompt):
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            print(f"Trying {model}, attempt {attempt + 1}...")
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.5,
                    max_output_tokens=12000
                )
            )
            if not response.text:
                raise ValueError("Empty Gemini response")
            result = json.loads(response.text)
            if not isinstance(result, dict):
                raise ValueError("Invalid JSON structure")
            return result
        except Exception as error:
            print(f"Generation error: {error}")
            status = getattr(error, "code", None)
            retryable = (status in TEMPORARY_ERRORS or isinstance(error, json.JSONDecodeError) or "empty gemini response" in str(error).lower())
            if not retryable:
                raise
            if attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
    return None

def create_scene_plan(plan, script, client):
    video_type = plan["video_type"]
    duration = int(plan["duration"])
    scene_count = 8 if video_type == "short" else 24
    scene_duration = duration / scene_count

    prompt = f"""
You are an expert travel video director.
Create a detailed scene-by-scene production plan for a PRACTICAL TRAVEL GUIDE.

DESTINATION: {plan['destination']}, {plan['country']}
VIDEO TYPE: {video_type}
TOTAL DURATION: {duration} seconds
NUMBER OF SCENES: Exactly {scene_count}
DURATION PER SCENE: Exactly {scene_duration} seconds.

VIDEO TITLE: {script['title']}
APPROVED FULL NARRATION: {script['narration']}
VISUAL IDEAS: {json.dumps(plan.get('visual_ideas', []), ensure_ascii=False)}

IMPORTANT RULES:
1. Create exactly {scene_count} scenes, each {scene_duration} seconds long.
2. Divide the approved narration exactly into consecutive segments.
3. Preserve the original narration exactly. Do not rewrite it.
4. Every narration segment must appear in exactly one scene.
5. Each scene must have a visual description suitable for travel footage.
6. FOCUS ON TOURISM: Visuals should show beaches, hotels, local food, streets, tourists, and transportation.
7. CRITICAL RULE FOR VIDEO QUERIES: The `pexels_video_query` MUST be a simple, broad, 2-3 word search term. 
   - Good examples: "hotel room", "beach resort", "street food", "airport travel", "mediterranean beach", "city walking".
   - Bad examples: "Can Picafort beach at sunset", "Mallorca luxury hotel", "Spanish paella cooking". (Keep it generic!).
8. Specify camera movements (drone, pan, tracking, close-up).
9. First scene must have a strong hook. Final scene a memorable ending.

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
            "visual_description": "Detailed visual description",
            "pexels_video_query": "BROAD 2-3 word query ONLY",
            "pexels_image_query": "BROAD 2-3 word query ONLY",
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
    if result is None:
        raise RuntimeError(f"Scene planning failed for {video_type}")

    scenes = result.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != scene_count:
        raise ValueError(f"Expected {scene_count} scenes, received {len(scenes) if scenes else 0}")

    required_fields = ["scene_id", "start_time", "duration", "narration", "visual_description", "pexels_video_query", "pexels_image_query", "camera_movement", "transition", "sound_effect"]
    current_time = 0
    narration_segments = []

    for index, scene in enumerate(scenes):
        for field in required_fields:
            if field not in scene:
                raise ValueError(f"Scene {index + 1} missing {field}")
        if scene["scene_id"] != index + 1:
            raise ValueError("Invalid scene numbering")
        if abs(float(scene["start_time"]) - current_time) > 0.01:
            raise ValueError("Invalid scene timeline")
        if abs(float(scene["duration"]) - scene_duration) > 0.01:
            raise ValueError("Invalid scene duration")
        for field in required_fields[3:]:
            if not isinstance(scene[field], str) or not scene[field].strip():
                raise ValueError(f"Scene {index + 1}: invalid {field}")
        narration_segments.append(scene["narration"])
        current_time += scene_duration

    if abs(current_time - duration) > 0.01:
        raise ValueError("Total video duration mismatch")

    original_narration = " ".join(script["narration"].split())
    combined_narration = " ".join(" ".join(narration_segments).split())
    if original_narration != combined_narration:
        raise ValueError("Scene narration does not exactly match the approved script.")

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
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(result, file, indent=4, ensure_ascii=False)
        print(f"Saved: {filename}")

    print("\nAll scene plans generated successfully!")

if __name__ == "__main__":
    main()
