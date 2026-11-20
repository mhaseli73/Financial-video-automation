import os
import json
import re
import random
import requests
from pathlib import Path
from urllib.parse import quote

def fetch_bing_image(query, scene_id, output_dir):
    print(f"  [Bing] Searching for image: {query}")
    search_url = f"https://www.bing.com/images/search?q={quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        # Extract image URLs from Bing HTML
        pattern = r'murl&quot;:&quot;(https?://[^&]+?)&quot;'
        matches = re.findall(pattern, response.text)
        
        if not matches:
            print(f"  [Bing] No images found.")
            return None
            
        # Pick a random image from the top 10 results
        image_url = random.choice(matches[:10])
        
        # Create unique filename
        safe_query = quote(query.replace(" ", "_"), safe="")
        local_filename = output_dir / f"scene_{scene_id}_{safe_query}.jpg"
        
        img_data = requests.get(image_url, headers=headers, timeout=30)
        img_data.raise_for_status()
        
        with open(local_filename, "wb") as f:
            f.write(img_data.content)
            
        print(f"  [Bing] Downloaded image: {local_filename.name}")
        return str(local_filename)
        
    except Exception as error:
        print(f"  [Bing] Error: {error}")
        return None

def main():
    output_dir = Path("output")
    scene_plans_dir = output_dir / "scene_plans"
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    scene_plan_files = list(scene_plans_dir.glob("*_scene_plan.json"))
    
    all_image_paths = []

    for plan_file in scene_plan_files:
        print(f"\nProcessing scene plan: {plan_file.name}")
        with open(plan_file, encoding="utf-8") as f:
            scene_plan = json.load(f)

        for scene in scene_plan.get("scenes", []):
            # Use a new key specifically for photos to avoid old video queries
            query = scene.get("visual_description", "")[:50] # Use first 50 chars of visual description
            # If you prefer the AI's query, use scene.get("pexels_video_query") 
            
            scene_id = scene.get("scene_id", 1)
            if query:
                path = fetch_bing_image(query, scene_id, images_dir)
                if path:
                    all_image_paths.append(path)

    with open(output_dir / "image_assets.json", "w", encoding="utf-8") as f:
        json.dump(all_image_paths, f, indent=4)

    print(f"\nDownloaded {len(all_image_paths)} images total.")

if __name__ == "__main__":
    main()
