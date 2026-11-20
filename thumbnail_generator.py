import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

def generate_thumbnail(destination_name, image_paths, output_path):
    print("Generating professional thumbnail...")
    
    if not image_paths:
        print("No images found to make a thumbnail.")
        return
        
    # Grab the first image from the list
    try:
        img = Image.open(image_paths[0])
        # Resize to YouTube standard 1280x720
        img = img.resize((1280, 720), Image.Resampling.LANCZOS)
        
        # Darken the image slightly so the white text is readable
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.6) 
    except Exception as e:
        print(f"Error opening image: {e}")
        img = Image.new('RGB', (1280, 720), color=(20, 20, 20))

    draw = ImageDraw.Draw(img)
    
    # Try to load a bold font, fallback to default
    try:
        font = ImageFont.truetype("arialbd.ttf", 120) # Arial Bold
    except IOError:
        font = ImageFont.load_default()

    # Draw the text in the center
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

def main():
    output_dir = Path("output")
    
    # Load destination name
    with open(output_dir / "video_plan.json", "r", encoding="utf-8") as f:
        plans = json.load(f)
    dest = plans[0]["destination"]
    
    # Load image paths
    image_paths = []
    assets_file = output_dir / "video_assets.json"
    if assets_file.exists():
        with open(assets_file, "r", encoding="utf-8") as f:
            image_paths = json.load(f)

    generate_thumbnail(dest, image_paths, output_dir / "thumbnail.jpg")

if __name__ == "__main__":
    main()
