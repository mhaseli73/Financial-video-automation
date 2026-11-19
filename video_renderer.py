import json
from pathlib import Path
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeAudioClip,
    TextClip, CompositeVideoClip, concatenate_videoclips, vfx
)

def apply_ken_burns(clip, zoom_ratio=0.1):
    """Applies a slow zoom to a video clip to make it look alive."""
    def effect(get_frame, t):
        frame = get_frame(t)
        h, w = frame.shape[:2]
        new_w, new_h = int(w * (1 + zoom_ratio * t)), int(h * (1 + zoom_ratio * t))
        resized = vfx.resize(frame, newsize=(new_w, new_h))
        return resized[(new_h-h)//2:(new_h-h)//2 + h, (new_w-w)//2:(new_w-w)//2 + w]
    return clip.fl(effect)

def create_text_overlay(text, duration, fontsize=60):
    """Creates text on the screen with a dark background."""
    txt_clip = TextClip(
        text, fontsize=fontsize, color='white', font='Arial-Bold',
        stroke_color='black', stroke_width=2, method='caption', size=(1200, None)
    )
    bg = TextClip(
        text, fontsize=fontsize, font='Arial-Bold', method='caption',
        size=(txt_clip.w + 40, txt_clip.h + 40), color='black'
    ).set_opacity(0.6)
    
    text_with_bg = CompositeVideoClip([bg, txt_clip.set_position('center')])
    return text_with_bg.set_duration(duration).set_position(('center', 100))

def main():
    output_dir = Path("output")
    audio_dir = output_dir / "audio"
    
    # 1. Load the video plan to get the dynamic destination name
    plan_file = output_dir / "video_plan.json"
    destination_name = "Amazing Places" # Fallback text
    if plan_file.exists():
        with open(plan_file, encoding="utf-8") as f:
            plans = json.load(f)
            destination_name = plans[0].get("destination", "Amazing Places")

    with open(output_dir / "video_assets.json", encoding="utf-8") as f:
        video_paths = json.load(f)

    audio_files = list(audio_dir.glob("*_narration.mp3"))

    # Define the length of the crossfade (in seconds)
    crossfade_duration = 1.0

    for audio_path in audio_files:
        video_type = audio_path.stem.replace("_narration", "")
        print(f"\nRendering {video_type} video with crossfades...")

        narration = AudioFileClip(str(audio_path))
        target_duration = narration.duration

        clips = []
        current_duration = 0.0
        
        for path in video_paths:
            # Because of the crossfades, we need to grab a little extra footage
            if current_duration >= target_duration + (len(clips) * crossfade_duration):
                break
            
            clip = VideoFileClip(path)
            clip = apply_ken_burns(clip, zoom_ratio=0.05)
            
            # Apply the crossfade to every clip EXCEPT the first one
            if len(clips) > 0:
                clip = clip.crossfadein(crossfade_duration)
                
            clips.append(clip)
            current_duration += clip.duration

        if not clips:
            continue

        # Overlap the clips by using a negative padding value
        visual_track = concatenate_videoclips(clips, method="compose", padding=-crossfade_duration)
        
        # Ensure the video matches the audio duration exactly
        visual_track = visual_track.set_duration(target_duration)

        # Add Dynamic Text Overlay (Uses the destination name!)
        title_overlay = create_text_overlay(destination_name, duration=5, fontsize=80)
        visual_track = CompositeVideoClip([visual_track, title_overlay])

        # Mix Background Music (if you have output/bgm.mp3)
        bgm_path = output_dir / "bgm.mp3"
        if bgm_path.exists():
            bgm = AudioFileClip(str(bgm_path)).volumex(0.1) # 10% volume
            bgm = bgm.set_duration(target_duration)
            final_audio = CompositeAudioClip([narration, bgm])
        else:
            final_audio = narration

        final_video = visual_track.set_audio(final_audio)

        # Export
        output_video_path = output_dir / f"{video_type}_final_video.mp4"
        print(f"Exporting to {output_video_path}...")
        final_video.write_videofile(
            str(output_video_path), fps=24, codec="libx264", audio_codec="aac", threads=4, logger="bar"
        )
        
        final_video.close()
        for c in clips: c.close()
        narration.close()

    print("\nRendering complete!")

if __name__ == "__main__":
    main()
