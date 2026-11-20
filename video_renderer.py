import json
from pathlib import Path
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeAudioClip,
    TextClip, CompositeVideoClip, concatenate_videoclips
)

def create_ken_burns_clip(image_path, duration, is_vertical=False):
    """Creates a video clip from an image with a slow zoom effect."""
    clip = ImageClip(image_path).set_duration(duration)
    
    # Target dimensions
    target_w, target_h = (1080, 1920) if is_vertical else (1920, 1080)
    
    # Resize image to cover the screen
    clip = clip.resize(height=target_h) if not is_vertical else clip.resize(width=target_w)
    
    # Center crop
    clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=target_w, height=target_h)
    
    # Apply Ken Burns Zoom
    clip = clip.resize(lambda t: 1 + 0.05 * t)
    
    # Re-crop to prevent zoom from exceeding bounds
    clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=target_w, height=target_h)
    
    return clip

def main():
    output_dir = Path("output")
    audio_dir = output_dir / "audio"
    
    plan_file = output_dir / "video_plan.json"
    destination_name = "Amazing Places" 
    if plan_file.exists():
        with open(plan_file, encoding="utf-8") as f:
            plans = json.load(f)
            destination_name = plans[0].get("destination", "Amazing Places")

    with open(output_dir / "image_assets.json", encoding="utf-8") as f:
        image_paths = json.load(f)

    audio_files = list(audio_dir.glob("*_narration.mp3"))

    for audio_path in audio_files:
        video_type = audio_path.stem.replace("_narration", "")
        is_vertical = (video_type == "short")
        print(f"\nRendering {video_type} video...")

        narration = AudioFileClip(str(audio_path))
        target_duration = narration.duration

        clips = []
        current_duration = 0.0
        clip_duration = 5.0 # Each image shows for 5 seconds
        
        for path in image_paths:
            if current_duration >= target_duration:
                break
            
            # Make sure we don't exceed audio duration
            remaining = target_duration - current_duration
            duration = min(clip_duration, remaining)
            
            clip = create_ken_burns_clip(path, duration, is_vertical)
            clips.append(clip)
            current_duration += duration

        if not clips:
            continue

        visual_track = concatenate_videoclips(clips, method="compose")
        visual_track = visual_track.set_duration(target_duration)

        # Add Text Overlay
        try:
            txt_clip = TextClip(destination_name.upper(), fontsize=90, color='white', font='Arial-Bold', stroke_color='black', stroke_width=4)
            txt_clip = txt_clip.set_position('center').set_duration(4).crossfadeout(1)
            visual_track = CompositeVideoClip([visual_track, txt_clip])
        except:
            pass # Skip text if font fails

        # Mix Background Music
        bgm_path = output_dir / "bgm.mp3"
        if bgm_path.exists():
            bgm = AudioFileClip(str(bgm_path)).volumex(0.1) 
            bgm = bgm.set_duration(target_duration)
            final_audio = CompositeAudioClip([narration, bgm])
        else:
            final_audio = narration

        final_video = visual_track.set_audio(final_audio)

        output_video_path = output_dir / f"{video_type}_final_video.mp4"
        print(f"Exporting to {output_video_path}...")
        
        # Vertical for Shorts, Horizontal for Long
        final_video.write_videofile(
            str(output_video_path), fps=24, codec="libx264", audio_codec="aac", threads=4, logger="bar"
        )
        
        final_video.close()
        for c in clips: c.close()
        narration.close()

    print("\nRendering complete!")

if __name__ == "__main__":
    main()
