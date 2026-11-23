import json
import random
import re
from difflib import SequenceMatcher
from pathlib import Path

from gemini_client import generate_json

THEMES = [
    "Behavioral Finance",
    "Beginner Investing",
    "Debt & Credit",
    "Side Hustles",
    "Scams & Frauds",
    "Saving & Budgeting",
    "Economics Basics",
]

STOP_WORDS = {"the", "a", "an", "of", "to", "why", "how", "you", "your", "and", "in", "is",
              "for", "on", "that", "it", "what", "do", "does", "with", "keep", "keeps"}

REQUIRED_KEYS = ["name", "theme", "topic_angle", "audience_reason", "visual_ideas"]


def load_history():
    history_file = Path("output/decision_history.json")
    if not history_file.exists():
        return []
    try:
        history = json.loads(history_file.read_text(encoding="utf-8"))
        return history if isinstance(history, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _words(title):
    text = re.sub(r"[^a-z0-9 ]", " ", title.lower())
    return {w for w in text.split() if w not in STOP_WORDS}


def _similar(a, b):
    if not a or not b:
        return False
    if a.strip().lower() == b.strip().lower():
        return True
    if SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.8:
        return True
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= 0.6


def is_duplicate(title, past_titles):
    """The old check only caught identical titles. This also catches re-worded ones."""
    core = title.split(":")[0]
    for past in past_titles:
        if _similar(title, past) or _similar(core, past.split(":")[0]):
            return True
    return False


def validate_topic(result):
    if not isinstance(result, dict):
        return "not a JSON object"
    missing = [k for k in REQUIRED_KEYS if not result.get(k)]
    if missing:
        return f"missing keys: {missing}"
    return None


def choose_destination():
    """Pick today's finance topic. (Function name kept so other files still work.)"""
    history = load_history()
    entries = [h for h in history if isinstance(h, dict) and h.get("destination")]

    # Old travel entries (Phuket, Maui...) have a real country. Finance topics use "Global".
    finance = [h for h in entries if h.get("country") == "Global" or h.get("theme")]

    recent = finance[-30:]
    older = finance[:-30]
    sample = random.sample(older, min(30, len(older))) if older else []
    avoid_titles = [h["destination"] for h in recent + sample]
    all_past_titles = [h["destination"] for h in entries]

    # The old prompt asked to "rotate categories" but never told the model the last category.
    recent_themes = [h["theme"] for h in finance[-3:] if h.get("theme")]

    rejected = []
    for attempt in range(3):
        extra = ""
        if rejected:
            extra = "\nThese were rejected as duplicates, pick something clearly different:\n" \
                    + json.dumps(rejected, ensure_ascii=False)

        prompt = f"""
You are the AI director of a successful YouTube channel called "Money Explained". We use Stickman animations to explain finance.

Target audience: United States, United Kingdom, Europe and Australia.

Your task: choose ONE highly engaging topic about PERSONAL FINANCE, WEALTH or ECONOMICS.

CRITICAL RULES:
1. ROTATE CATEGORIES. Allowed themes: {json.dumps(THEMES)}.
   The most recent themes were (oldest first): {json.dumps(recent_themes)}. Do NOT use any of them again.
2. DO NOT give specific stock picks, personal financial advice, or legal or tax advice. Focus on EDUCATION and human behavior.
3. VISUAL POTENTIAL: the topic must be easy to draw with stickmen (graphs, coins, wallets, brains).
4. The topic must not be similar to these past topics:
{json.dumps(avoid_titles, ensure_ascii=False)}
{extra}

Return ONLY valid JSON:
{{
  "name": "The Topic (e.g. 'The Psychology of Why You Buy Things You Don't Need')",
  "country": "Global",
  "theme": "One of the allowed themes, written exactly",
  "topic_angle": "The specific angle of the video",
  "audience_reason": "Why viewers will click on this",
  "research_query": "2-4 words to look up on Wikipedia, e.g. 'Hedonic treadmill'",
  "visual_ideas": [
    "Stickman looking at a glowing shopping cart",
    "Stickman brain lighting up with a dollar sign",
    "Stickman breaking free from chains of debt"
  ]
}}
"""
        # max_tokens is high because newer Gemini models also count "thinking" tokens in it.
        result = generate_json(prompt, temperature=0.8, max_tokens=4000, validate=validate_topic)
        title = str(result["name"]).strip()

        if is_duplicate(title, all_past_titles):
            print(f"Duplicate topic, trying again: {title}", flush=True)
            rejected.append(title)
            continue

        result["name"] = title
        result.setdefault("country", "Global")
        if not isinstance(result["visual_ideas"], list):
            result["visual_ideas"] = [str(result["visual_ideas"])]
        print("Topic selected and verified unique!", flush=True)
        return result

    raise RuntimeError("Failed to generate a unique topic after 3 attempts.")


if __name__ == "__main__":
    print(json.dumps(choose_destination(), indent=4, ensure_ascii=False))
