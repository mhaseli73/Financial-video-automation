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
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60000))

def is_daily_quota_error(error):
    message = str(error).lower()
    indicators = ["per day", "per_day", "daily quota", "requests per day", "limit exceeded", "free tier"]
    return any(item in message for item in indicators)

def generate_with_retry(client, model, prompt):
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            print(f"Trying {model} (attempt {attempt + 1})...", flush=True)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.8,
                    max_output_tokens=1500
                )
            )
            if not response.text:
                return None
            result = json.loads(response.text)
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
            if not isinstance(history, list): history = []
        except:
            history = []

    recent_30 = history[-30:] if len(history) > 30 else history
    older_sample = random.sample(history[:-30], min(30, len(history) - 30)) if len(history) > 30 else []
    memory_context = recent_30 + older_sample
    
    recent_topics = [f"{item.get('destination')}" for item in memory_context if isinstance(item, dict)]
    all_past_topics = {f"{item.get('destination')}".lower() for item in history if isinstance(item, dict)}

    prompt = f"""
You are the AI director of a highly successful YouTube channel called "Money Explained". We use Stickman animations to explain finance.

Your target audience: United States, United Kingdom, Europe, and Australia.

Your task:
Choose ONE highly engaging topic related to PERSONAL FINANCE, WEALTH, or ECONOMICS.

CRITICAL RULES:
1. ROTATE CATEGORIES: Do not pick the same type of topic twice in a row. Rotate between:
   - Behavioral Finance (Psychology of money, impulse buying)
   - Beginner Investing (Compound interest, ETFs, risk)
   - Debt & Credit (Credit card traps, student loans)
   - Side Hustles (Passive income, freelancing)
   - Scams & Frauds (Ponzi schemes, phishing)
2. DO NOT give specific stock picks, financial advice, or legal tax advice. Focus on EDUCATION and human behavior.
3. VISUAL POTENTIAL: The topic must be easy to draw with stickmen (graphs, coins, wallets, brains).

Avoid recently selected topics:
{json.dumps(recent_topics, ensure_ascii=False)}

Return ONLY valid JSON:
{{
  "name": "The Topic (e.g., 'The Psychology of Why You Buy Things You Don't Need')",
  "country": "Global",
  "theme": "Behavioral Finance",
  "topic_angle": "The specific angle of the video",
  "audience_reason": "Why viewers will click on this",
  "visual_ideas": [
    "Stickman looking at a glowing shopping cart",
    "Stickman brain lighting up with a dollar sign",
    "Stickman breaking free from chains of debt"
  ]
}}
"""

    client = get_client()
    for attempt in range(3):
        result = generate_with_retry(client, PRIMARY_MODEL, prompt)
        if result is None:
            result = generate_with_retry(client, FALLBACK_MODEL, prompt)

        if result is None:
            raise RuntimeError("Both Gemini models failed.")

        generated_title = f"{result['name']}".lower()
        
        if generated_title not in all_past_topics:
            print("Topic successfully selected and verified unique!", flush=True)
            return result
        else:
            print(f"⚠️ Duplicate topic. Forcing retry...")

    raise RuntimeError("Failed to generate a unique topic after 3 attempts.")

if __name__ == "__main__":
    destination = choose_destination()
    print(json.dumps(destination, indent=4, ensure_ascii=False))
