import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

def generate_thumbnail(topic_name, image_path, output_path, is_vertical=False):
    print(f"Generating thumbnail for {output_path.name}...")
    
    if not image_path:
        print("No image found to make a thumbnail.")
        return
        
    try:
        img = Image.open(image_path)
        # Resize to YouTube standard sizes
        target_size = (1080, 1920) if is_vertical else (1280, 720)
        img = img.resize(target_size, Image.Resampling.LANCZOS)
        
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.6) 
    except Exception as e:
        print(f"Error opening image: {e}")
        target_size = (1080, 1920) if is_vertical else (1280, 720)
        img = Image.new('RGB', target_size, color=(20, 20, 20))

    draw = ImageDraw.Draw(img)
    
    try:
        # Make font smaller for vertical shorts
        font_size = 80 if is_vertical else 90
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()

    text = topic_name.upper()
    if len(text) > 30:
        text = text[:27] + "..."

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (img.width - text_width) / 2
    y = (img.height - text_height) / 2
    
    draw.text((x, y), text, font=font, fill=(255, 255, 0), stroke_width=8, stroke_fill=(0, 0, 0))
    
    img.save(output_path, "JPEG")
    print(f"Saved: {output_path}")

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

    # Find the first LONG image and first SHORT image
    long_img = next((p for p in image_paths if "long_" in Path(p).name), None)
    short_img = next((p for p in image_paths if "short_" in Path(p).name), None)

    # Generate both
    if long_img:
        generate_thumbnail(topic, long_img, output_dir / "long_thumbnail.jpg", is_vertical=False)
    if short_img:
        generate_thumbnail(topic, short_img, output_dir / "short_thumbnail.jpg", is_vertical=True)

if __name__ == "__main__":
    main()
