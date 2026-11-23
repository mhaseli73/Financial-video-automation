import json
from datetime import datetime, timezone
from pathlib import Path

from common import load_json, save_json
from gemini_brain import choose_destination, load_history
from styles import pick_style

AUDIENCE = "English-speaking viewers in the US, UK, Europe and Australia"


def main():
    """Step 1: pick a topic and write output/video_plan.json.
    (The topic is saved to history LATER, by record_history(), only after the upload worked.
    Before, a failed run still 'used up' a topic, and every retry added another entry.)"""
    output = Path("output")
    output.mkdir(exist_ok=True)

    print("Gemini AI is selecting today's topic...")
    topic = choose_destination()
    print("Selected:", topic["name"], "|", topic.get("theme", ""))
    style = pick_style(load_history())
    print("Video style:", style)

    common = {
        "style": style,
        "destination": topic["name"],  # key name kept so older files/history keep working
        "country": topic.get("country", "Global"),
        "theme": topic.get("theme", ""),
        "topic_angle": topic["topic_angle"],
        "audience_reason": topic.get("audience_reason", ""),
        "research_query": topic.get("research_query", ""),
        "visual_ideas": topic.get("visual_ideas", []),
        "language": "English",
        "audience": AUDIENCE,
        "status": "planned",
    }
    plans = [
        {**common, "video_type": "short", "duration": 60},
        {**common, "video_type": "long", "duration": 240},
    ]
    save_json(output / "video_plan.json", plans)
    print("AI video plans created successfully!")
    print(json.dumps(plans, indent=4, ensure_ascii=False))


def record_history():
    """Last step of the pipeline: remember the topic so it is not used again."""
    output = Path("output")
    plan = load_json(output / "video_plan.json")[0]
    history_file = output / "decision_history.json"

    history = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            history = []
    if not isinstance(history, list):
        history = []

    if any(isinstance(h, dict) and h.get("destination") == plan["destination"] for h in history):
        print("Topic already in history.")
        return

    history.append({
        "destination": plan["destination"],
        "country": plan["country"],
        "theme": plan.get("theme", ""),
        "style": plan.get("style", ""),
        "topic_angle": plan["topic_angle"],
        "date": datetime.now(timezone.utc).isoformat(),
    })
    save_json(history_file, history)
    print("Topic saved to history.")


if __name__ == "__main__":
    main()
