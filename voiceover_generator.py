import asyncio
import os
import random
import time
from pathlib import Path

import edge_tts

from common import clean_for_speech, load_json

VOICES = [
    "en-US-ChristopherNeural", "en-US-GuyNeural", "en-US-EricNeural",
    "en-GB-RyanNeural", "en-AU-WilliamNeural",
]


async def generate_audio(text, output_file, voice):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)


def generate_with_retry(text, output_file, voice, tries=4):
    """edge-tts sometimes fails for a moment (no audio received). Try again."""
    for attempt in range(1, tries + 1):
        try:
            asyncio.run(generate_audio(text, output_file, voice))
            if Path(output_file).exists() and Path(output_file).stat().st_size > 0:
                return
            raise RuntimeError("audio file is empty")
        except Exception as error:  # noqa: BLE001
            print(f"  TTS attempt {attempt}/{tries} failed: {error}", flush=True)
            if attempt == tries:
                raise
            time.sleep(5 * attempt)


def main():
    output_dir = Path("output")
    scene_plans_dir = output_dir / "scene_plans"
    scripts_dir = output_dir / "scripts"
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    plan_files = sorted(scene_plans_dir.glob("*_scene_plan.json"))
    if not plan_files:
        raise FileNotFoundError("No scene plan files found in output/scene_plans/")

    # One voice for the whole run, so the Short and the long video sound like the same channel.
    voice = os.getenv("TTS_VOICE") or random.choice(VOICES)
    print(f"Selected voice for this run: {voice}")

    for plan_file in plan_files:
        video_type = plan_file.name.replace("_scene_plan.json", "")

        # The approved script is the source of truth for what is spoken.
        script_path = scripts_dir / f"{video_type}_script.json"
        text = load_json(script_path).get("narration", "") if script_path.exists() else ""
        if not text.strip():
            text = " ".join(s.get("narration", "") for s in load_json(plan_file).get("scenes", []))
        text = clean_for_speech(text)
        if not text:
            raise RuntimeError(f"No narration text for {video_type}")

        output_audio_path = audio_dir / f"{video_type}_narration.mp3"
        generate_with_retry(text, str(output_audio_path), voice)
        print(f"Successfully created {output_audio_path}")

    print("Voiceover generation complete!")


if __name__ == "__main__":
    main()
