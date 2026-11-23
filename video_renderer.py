import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from moviepy.editor import (
    AudioFileClip, CompositeAudioClip, CompositeVideoClip, ImageClip,
    concatenate_audioclips, concatenate_videoclips,
)

from common import draw_centered_lines, fit_text_block, headline, load_json
from styles import get_style

FPS = 24
TAIL_SECONDS = 1.0     # small pause at the end so the voice is not cut
TITLE_SECONDS = 4


def fit_image_to_frame(clip, target_w, target_h):
    scale = max(target_w / clip.w, target_h / clip.h)
    clip = clip.resize(scale)
    return clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=target_w, height=target_h)


def create_ken_burns_clip(image_path, duration, is_vertical, zoom_in=True, zoom=0.08):
    """Slow zoom. The old version cropped a resized clip using its OLD size, so the zoom
    drifted to the top-left corner. A CompositeVideoClip with a fixed size keeps it centered."""
    target_w, target_h = (1080, 1920) if is_vertical else (1920, 1080)
    base = fit_image_to_frame(ImageClip(str(image_path)).set_duration(duration), target_w, target_h)
    if zoom_in:
        scale = lambda t: 1 + zoom * t / duration
    else:
        scale = lambda t: 1 + zoom * (1 - t / duration)
    moving = base.resize(scale).set_position("center")
    return CompositeVideoClip([moving], size=(target_w, target_h)).set_duration(duration)


def build_title_clip(text, is_vertical, color=(255, 235, 0), y_frac=0.5):
    """Intro title drawn with Pillow. The old TextClip needed ImageMagick and the font
    'Arial-Bold'; when they were missing, a bare 'except: pass' silently removed the title."""
    w, h = (1080, 1920) if is_vertical else (1920, 1080)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font, lines, line_h = fit_text_block(draw, text.upper(), int(w * 0.85), int(h * 0.5),
                                         start_size=110 if not is_vertical else 96, max_lines=4)
    top, bottom = draw_centered_lines(draw, lines, font, w / 2, h * y_frac, line_h,
                                      fill=(*color, 255), stroke_width=8,  # bright color: white is invisible on the white stickman images
                                      stroke_fill=(0, 0, 0, 255))
    clip = ImageClip(np.array(img)).set_duration(TITLE_SECONDS)
    return clip.crossfadein(0.5).crossfadeout(1)


def scene_durations(scenes, total):
    """Give each scene a share of the REAL audio length, by number of words.
    The old code showed each image for a fixed 5 seconds, so a 24-image video was only
    120 s long and the rest of a ~4 min video turned BLACK."""
    weights = [max(1, len(s.get("narration", "").split())) for s in scenes]
    return [total * w / sum(weights) for w in weights]


def pick_music(output_dir, style_id):
    """Use output/bgm.mp3, plus any extra tracks named bgm_*.mp3. The style chooses the track."""
    tracks = sorted(output_dir.glob("bgm*.mp3"))
    if not tracks:
        return None
    return tracks[sum(map(ord, style_id or "")) % len(tracks)]


def build_audio(narration, output_dir, total, style_id=""):
    bgm_path = pick_music(output_dir, style_id)
    if bgm_path is None:
        return CompositeAudioClip([narration]).set_duration(total)

    bgm = AudioFileClip(str(bgm_path)).volumex(0.1)
    loops = math.ceil(total / bgm.duration)
    bgm = concatenate_audioclips([bgm] * loops).subclip(0, total).audio_fadeout(1.5)
    return CompositeAudioClip([narration, bgm]).set_duration(total)


def main():
    output_dir = Path("output")
    audio_dir = output_dir / "audio"
    images_dir = output_dir / "images"

    plans = load_json(output_dir / "video_plan.json")
    topic_name = headline(plans[0].get("destination", "Money Explained"), max_chars=60)
    style_id = plans[0].get("style", "")
    style = get_style(style_id)

    audio_files = sorted(audio_dir.glob("*_narration.mp3"))
    if not audio_files:
        raise FileNotFoundError("No narration audio found in output/audio/")

    for audio_path in audio_files:
        video_type = audio_path.stem.replace("_narration", "")
        is_vertical = video_type == "short"
        print(f"\nRendering {video_type} video...", flush=True)

        scenes = load_json(output_dir / "scene_plans" / f"{video_type}_scene_plan.json")["scenes"]
        narration = AudioFileClip(str(audio_path))
        total = narration.duration + TAIL_SECONDS
        durations = scene_durations(scenes, total)

        clips, last_image = [], None
        for index, (scene, duration) in enumerate(zip(scenes, durations)):
            image = images_dir / f"{video_type}_scene_{scene['scene_id']}.jpg"
            if not image.exists():
                if last_image is None:
                    raise FileNotFoundError(f"Missing image: {image}")
                image = last_image  # reuse the previous picture instead of a black gap
            last_image = image
            clips.append(create_ken_burns_clip(image, duration, is_vertical, zoom_in=index % 2 == 0,
                                              zoom=style["zoom"]))

        visual_track = concatenate_videoclips(clips, method="chain")
        title = build_title_clip(topic_name, is_vertical, style["title_color"], style["title_y"]).set_start(0)
        visual_track = CompositeVideoClip([visual_track, title]).set_duration(total)

        final_video = visual_track.set_audio(build_audio(narration, output_dir, total, style_id))
        output_video_path = output_dir / f"{video_type}_final_video.mp4"

        final_video.write_videofile(
            str(output_video_path), fps=FPS, codec="libx264", audio_codec="aac",
            preset="veryfast", threads=4,
            # yuv420p = plays everywhere (moviepy's default can make 4:4:4 video that
            # QuickTime, phones and some TVs cannot play). faststart = quick web start.
            ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
            temp_audiofile=str(output_dir / f"{video_type}_temp_audio.m4a"),
            remove_temp=True, logger="bar",
        )

        final_video.close()
        for clip in clips:
            clip.close()
        narration.close()
        print(f"Saved: {output_video_path}", flush=True)


if __name__ == "__main__":
    main()
