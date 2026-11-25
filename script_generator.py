from pathlib import Path

from common import clean_for_speech, load_json, save_json
import script_checker
from gemini_client import generate_json
from styles import get_style

# Voice speed is about 2.5 words per second, so 240 s is ~600 words.
# (The old prompt asked for 480-520 words, which is only ~3 minutes.)
# The real target now comes from the daily style; these are only the allowed limits.
SHORT_WORDS = (80, 200)

SPEECH_RULES = (
    "The narration is read by a text-to-speech voice. Write plain spoken sentences only: "
    "no headings, no bullet points, no markdown, no emojis, no hashtags, no stage directions "
    "or notes in brackets. Do not name real companies, brands or people."
)


def make_validator(video_type, style):
    if video_type == "short":
        low, high = SHORT_WORDS
    else:
        low, high = style["words"][0] - 100, style["words"][1] + 200

    def validate(result):
        if not isinstance(result, dict):
            return "not a JSON object"
        if not str(result.get("title", "")).strip():
            return "missing title"
        narration = str(result.get("narration", "")).strip()
        words = len(narration.split())
        if not low <= words <= high:
            return f"narration has {words} words, expected {low}-{high}"
        return None

    return validate


def build_long_prompt(plan, research, style):
    return f"""
You are a professional YouTube scriptwriter creating an animated cartoon finance explainer.

TOPIC: {plan['destination']}
MAIN THEME: {plan.get('theme', '')}
VIDEO CONCEPT: {plan.get('topic_angle', '')}
AUDIENCE INTEREST: {plan.get('audience_reason', '')}
BACKGROUND (from Wikipedia, may be empty): {research.get('description', '')}

TARGET LENGTH: {style['words'][0]} to {style['words'][1]} words.

CRITICAL LOGIC RULES:
1. DO NOT invent specific stock tips, tax laws, or fake statistics. Use only well-known, general facts.
2. Use simple, real-world examples (coffee, subscriptions, groceries).
3. The advice must be practical, safe and general. It is education, not personal financial advice.
4. {SPEECH_RULES}

VIDEO STYLE (follow this structure):
{style['structure']}
OPENING: {style['hook']}

Return ONLY valid JSON:
{{
  "title": "SEO video title, maximum 90 characters, no hashtags",
  "hook": "Opening hook",
  "narration": "Complete voice-over script",
  "visual_suggestions": ["Visual 1", "Visual 2"],
  "description": "YouTube description, 2-3 short paragraphs, no < or > characters",
  "tags": ["8 to 12 short tags"]
}}
"""


def build_short_prompt(plan, long_narration):
    return f"""
You are a YouTube Shorts strategist.
We just made a 4-minute long video about: {plan['destination']}
Here is the full script of the long video:
"{long_narration}"

Write a 60-second script (120 to 140 words) that is a TEASER for this long video.
1. Start with a shocking hook based on the long video.
2. Give 2-3 rapid-fire facts from the long script. Do not add new facts.
3. End by saying exactly: "Watch the full video on my channel to learn more!"
{SPEECH_RULES}

Return ONLY valid JSON:
{{
  "title": "Punchy Short title, maximum 60 characters, no hashtags",
  "hook": "Shocking hook",
  "narration": "Complete voice-over script",
  "visual_suggestions": ["Visual 1", "Visual 2"],
  "description": "1-2 short sentences, no < or > characters",
  "tags": ["finance", "money", "shorts"]
}}
"""


def main():
    output = Path("output")
    script_folder = output / "scripts"
    script_folder.mkdir(parents=True, exist_ok=True)

    plans = load_json(output / "video_plan.json")
    research = load_json(output / "destination_research.json")

    # The long video goes FIRST so the Short can be a teaser of it.
    plans = sorted(plans, key=lambda x: 0 if x["video_type"] == "long" else 1)
    long_narration = ""

    for plan in plans:
        video_type = plan["video_type"]
        print(f"Generating {video_type} script...", flush=True)

        style = get_style(plan.get("style"))
        if video_type == "short":
            prompt, temperature = build_short_prompt(plan, long_narration), 0.7
        else:
            prompt, temperature = build_long_prompt(plan, research, style), 0.7

        result = generate_json(prompt, temperature=temperature, max_tokens=8000,
                               validate=make_validator(video_type, style))

        result["narration"] = clean_for_speech(result["narration"])
        result["title"] = " ".join(str(result["title"]).split())
        if not isinstance(result.get("tags"), list):
            result["tags"] = []
        # Automatic logic/fact/safety check. Fixes the script or stops the run (see script_checker.py).
        result = script_checker.check_and_fix(
            result, plan, research.get("description", ""), style, video_type, long_narration)

        if video_type == "long":
            long_narration = result["narration"]

        result["destination"] = plan["destination"]
        result["country"] = plan["country"]

        filename = script_folder / f"{video_type}_script.json"
        save_json(filename, result)
        print(f"Created: {filename} ({len(result['narration'].split())} words)", flush=True)


if __name__ == "__main__":
    main()
