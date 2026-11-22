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
    if not api_key: raise RuntimeError("GEMINI_API_KEY is missing")
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60000))

def generate_with_retry(client, model, prompt):
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            response = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7, max_output_tokens=4000)
            )
            if not response.text: return None
            return json.loads(response.text)
        except Exception as error:
            status = getattr(error, "code", None)
            if status in TEMPORARY_ERRORS and attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
            else: return None
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
    
    # Force Long video to be processed FIRST so the Short can summarize it
    plans = sorted(plans, key=lambda x: 0 if x["video_type"] == "long" else 1)
    
    long_script_narration = ""

    for plan in plans:
        video_type = plan["video_type"]
        
        if video_type == "short":
            prompt = f"""
You are a YouTube Shorts strategist. 
We just made a 4-minute long video about: {plan['destination']}
Here is the full script of the long video:
"{long_script_narration}"

Write a 60-second script (120-140 words) that acts as a TEASER for this long video.
1. Start with a shocking hook based on the long video.
2. Give 2-3 rapid-fire logical facts from the long script.
3. End by saying: "Watch the full video on my channel to learn more!"
Return ONLY valid JSON:
{{
  "title": "Punchy Short Title #Shorts",
  "hook": "Shocking hook",
  "narration": "Complete voice-over script",
  "visual_suggestions": ["Visual 1", "Visual 2"],
  "description": "Link to full video",
  "tags": ["finance", "money", "shorts"]
}}
"""
        else:
            prompt = f"""
You are a professional YouTube scriptwriter creating a Stickman animated finance explainer.

TOPIC: {plan['destination']}
MAIN THEME: {plan.get('theme', '')}
VIDEO CONCEPT: {plan.get('topic_angle', '')}
AUDIENCE INTEREST: {plan.get('audience_reason', '')}
RESEARCH: {research.get('description', '')}

TARGET DURATION: 240 seconds (480 to 520 words)

CRITICAL LOGIC RULES:
1. DO NOT invent specific stock tips, tax laws, or fake statistics. 
2. You MUST follow a logical "Problem -> Psychology -> Solution" framework.
3. Use simple, real-world examples (e.g., coffee, subscriptions, groceries).
4. The advice must be practical, safe, and universally applicable.

INSTRUCTIONS:
1. THE HOOK: Start with a highly engaging, relatable problem about money.
2. THE PSYCHOLOGY: Explain WHY we make this financial mistake (behavioral finance).
3. THE SOLUTION: Give 3 actionable, logical steps on how to fix it and save money.
4. End with a natural audience engagement question (e.g., "What's your biggest money leak? Let me know in the comments!").

Return ONLY valid JSON:
{{
  "title": "Video title (SEO optimized)",
  "hook": "Opening hook",
  "narration": "Complete voice-over script",
  "visual_suggestions": ["Visual 1", "Visual 2"],
  "description": "YouTube video description",
  "tags": ["finance", "psychology", "explainer"]
}}
"""

        print(f"Generating {video_type} script...", flush=True)
        result = generate_with_retry(client, PRIMARY_MODEL, prompt)
        if result is None:
            result = generate_with_retry(client, FALLBACK_MODEL, prompt)
        if result is None: raise RuntimeError(f"Script failed for {video_type}.")

        if video_type == "long":
            long_script_narration = result["narration"]

        result["destination"] = plan["destination"]
        result["country"] = plan["country"]

        filename = script_folder / f"{video_type}_script.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        
        print(f"Created: {filename}", flush=True)

if __name__ == "__main__":
    main()
