from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import json

def generate_thumbnail(destination_name, output_path):
    # Create a blank 1280x720 image (YouTube standard)
    img = Image.new('RGB', (1280, 720), color=(20, 20, 20))
    draw = ImageDraw.Draw(img)
    
    # Try to load a default font, fallback to default if not found
    try:
        font = ImageFont.truetype("arial.ttf", 100)
    except IOError:
        font = ImageFont.load_default()

    # Draw the text in the center
    text = destination_name.upper()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (1280 - text_width) / 2
    y = (720 - text_height) / 2
    
    # Add outline for readability
    draw.text((x, y), text, font=font, fill=(255, 255, 255), stroke_width=5, stroke_fill=(0, 0, 0))
    
    img.save(output_path)
    print(f"Thumbnail saved to {output_path}")

if __name__ == "__main__":
    with open("output/video_plan.json", "r", encoding="utf-8") as f:
        plans = json.load(f)
    dest = plans[0]["destination"]
    
    generate_thumbnail(dest, "output/thumbnail.jpg")
