import json
from pathlib import Path
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeAudioClip,
    TextClip, CompositeVideoClip, concatenate_videoclips
)

def fit_image_to_frame(clip, target_w, target_h):
    img_w, img_h = clip.size
    scale_w = target_w / img_w
    scale_h = target_h / img_h
    scale = max(scale_w, scale_h)
    clip = clip.resize(scale)
    clip = clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=target_w, height=target_h)
    return clip

def create_ken_burns_clip(image_path, duration, is_vertical=False):
    clip = ImageClip(image_path).set_duration(duration)
    target_w, target_h = (1080, 1920) if is_vertical else (1920, 1080)
    clip = fit_image_to_frame(clip, target_w, target_h)
    
    zoomed_clip = clip.resize(lambda t: 1 + 0.05 * t)
    zoomed_clip = zoomed_clip.crop(x_center=zoomed_clip.w/2, y_center=zoomed_clip.h/2, width=target_w, height=target_h)
    return zoomed_clip

def main():
    output_dir = Path("output")
    audio_dir = output_dir / "audio"
    
    plan_file = output_dir / "video_plan.json"
    topic_name = "Money Explained" 
    if plan_file.exists():
        with open(plan_file, encoding="utf-8") as f:
            plans = json.load(f)
            topic_name = plans[0].get("destination", "Money Explained")

    with open(output_dir / "video_assets.json", encoding="utf-8") as f:
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
        clip_duration = 5.0 
        
        for path in image_paths:
            if current_duration >= target_duration:
                break
            remaining = target_duration - current_duration
            duration = min(clip_duration, remaining)
            clip = create_ken_burns_clip(path, duration, is_vertical)
            clips.append(clip)
            current_duration += duration

        if not clips: continue

        visual_track = concatenate_videoclips(clips, method="compose")
        visual_track = visual_track.set_duration(target_duration)

        try:
            txt_clip = TextClip(topic_name.upper(), fontsize=90, color='white', font='Arial-Bold', stroke_color='black', stroke_width=4)
            txt_clip = txt_clip.set_position('center').set_duration(4).crossfadeout(1)
            visual_track = CompositeVideoClip([visual_track, txt_clip])
        except: pass 

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
        
        final_video.write_videofile(str(output_video_path), fps=24, codec="libx264", audio_codec="aac", threads=4, logger="bar")
        
        final_video.close()
        for c in clips: c.close()
        narration.close()

    print("\nRendering complete!")

if __name__ == "__main__":
    main()
