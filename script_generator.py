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

NETWORK_ERRORS = {
    "remoteprotocolerror", "connecterror", "readerror", "writeerror",
    "connecttimeout", "readtimeout", "writetimeout", "pooltimeout",
    "timeoutexception", "networkerror", "protocolerror",
}

def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")
    
    # ADDED: Timeout of 60 seconds so it doesn't hang forever
    return genai.Client(
        api_key=api_key, 
        http_options=types.HttpOptions(timeout=60000) 
    )

def is_daily_quota_error(error):
    message = str(error).lower()
    indicators = ["per day", "per_day", "daily quota", "requests per day", "limit exceeded", "free tier"]
    return any(item in message for item in indicators)

def is_retryable_error(error):
    current = error
    while current is not None:
        error_name = type(current).__name__.lower()
        error_message = str(current).lower()

        if isinstance(current, errors.APIError):
            status = getattr(current, "code", None)
            if status == 429 and is_daily_quota_error(current):
                return False
            if status in TEMPORARY_ERRORS:
                return True

        if error_name in NETWORK_ERRORS:
            return True
        if isinstance(current, json.JSONDecodeError):
            return True
        if "empty gemini response" in error_message:
            return True
        if "server disconnected" in error_message:
            return True

        current = (current.__cause__ or current.__context__)
    return False

def generate_with_retry(client, model, prompt):
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            print(f"Trying {model} (attempt {attempt + 1}/{len(RETRY_DELAYS) + 1})...", flush=True)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.8,
                    max_output_tokens=4000
                )
            )
            if not response.text:
                raise RuntimeError("Empty Gemini response")
            result = json.loads(response.text)
            if not isinstance(result, dict):
                raise ValueError("Gemini response must be a JSON object")
            return result
        except Exception as error:
            print(f"Error with {model}: {type(error).__name__}: {error}", flush=True)
            if not is_retryable_error(error):
                if (isinstance(error, errors.APIError) and getattr(error, "code", None) == 429 and is_daily_quota_error(error)):
                    print("Daily API quota exhausted. Skipping further retries.", flush=True)
                    return None
                raise
            if attempt < len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempt]
                print(f"Temporary error detected. Retrying in {delay} seconds...", flush=True)
                time.sleep(delay)
            else:
                print(f"{model} failed after all retries.", flush=True)
    return None

def validate_script(result):
    if not isinstance(result, dict):
        return False
    required = ["title", "hook", "narration", "visual_suggestions", "description", "tags"]
    for field in required:
        if field not in result:
            return False
    text_fields = ["title", "hook", "narration", "description"]
    if not all(isinstance(result[field], str) and result[field].strip() for field in text_fields):
        return False
    if not isinstance(result["visual_suggestions"], list):
        return False
    if not isinstance(result["tags"], list):
        return False
    return True

def generate_script(plan, research, client):
    video_type = plan["video_type"]
    if video_type == "short":
        target_words = "120 to 140 words"
        duration = "60 seconds"
    elif video_type == "long":
        target_words = "480 to 520 words"
        duration = "4 minutes"
    else:
        raise ValueError(f"Unknown video type: {video_type}")

    # --- UPGRADED PROMPT FOR PRACTICAL TRAVEL GUIDE ---
    prompt = f"""
You are a professional travel vlogger and YouTube strategist creating a PRACTICAL TRAVEL GUIDE.

Create an original, engaging English travel script.

DESTINATION: {plan['destination']}, {plan['country']}
MAIN THEME: {plan.get('theme', '')}
VIDEO CONCEPT: {plan.get('topic_angle', '')}
TARGET AUDIENCE: United States, United Kingdom, Europe and Australia.
AUDIENCE INTEREST: {plan.get('audience_reason', '')}
RESEARCH: {research.get('description', '')}
VISUAL IDEAS: {json.dumps(plan.get('visual_ideas', []), ensure_ascii=False)}

VIDEO FORMAT: {video_type}
TARGET DURATION: {duration}
TARGET SCRIPT LENGTH: {target_words}

INSTRUCTIONS:
1. THE HOOK: Start with a highly engaging, practical hook. (e.g., "Thinking of visiting [Place]? Here are the 3 things you MUST know before you book", or "Don't book a hotel in [Place] until you see this").
2. PRACTICAL ADVICE: Focus on what tourists actually need to know (best beaches, hotel areas, food to try, how to get around).
3. CONVERSATIONAL TONE: Write like a friendly travel vlogger speaking directly to the viewer. Avoid sounding like an encyclopedia.
4. Provide specific details only if supported by the research. Do not invent prices or facts.
5. Make the narration suitable for voice-over. Use short, punchy sentences.
6. SEO: Include keywords in the title and description (e.g., "[Place] Travel Guide", "Best things to do in [Place]").
7. End with a natural audience engagement question (e.g., "Have you been to [Place]? Let me know in the comments!").

For SHORT:
Focus on 1 to 3 rapid-fire, highly valuable travel tips or one amazing location. Fast-paced and visual.

For LONG:
Create a structured travel guide with:
- Hook
- Best Beaches / Main Attractions
- Where to Stay (Neighborhoods/Hotels)
- Local Food & Culture
- Getting Around (Transport)
- Conclusion & Engagement Question

Return ONLY valid JSON:
{{
  "title": "Video title (SEO optimized)",
  "hook": "Opening hook",
  "narration": "Complete voice-over script",
  "visual_suggestions": [
    "Visual suggestion 1",
    "Visual suggestion 2"
  ],
  "description": "YouTube video description with SEO tags",
  "tags": ["travel guide", "destination", "best beaches"]
}}
"""

    print(f"Generating {video_type} script...", flush=True)
    result = generate_with_retry(client, PRIMARY_MODEL, prompt)

    if result is None:
        print("Primary model unavailable. Switching to fallback model...", flush=True)
        result = generate_with_retry(client, FALLBACK_MODEL, prompt)

    if result is None:
        raise RuntimeError(f"Both Gemini models failed for {video_type} script.")

    if not validate_script(result):
        raise ValueError(f"Invalid script structure for {video_type}")

    result["destination"] = plan["destination"]
    result["country"] = plan["country"]

    print(f"{video_type.capitalize()} script generated successfully!", flush=True)
    return result

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
        print(f"\nGenerating: {video_type}", flush=True)
        filename = f"{video_type}_script.json"
        json_path = script_folder / filename

        # Reuse a valid script only for the same destination.
        if json_path.exists():
            try:
                existing = json.loads(json_path.read_text(encoding="utf-8"))
                if (validate_script(existing) and existing.get("destination") == plan["destination"] and existing.get("country") == plan["country"]):
                    print(f"Valid existing script found for {plan['destination']}. Skipping regeneration.", flush=True)
                    continue
            except (json.JSONDecodeError, OSError):
                print("Existing script is invalid. Generating a new one.", flush=True)

        result = generate_script(plan, research, client)

        with open(json_path, "w", encoding="utf-8") as file:
            json.dump(result, file, indent=4, ensure_ascii=False)

        text_file = script_folder / (f"{video_type}_script.txt")
        text_file.write_text(result["title"] + "\n\n" + result["narration"], encoding="utf-8")

        print(f"Created: {filename}", flush=True)

    print("\nGemini script generation completed!", flush=True)

if __name__ == "__main__":
    main()
