import os
import json
import time
from pathlib import Path

from google import genai
from google.genai import types, errors

PRIMARY_MODEL = "gemini-3.8-flash"
FALLBACK_MODEL = "gemini-3.5-flash-lite"
RETRY_DELAYS = [10, 30, 60]
TEMPORARY_ERRORS = [408, 429, 500, 502, 503, 504]

def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60000))

def generate_with_retry(client, model, prompt):
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            print(f"Trying {model} (attempt {attempt + 1})...", flush=True)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                    max_output_tokens=4000
                )
            )
            if not response.text:
                return None
            return json.loads(response.text)
        except Exception as error:
            status = getattr(error, "code", None)
            if status in TEMPORARY_ERRORS and attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
            else:
                print(f"Error: {error}")
                return None
    return None

def main():
    output = Path("output")
    script_folder = output / "scripts"
    script_folder.mkdir(parents=True, exist_ok=True)

    with open(output / "video_plan.json", encoding="utf-8") as file:
        plans = json.load(file)

    with open(output / "destination_research.json", encoding="utf-8") as file:
        research = json.load(file)

    client = get_client()

    for plan in plans:
        video_type = plan["video_type"]
        duration = int(plan["duration"])
        target_words = "120 to 140 words" if video_type == "short" else "480 to 520 words"

        prompt = f"""
You are a professional YouTube scriptwriter creating a Stickman animated explainer video.

Create an original, engaging English script.

TOPIC: {plan['destination']}
MAIN THEME: {plan.get('theme', '')}
VIDEO CONCEPT: {plan.get('topic_angle', '')}
AUDIENCE INTEREST: {plan.get('audience_reason', '')}
RESEARCH: {research.get('description', '')}
VISUAL IDEAS: {json.dumps(plan.get('visual_ideas', []), ensure_ascii=False)}

VIDEO FORMAT: {video_type}
TARGET DURATION: {duration} seconds
TARGET SCRIPT LENGTH: {target_words}

INSTRUCTIONS:
1. THE HOOK: Start with a highly engaging, relatable problem.
2. EXPLAINER STYLE: Write like a friendly YouTuber explaining a concept. Use clear, punchy sentences.
3. Provide practical, actionable advice.
4. Make the narration suitable for voice-over. 
5. SEO: Include keywords in the title and description.
6. End with a natural audience engagement question.

Return ONLY valid JSON:
{{
  "title": "Video title (SEO optimized)",
  "hook": "Opening hook",
  "narration": "Complete voice-over script",
  "visual_suggestions": ["Visual 1", "Visual 2"],
  "description": "YouTube video description with SEO tags",
  "tags": ["finance", "psychology", "explainer"]
}}
"""

        print(f"Generating {video_type} script...", flush=True)
        result = generate_with_retry(client, PRIMARY_MODEL, prompt)
        
        if result is None:
            print("Primary model failed. Switching to fallback...")
            result = generate_with_retry(client, FALLBACK_MODEL, prompt)

        if result is None:
            raise RuntimeError(f"Both models failed for {video_type} script.")

        result["destination"] = plan["destination"]
        result["country"] = plan["country"]

        filename = script_folder / f"{video_type}_script.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        
        print(f"Created: {filename}", flush=True)

    print("\nScript generation completed!")

if __name__ == "__main__":
    main()
