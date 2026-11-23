import requests
from pathlib import Path
from urllib.parse import quote

from common import headline, load_json, save_json

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"
HEADERS = {"User-Agent": "MoneyExplainedResearchBot/1.0 (educational finance videos)"}


def find_page_title(query):
    """The old code used the whole video title as a Wikipedia page name (always a 404
    for a finance title). Here we search first and take the best matching page."""
    response = requests.get(
        WIKI_API,
        params={"action": "query", "list": "search", "srsearch": query,
                "srlimit": 1, "format": "json"},
        headers=HEADERS, timeout=20,
    )
    response.raise_for_status()
    hits = response.json().get("query", {}).get("search", [])
    return hits[0]["title"] if hits else None


def fetch_summary(title):
    response = requests.get(WIKI_SUMMARY + quote(title.replace(" ", "_"), safe=""),
                            headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.json()


def research_topic(plan):
    result = {
        "destination": plan["destination"],
        "country": plan["country"],
        "topic_angle": plan.get("topic_angle", ""),
        "audience_reason": plan.get("audience_reason", ""),
        "visual_ideas": plan.get("visual_ideas", []),
        "theme": plan.get("theme", ""),
        "description": "",
        "source": "",
        "status": "failed",
    }

    queries = [q for q in [plan.get("research_query"), headline(plan["destination"])] if q]
    for query in queries:
        try:
            title = find_page_title(query)
            if not title:
                continue
            data = fetch_summary(title)
            if data.get("type") == "disambiguation" or not data.get("extract"):
                continue
            result["description"] = data["extract"]
            result["source"] = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            result["status"] = "success"
            break
        except requests.RequestException as error:
            result["error"] = str(error)
    return result


def main():
    output = Path("output")
    output.mkdir(exist_ok=True)
    plans = load_json(output / "video_plan.json")
    result = research_topic(plans[0])
    save_json(output / "destination_research.json", result)
    # A failed lookup is not fatal: the script generator works without it.
    print("Research completed:", result["status"])


if __name__ == "__main__":
    main()
