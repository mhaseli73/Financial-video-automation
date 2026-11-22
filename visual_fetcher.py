import os
import json
import time
import requests
from pathlib import Path
from urllib.parse import quote

def fetch_ai_image(prompt, scene_id, is_vertical, output_dir):
    print(f"  [AI Generator] Generating image for: {prompt}")
    
    width, height = (1080, 1920) if is_vertical else (1920, 1080)
    
    # Force Stickman style and use the 'flux' model
    full_prompt = f"Stickman drawing, thick black marker, white background, minimalist cartoon of: {prompt}"
    image_url = f"https://image.pollinations.ai/prompt/{quote(full_prompt)}?width={width}&height={height}&nologo=true&model=flux"
    
    try:
        response = requests.get(image_url, timeout=60)
        response.raise_for_status()
        local_filename = output_dir / f"{'short' if is_vertical else 'long'}_scene_{scene_id}.jpg"
        with open(local_filename, "wb") as f:
            f.write(response.content)
        return str(local_filename)
    except Exception as error:
        print(f"  [AI Generator] Error: {error}")
        return None

def main():
    output_dir = Path("output")
    scene_plans_dir = output_dir / "scene_plans"
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    scene_plan_files = list(scene_plans_dir.glob("*_scene_plan.json"))
    all_image_paths = []

    for plan_file in scene_plan_files:
        print(f"\nProcessing: {plan_file.name}")
        is_vertical = "short" in plan_file.name
        
        with open(plan_file, encoding="utf-8") as f:
            scene_plan = json.load(f)

        for scene in scene_plan.get("scenes", []):
            prompt = scene.get("visual_description", "")
            scene_id = scene.get("scene_id", 1)
            
            if prompt:
                path = fetch_ai_image(prompt, scene_id, is_vertical, images_dir)
                if path: all_image_paths.append(path)
                
                print("  [Waiting 45 seconds...]")
                time.sleep(45)

    with open(output_dir / "video_assets.json", "w", encoding="utf-8") as f:
        json.dump(all_image_paths, f, indent=4)

if __name__ == "__main__":
    main()
