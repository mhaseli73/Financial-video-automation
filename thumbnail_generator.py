import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

def generate_thumbnail(topic_name, image_paths, output_path):
    print("Generating thumbnail...")
    
    if not image_paths:
        print("No images found to make a thumbnail.")
        return
        
    try:
        img = Image.open(image_paths[0])
        img = img.resize((1280, 720), Image.Resampling.LANCZOS)
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.6) 
    except Exception as e:
        print(f"Error opening image: {e}")
        img = Image.new('RGB', (1280, 720), color=(20, 20, 20))

    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arialbd.ttf", 90)
    except IOError:
        font = ImageFont.load_default()

    # Keep text short if topic is long
    text = topic_name.upper()
    if len(text) > 30:
        text = text[:27] + "..."

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (1280 - text_width) / 2
    y = (720 - text_height) / 2
    
    draw.text((x, y), text, font=font, fill=(255, 255, 0), stroke_width=8, stroke_fill=(0, 0, 0))
    
    img.save(output_path, "JPEG")
    print(f"Thumbnail saved to {output_path}")

def main():
    output_dir = Path("output")
    
    with open(output_dir / "video_plan.json", "r", encoding="utf-8") as f:
        plans = json.load(f)
    topic = plans[0]["destination"]
    
    image_paths = []
    assets_file = output_dir / "video_assets.json"
    if assets_file.exists():
        with open(assets_file, "r", encoding="utf-8") as f:
            image_paths = json.load(f)

    generate_thumbnail(topic, image_paths, output_dir / "thumbnail.jpg")

if __name__ == "__main__":
    main()
