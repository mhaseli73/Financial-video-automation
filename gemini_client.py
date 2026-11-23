"""One shared Gemini helper (before, the same code was copied in 3 files)."""
import json
import os
import re
import time

from google import genai
from google.genai import types

PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-3.8-flash")
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
DEFAULT_DELAYS = [10, 30, 60]
TEMPORARY_ERRORS = {408, 429, 500, 502, 503, 504}


def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=120000))


def is_daily_quota_error(error):
    # Google writes the quota id as "...PerDay..." (no space), so we check that too.
    # We do NOT treat "free tier" as daily: per-minute limits also say "free tier".
    message = str(error).lower()
    return any(x in message for x in ["per day", "per_day", "perday", "daily"])


def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    data = json.loads(text)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        data = data[0]
    return data


def _call(client, model, prompt, temperature, max_tokens, delays):
    for attempt in range(len(delays) + 1):
        try:
            print(f"  Gemini: {model} (attempt {attempt + 1})", flush=True)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            if not response.text:
                raise ValueError("Empty response")
            return parse_json(response.text)
        except Exception as error:  # noqa: BLE001 - we decide below
            code = getattr(error, "code", None)
            if code == 429 and is_daily_quota_error(error):
                print(f"  Daily quota reached for {model}.", flush=True)
                return None
            retryable = code in TEMPORARY_ERRORS or code is None  # None = bad JSON / network
            if retryable and attempt < len(delays):
                wait = delays[attempt]
                print(f"  {type(error).__name__}: {str(error)[:150]} -> retry in {wait}s", flush=True)
                time.sleep(wait)
                continue
            print(f"  {model} failed: {str(error)[:200]}", flush=True)
            return None
    return None


def generate_json(prompt, temperature=0.7, max_tokens=8000, validate=None, delays=None):
    """Ask Gemini for JSON. Try the main model, then the fallback model.
    `validate(result)` returns None when OK, or a text that says what is wrong.
    Raises RuntimeError if both models fail."""
    delays = delays or DEFAULT_DELAYS
    client = get_client()
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        result = _call(client, model, prompt, temperature, max_tokens, delays)
        if result is None:
            continue
        problem = validate(result) if validate else None
        if problem is None:
            return result
        print(f"  {model} gave a bad result: {problem}", flush=True)
    raise RuntimeError("Both Gemini models failed or returned an invalid result.")
