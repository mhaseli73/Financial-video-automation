import json
import math
from pathlib import Path
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeAudioClip,
    TextClip, CompositeVideoClip, concatenate_videoclips, concatenate_audioclips
)

def fit_image_to_frame(clip, target_w, target_h):
    img_w, img_h = clip.size
    scale = max(target_w / img_w, target_h / img_h)
    clip = clip.resize(scale)
    return clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=target_w, height=target_h)

def create_ken_burns_clip(image_path, duration, is_vertical=False):
    clip = ImageClip(image_path).set_duration(duration)
    target_w, target_h = (1080, 1920) if is_vertical else (1920, 1080)
    clip = fit_image_to_frame(clip, target_w, target_h)
    zoomed_clip = clip.resize(lambda t: 1 + 0.05 * t)
    return zoomed_clip.crop(x_center=zoomed_clip.w/2, y_center=zoomed_clip.h/2, width=target_w, height=target_h)

def main():
    output_dir = Path("output")
    audio_dir = output_dir / "audio"
    
    plan_file = output_dir / "video_plan.json"
    topic_name = "Money Explained" 
    if plan_file.exists():
        with open(plan_file, encoding="utf-8") as f:
            topic_name = json.load(f)[0].get("destination", "Money Explained")

    with open(output_dir / "video_assets.json", encoding="utf-8") as f:
        image_paths = json.load(f)

    audio_files = list(audio_dir.glob("*_narration.mp3"))

    for audio_path in audio_files:
        video_type = audio_path.stem.replace("_narration", "")
        is_vertical = (video_type == "short")
        print(f"\nRendering {video_type} video...")

        narration = AudioFileClip(str(audio_path))
        target_duration = narration.duration

        prefix = "short_" if is_vertical else "long_"
        valid_images = [p for p in image_paths if prefix in Path(p).name]

        clips = []
        current_duration = 0.0
        clip_duration = 5.0 
        
        for path in valid_images:
            if current_duration >= target_duration: break
            duration = min(clip_duration, target_duration - current_duration)
            clips.append(create_ken_burns_clip(path, duration, is_vertical))
            current_duration += duration

        if not clips: continue

        visual_track = concatenate_videoclips(clips, method="compose").set_duration(target_duration)

        try:
            txt_clip = TextClip(topic_name.upper(), fontsize=90, color='white', font='Arial-Bold', stroke_color='black', stroke_width=4)
            visual_track = CompositeVideoClip([visual_track, txt_clip.set_position('center').set_duration(4).crossfadeout(1)])
        except: pass 

        bgm_path = output_dir / "bgm.mp3"
        if bgm_path.exists():
            bgm_original = AudioFileClip(str(bgm_path)).volumex(0.1) 
            
            # BULLETPROOF LOOPING: Stitch copies together
            loops_needed = math.ceil(target_duration / bgm_original.duration)
            bgm_looped = concatenate_audioclips([bgm_original] * loops_needed)
            bgm_final = bgm_looped.subclip(0, target_duration)
            
            final_audio = CompositeAudioClip([narration, bgm_final])
        else:
            final_audio = narration

        final_video = visual_track.set_audio(final_audio)
        output_video_path = output_dir / f"{video_type}_final_video.mp4"
        
        final_video.write_videofile(str(output_video_path), fps=24, codec="libx264", audio_codec="aac", threads=4, logger="bar")
        
        final_video.close()
        for c in clips: c.close()
        narration.close()

if __name__ == "__main__":
    main()
