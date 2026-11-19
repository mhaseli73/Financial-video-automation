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
    return genai.Client(api_key=api_key)

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
                print("Gemini returned an empty response.")
                return None
            try:
                result = json.loads(response.text)
            except json.JSONDecodeError as error:
                print(f"Invalid JSON from {model}: {error}", flush=True)
                return None
            if not isinstance(result, dict):
                print("Gemini response is not a JSON object.")
                return None
            return result
        except errors.APIError as error:
            status = getattr(error, "code", None)
            print(f"Gemini API error: {status} - {error}", flush=True)
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

    recent_destinations = [
        f"{item.get('destination')} ({item.get('topic_angle')})"
        for item in history[-20:]
        if isinstance(item, dict)
    ]

    # --- PRACTICAL TRAVEL GUIDE PROMPT ---
    prompt = f"""
You are the AI director of a popular travel guide YouTube channel called "Amazing Places Around the World".

Your target audience:
United States, United Kingdom, Europe, and Australia.

Your task:
Choose ONE tourist destination (a city, a specific beach town, or a region) and create a PRACTICAL TRAVEL GUIDE angle for today's video.

CRITICAL RULES:
1. FOCUS ON PRACTICAL TOURISM: The video should cover things like the best beaches, quality of hotels, local food to try, how to get there, and what to do.
2. VISUAL POTENTIAL: The destination must have visuals that can be easily found in generic stock footage libraries (e.g., beautiful beaches, hotel rooms, food, city streets, airplanes). 
3. AVOID: Mysteries, dark history, extreme survival, and industrial topics.

Example of a good topic_angle: 
"A Complete Guide to Can Picafort: Beaches, Hotels, and Where to Eat in Mallorca"

Avoid recently selected destinations:
{json.dumps(recent_destinations, ensure_ascii=False)}

Return ONLY valid JSON with these fields:

{{
  "name": "Destination name (e.g., Can Picafort)",
  "country": "Country (e.g., Spain)",
  "theme": "Practical Travel Guide",
  "topic_angle": "Specific guide angle (e.g., Best beaches and local food in [Place])",
  "audience_reason": "Why viewers will want this practical travel information",
  "visual_ideas": [
    "Visual idea 1 (e.g., Mediterranean beach resort)",
    "Visual idea 2 (e.g., Paella local food)",
    "Visual idea 3 (e.g., Tourists walking in a coastal town)"
  ]
}}
"""

    client = get_client()
    print("Trying primary Gemini model...", flush=True)
    
    result = generate_with_retry(client, PRIMARY_MODEL, prompt)

    if result is None:
        print("Switching to fallback model...", flush=True)
        result = generate_with_retry(client, FALLBACK_MODEL, prompt)

    if result is None:
        raise RuntimeError("Both Gemini models failed.")

    required = ["name", "country", "theme", "topic_angle", "audience_reason", "visual_ideas"]
    for field in required:
        if field not in result:
            raise ValueError(f"Gemini response missing: {field}")
    if not all(isinstance(result[field], str) and result[field].strip() for field in required[:5]):
        raise ValueError("Invalid destination information")
    if (not isinstance(result["visual_ideas"], list) or not result["visual_ideas"]):
        raise ValueError("Invalid visual ideas")

    print("Destination successfully selected!", flush=True)
    return result

if __name__ == "__main__":
    destination = choose_destination()
    print(json.dumps(destination, indent=4, ensure_ascii=False))
