import json
import re
from itertools import accumulate
from pathlib import Path

from common import load_json, save_json
from gemini_client import generate_json
from styles import visual

SCENES_BY_TYPE = {"short": 8, "long": 24}
WORDS_PER_SECOND = 2.5  # only used for the estimate; the renderer uses the real audio length


def split_narration(narration, scene_count):
    """Split the approved narration into consecutive parts in PYTHON, by sentence.
    The old code asked Gemini to cut the text. Gemini often shortened or rewrote it, and the
    voiceover (built from those scene texts) then lost sentences."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", narration.strip()) if s]
    scene_count = max(1, min(scene_count, len(sentences)))
    counts = [len(s.split()) for s in sentences]
    cumulative = list(accumulate(counts))
    total = cumulative[-1]

    cuts, previous = [], -1
    for k in range(1, scene_count):
        target = total * k / scene_count
        low = previous + 1
        high = len(sentences) - (scene_count - k) - 1
        best = min(range(low, high + 1), key=lambda i: abs(cumulative[i] - target))
        cuts.append(best)
        previous = best

    parts, start = [], 0
    for end in cuts + [len(sentences) - 1]:
        parts.append(" ".join(sentences[start:end + 1]))
        start = end + 1
    return parts


def get_visuals(plan, script, parts):
    """Ask Gemini ONLY for the picture idea of each scene."""
    numbered = "\n".join(f"{i + 1}. {text}" for i, text in enumerate(parts))
    prompt = f"""
You are an expert director for an animated Finance YouTube channel.
For each numbered narration part below, write ONE visual description for an AI image generator.

TOPIC: {plan['destination']}
VIDEO TITLE: {script['title']}
IDEAS FROM THE SCRIPT: {json.dumps(script.get('visual_suggestions', []), ensure_ascii=False)}

NARRATION PARTS:
{numbered}

RULES:
1. Return exactly {len(parts)} descriptions, in the same order.
2. Style: {visual()['scene_rules']}. No travel, beaches or tourists.
3. Use the same main character in every scene: {visual()['character']}.
4. One clear idea per scene: say who is there, what they do, which objects, and the emotion.
5. Do NOT ask for readable words, letters or numbers in the picture (image AI writes them badly).
   Use symbols like $, %, arrows and charts instead.
6. Do not name real brands, logos or people.

Return ONLY valid JSON:
{{"visuals": ["description for part 1", "description for part 2"]}}
"""

    def validate(result):
        visuals = result.get("visuals") if isinstance(result, dict) else None
        if not isinstance(visuals, list) or len(visuals) != len(parts):
            return f"expected {len(parts)} visuals, got {len(visuals) if isinstance(visuals, list) else 'none'}"
        return None

    try:
        return [str(v) for v in generate_json(prompt, temperature=0.5, max_tokens=12000,
                                              validate=validate)["visuals"]]
    except RuntimeError:
        # Do not stop the whole pipeline because of pictures: use simple generic scenes.
        print("  Could not get visuals from Gemini. Using generic scenes.", flush=True)
        return [f"{visual()['fallback']}{t[:120]}"
                for t in parts]


def create_scene_plan(plan, script):
    video_type = plan["video_type"]
    parts = split_narration(script["narration"], SCENES_BY_TYPE[video_type])
    print(f"\nPlanning {len(parts)} scenes for {video_type}...", flush=True)
    visuals = get_visuals(plan, script, parts)

    scenes, current_time = [], 0.0
    for index, text in enumerate(parts):
        duration = round(len(text.split()) / WORDS_PER_SECOND, 2)
        scenes.append({
            "scene_id": index + 1,
            "start_time": round(current_time, 2),
            "duration": duration,  # estimate only
            "narration": text,
            "visual_description": visuals[index],
            "camera_movement": "slow zoom",
            "transition": "cut",
        })
        current_time += duration

    return {
        "destination": plan["destination"],
        "country": plan["country"],
        "video_type": video_type,
        "total_duration": round(current_time, 2),
        "scene_count": len(scenes),
        "scenes": scenes,
    }


def main():
    output = Path("output")
    scripts_folder = output / "scripts"
    scene_folder = output / "scene_plans"
    scene_folder.mkdir(parents=True, exist_ok=True)

    for plan in load_json(output / "video_plan.json"):
        video_type = plan["video_type"]
        script_path = scripts_folder / f"{video_type}_script.json"
        if not script_path.exists():
            raise FileNotFoundError(f"Missing script: {script_path}")
        result = create_scene_plan(plan, load_json(script_path))
        filename = scene_folder / f"{video_type}_scene_plan.json"
        save_json(filename, result)
        print(f"Saved: {filename}")


if __name__ == "__main__":
    main()
