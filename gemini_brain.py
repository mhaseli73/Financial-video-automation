import os
import json
import time
import random
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
    
    # ADDED: Timeout of 60 seconds so it doesn't hang forever
    return genai.Client(
        api_key=api_key, 
        http_options=types.HttpOptions(timeout=60000) 
    )

def is_daily_quota_error(error):
    message = str(error).lower()
    indicators = ["per day", "per_day", "daily quota", "requests per day", "limit exceeded", "free tier"]
    return any(item in message for item in indicators)

def generate_with_retry(client, model, prompt):
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            print(f"Trying {model} (attempt {attempt + 1}/{len(RETRY_DELAYS) + 1})...", flush=True)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7, 
                    max_output_tokens=1500
                )
            )
            if not response.text:
                return None
            try:
                result = json.loads(response.text)
            except json.JSONDecodeError as error:
                print(f"Invalid JSON from {model}: {error}", flush=True)
                return None
            if not isinstance(result, dict):
                return None
            return result
        except errors.APIError as error:
            status = getattr(error, "code", None)
            if status == 429 and is_daily_quota_error(error):
                return None
            if status not in TEMPORARY_ERRORS:
                raise
            if attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
    return None

def choose_destination():
    history_file = Path("output/decision_history.json")
    history = []

    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except (json.JSONDecodeError, OSError):
            history = []

    # --- NEW: HYBRID MEMORY SYSTEM ---
    recent_30 = history[-30:] if len(history) > 30 else history
    
    older_sample = []
    if len(history) > 30:
        older_sample = random.sample(history[:-30], min(30, len(history) - 30))
    
    memory_context = recent_30 + older_sample
    recent_destinations = [
        f"{item.get('destination')} ({item.get('topic_angle')})"
        for item in memory_context
        if isinstance(item, dict)
    ]

    all_past_titles = {
        f"{item.get('destination')} ({item.get('topic_angle')})".lower() 
        for item in history if isinstance(item, dict)
    }

    prompt = f"""
You are the AI director of a popular travel guide YouTube channel called "Amazing Places Around the World".

Your target audience: United States, United Kingdom, Europe, and Australia.

Choose ONE tourist destination and a PRACTICAL TRAVEL GUIDE angle.

CRITICAL RULES:
1. FOCUS ON PRACTICAL TOURISM: Best beaches, quality of hotels, local food, how to get there.
2. VISUAL POTENTIAL: Use visuals easily found in stock footage (beaches, hotels, food, streets).
3. GEOGRAPHIC DIVERSITY: Try to pick a country different from the last 3 videos.
4. Here is a sample of past topics (recent and random older ones). DO NOT REPEAT ANY OF THESE:
{json.dumps(recent_destinations, ensure_ascii=False)}

Return ONLY valid JSON:
{{
  "name": "Destination name",
  "country": "Country",
  "theme": "Practical Travel Guide",
  "topic_angle": "Specific guide angle",
  "audience_reason": "Why viewers will want this",
  "visual_ideas": ["Idea 1", "Idea 2", "Idea 3"]
}}
"""

    client = get_client()
    print("Trying primary Gemini model...", flush=True)
    
    for attempt in range(3):
        result = generate_with_retry(client, PRIMARY_MODEL, prompt)
        if result is None:
            result = generate_with_retry(client, FALLBACK_MODEL, prompt)

        if result is None:
            raise RuntimeError("Both Gemini models failed.")

        generated_title = f"{result['name']} ({result['topic_angle']})".lower()
        
        if generated_title not in all_past_titles:
            print("Destination successfully selected and verified unique!", flush=True)
            return result
        else:
            print(f"⚠️ AI generated a duplicate title ({generated_title}). Forcing retry...")

    raise RuntimeError("Failed to generate a unique title after 3 attempts.")

if __name__ == "__main__":
    destination = choose_destination()
    print(json.dumps(destination, indent=4, ensure_ascii=False))
