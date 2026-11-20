import asyncio
import json
import random
import edge_tts
from pathlib import Path

VOICES = [
    "en-US-ChristopherNeural", "en-US-GuyNeural", "en-US-EricNeural",
    "en-GB-RyanNeural", "en-AU-WilliamNeural"
]

async def generate_audio(text, output_file, voice):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def main():
    output_dir = Path("output")
    scene_plans_dir = output_dir / "scene_plans"
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    scene_plan_files = list(scene_plans_dir.glob("*_scene_plan.json"))
    if not scene_plan_files:
        raise FileNotFoundError("No scene plan files found in output/scene_plans/")

    for plan_file in scene_plan_files:
        with open(plan_file, encoding="utf-8") as f:
            scene_plan = json.load(f)

        full_narration = ""
        for scene in scene_plan.get("scenes", []):
            text = scene.get("narration") or scene.get("script") or scene.get("text") or ""
            if text:
                full_narration += text + " "

        if not full_narration.strip():
            continue

        # Pick a random voice FOR EACH VIDEO
        chosen_voice = random.choice(VOICES)
        print(f"🎙️ Selected Voice for {plan_file.name}: {chosen_voice}")

        video_type = plan_file.stem.replace("_scene_plan", "")
        output_audio_path = audio_dir / f"{video_type}_narration.mp3"

        asyncio.run(generate_audio(full_narration.strip(), str(output_audio_path), chosen_voice))
        print(f"Successfully created {output_audio_path}")

    print("Voiceover generation complete!")

if __name__ == "__main__":
    main()
