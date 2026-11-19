import json
from pathlib import Path
from moviepy.editor import VideoFileClip
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

def generate_thumbnail(destination_name, video_paths, output_path):
    print("Generating professional thumbnail...")
    
    # 1. Grab a frame from the first downloaded video clip
    if not video_paths:
        print("No video clips found to make a thumbnail. Creating a blank one.")
        img = Image.new('RGB', (1280, 720), color=(20, 20, 20))
    else:
        first_clip = VideoFileClip(video_paths[0])
        # Get a frame from 2 seconds in (avoids black intro frames)
        frame_time = min(2.0, first_clip.duration / 2)
        frame = first_clip.get_frame(frame_time)
        first_clip.close()
        
        # Convert to PIL Image and resize to YouTube standard
        img = Image.fromarray(frame)
        img = img.resize((1280, 720), Image.Resampling.LANCZOS)
        
        # 2. Darken the image slightly so the white text is readable
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.6) 

    draw = ImageDraw.Draw(img)
    
    # 3. Try to load a bold font, fallback to default
    try:
        font = ImageFont.truetype("arialbd.ttf", 120) # Arial Bold
    except IOError:
        font = ImageFont.load_default()

    # 4. Draw the text in the center
    text = destination_name.upper()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (1280 - text_width) / 2
    y = (720 - text_height) / 2
    
    # Add a thick black outline for readability
    draw.text((x, y), text, font=font, fill=(255, 255, 255), stroke_width=8, stroke_fill=(0, 0, 0))
    
    img.save(output_path, "JPEG")
    print(f"Thumbnail saved to {output_path}")

if __name__ == "__main__":
    output_dir = Path("output")
    
    # Load destination name
    with open(output_dir / "video_plan.json", "r", encoding="utf-8") as f:
        plans = json.load(f)
    dest = plans[0]["destination"]
    
    # Load video paths
    video_paths = []
    assets_file = output_dir / "video_assets.json"
    if assets_file.exists():
        with open(assets_file, "r", encoding="utf-8") as f:
            video_paths = json.load(f)

    generate_thumbnail(dest, video_paths, output_dir / "thumbnail.jpg")
