import asyncio
import json
import random
import edge_tts
from pathlib import Path

# A pool of high-quality, documentary-style neural voices
VOICES = [
    "en-US-ChristopherNeural", # Deep American (Documentary style)
    "en-US-GuyNeural",         # Energetic American (News style)
    "en-US-EricNeural",        # Calm American
    "en-GB-RyanNeural",        # British accent (Very professional)
    "en-AU-WilliamNeural"      # Australian accent (Great for travel)
]

async def generate_audio(text, output_file, voice):
    """Uses edge-tts to generate an MP3 file from text with a specific voice."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def main():
    output_dir = Path("output")
    scene_plans_dir = output_dir / "scene_plans"
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Find all scene plan files
    scene_plan_files = list(scene_plans_dir.glob("*_scene_plan.json"))
    if not scene_plan_files:
        raise FileNotFoundError("No scene plan files found in output/scene_plans/")

    for plan_file in scene_plan_files:
        print(f"Generating voiceover for: {plan_file.name}")
        
        with open(plan_file, encoding="utf-8") as f:
            scene_plan = json.load(f)

        # Combine all narration text from every scene
        full_narration = ""
        for scene in scene_plan.get("scenes", []):
            # Safely check for the narration key your script generator uses
            text = scene.get("narration") or scene.get("script") or scene.get("text") or ""
            if text:
                full_narration += text + " "

        if not full_narration.strip():
            print(f"Warning: No text found in {plan_file.name}. Skipping.")
            continue

        # Pick a random voice for this specific video
        chosen_voice = random.choice(VOICES)
        print(f"Selected Voice: {chosen_voice}")

        # Create a clean output filename (e.g., short_narration.mp3)
        video_type = plan_file.stem.replace("_scene_plan", "")
        output_audio_path = audio_dir / f"{video_type}_narration.mp3"

        print(f"Generating audio -> {output_audio_path}")
        
        # Run the async TTS function and pass the chosen voice
        asyncio.run(generate_audio(full_narration.strip(), str(output_audio_path), chosen_voice))
        
        print(f"Successfully created {output_audio_path}")

    print("Voiceover generation complete!")

if __name__ == "__main__":
    main()
