"""Automatic check of every script Gemini writes, BEFORE any image, voice or upload is made.

Two layers:
  1. RULES (plain Python, fast, always the same): brands, risky advice words, numbers that look
     invented, repeated sentences, wrong ending, very long sentences.
  2. AI EDITOR (a second Gemini call with a strict reviewer prompt): logic, contradictions,
     wrong facts, wrong arithmetic, unsafe advice, off-topic parts.

If there are blocking problems, Gemini is asked to rewrite the script to fix them (max 2 rounds).
If it still fails, the step stops with an error. The workflow then retries, which writes a NEW
script, and nothing is uploaded. Set SCRIPT_CHECK_STRICT=0 to only warn and continue.
The result is saved in output/scripts/<type>_check.json so you can read what was found.
"""
import json
import os
import re
from pathlib import Path

from common import save_json
from gemini_client import generate_json

MAX_REVISIONS = 2
STRICT = os.getenv("SCRIPT_CHECK_STRICT", "1") != "0"
SHORT_ENDING = "watch the full video on my channel to learn more"

BRANDS = [
    "visa", "mastercard", "american express", "amex", "paypal", "venmo", "robinhood", "coinbase",
    "binance", "tesla", "apple", "amazon", "google", "netflix", "spotify", "starbucks",
    "mcdonald", "walmart", "chase", "wells fargo", "bank of america", "barclays", "hsbc",
    "vanguard", "fidelity", "blackrock", "elon musk", "warren buffett", "dave ramsey",
]
RISKY_ADVICE = [
    r"guarantee[sd]?", r"risk[- ]free", r"can'?t lose", r"get rich quick", r"sure thing",
    r"double your money", r"you should (?:buy|sell|invest in)", r"(?:buy|sell) (?:this|these|that) (?:stock|coin|crypto|share)",
    r"never fails", r"always goes up", r"financial advice[,:]? (?:is|says)",
]
STAT_PATTERNS = (
    r"\d[\d,\.]*\s?(?:%|percent)", r"\b(?:million|billion|trillion)\b",
    r"\bstudies (?:show|say|found)\b", r"\bresearch (?:shows|says|found)\b",
    r"\bexperts (?:say|agree)\b", r"\baccording to\b", r"\bsurveys? (?:show|found)\b",
)
EXAMPLE_MARKERS = ("for example", "for instance", "imagine", "say you", "let's say", "lets say",
                   "suppose", "picture this", "what if", "pretend", "in this example")


def split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def _issue(severity, quote, problem, source="rule"):
    return {"severity": severity, "quote": quote[:200], "problem": problem, "source": source}


def rule_issues(narration, video_type, research_text=""):
    issues = []
    sentences = split_sentences(narration)
    research_lower = (research_text or "").lower()
    seen = set()

    for sentence in sentences:
        low = sentence.lower()

        for brand in BRANDS:
            if re.search(rf"\b{re.escape(brand)}\b", low):
                issues.append(_issue("error", sentence, f"Names a real brand or person ('{brand}'). Use a general word instead."))
                break

        for pattern in RISKY_ADVICE:
            if re.search(pattern, low):
                issues.append(_issue("error", sentence, "Risky or personal financial advice / promise. Make it general education."))
                break

        # Statistics: allowed only when shown as an example, or when the number is in the research text.
        if any(re.search(p, low) for p in STAT_PATTERNS) and not any(m in low for m in EXAMPLE_MARKERS):
            numbers = [n.strip(",.") for n in re.findall(r"\d[\d,\.]*", sentence)]
            if not numbers or not all(n in research_lower for n in numbers):
                issues.append(_issue("error", sentence,
                                     "Looks like an unsupported statistic. Say it is an example ('for example, imagine...') or remove it."))

        normalized = re.sub(r"[^a-z0-9 ]", "", low)
        if len(normalized.split()) >= 5 and normalized in seen:
            issues.append(_issue("error", sentence, "Repeated sentence."))
        seen.add(normalized)

        if len(sentence.split()) > 40:
            issues.append(_issue("warning", sentence, "Very long sentence. Hard to listen to."))

    ending = (sentences[-1] if sentences else "").lower()
    if video_type == "short":
        if SHORT_ENDING not in ending:
            issues.append(_issue("error", sentences[-1] if sentences else "",
                                 "The Short must end with: 'Watch the full video on my channel to learn more!'"))
    elif "?" not in ending and "comment" not in " ".join(sentences[-2:]).lower():
        issues.append(_issue("warning", sentences[-1] if sentences else "",
                             "The video should end with a question for the audience."))
    return issues


def ai_review(script, plan, research_text, style, video_type, long_narration=""):
    """Second Gemini call. Low temperature, strict editor, no creative writing."""
    structure = style["structure"] if video_type == "long" else "A 60-second teaser of the long video."
    source = ""
    if video_type == "short":
        source = f"\nLONG VIDEO SCRIPT (the Short may only use facts from this):\n{long_narration}\n"

    prompt = f"""
You are a strict editor and fact-checker for a YouTube finance education channel (cartoon style).
Check the script below. You are NOT a writer: do not rewrite it, only find real problems.

TOPIC: {plan['destination']}
TITLE: {script['title']}
EXPECTED STRUCTURE: {structure}
BACKGROUND (Wikipedia, may be empty): {research_text}
{source}
SCRIPT TO CHECK:
\"\"\"{script['narration']}\"\"\"

CHECK THESE POINTS:
1. LOGIC: Does each idea follow from the one before? Any contradiction? Any cause/effect claim that is wrong?
2. FACTS: Any claim that is false, misleading, or presented as a fact but cannot be verified?
   Invented statistics, studies, laws or numbers are errors.
3. ARITHMETIC: Recalculate EVERY calculation or number example step by step. Any mistake is an error.
4. SAFETY: Any personal financial advice, stock/crypto picks, tax or legal advice, or promise of results is an error.
5. FIT: Does the script match the title/topic and the expected structure? Is anything off-topic?
6. CLARITY: Is anything confusing for a beginner?

Mark severity "error" only for REAL problems (wrong, unsafe, illogical, unsupported). Use "warning" for small improvements.
Do not invent problems. If the script is fine, return verdict "pass" and an empty list.

Return ONLY valid JSON:
{{
  "verdict": "pass or fail",
  "issues": [
    {{"severity": "error or warning", "quote": "short exact quote from the script", "problem": "what is wrong", "fix": "how to fix it"}}
  ]
}}
"""

    def validate(result):
        if not isinstance(result, dict) or result.get("verdict") not in ("pass", "fail"):
            return "bad verdict"
        if not isinstance(result.get("issues", []), list):
            return "issues is not a list"
        return None

    result = generate_json(prompt, temperature=0.2, max_tokens=8000, validate=validate)
    issues = []
    for item in result.get("issues", []):
        if isinstance(item, dict):
            problem = str(item.get("problem", "")) + (f" Fix: {item['fix']}" if item.get("fix") else "")
            issues.append(_issue(item.get("severity", "warning") if item.get("severity") in ("error", "warning") else "warning",
                                 str(item.get("quote", "")), problem, source="ai"))
    return issues


def revise(script, issues, style, video_type):
    """Ask Gemini to fix ONLY the listed problems and keep everything else."""
    words = len(script["narration"].split())
    problems = "\n".join(f"- [{i['severity']}] \"{i['quote']}\" -> {i['problem']}" for i in issues)
    ending_rule = ('The script must still end with exactly: "Watch the full video on my channel to learn more!"'
                   if video_type == "short" else "The script must still end with a question for the audience.")

    prompt = f"""
You are editing a voice-over script for an animated cartoon finance YouTube video.
Rewrite the narration so that ALL problems below are fixed. Keep everything that is not a problem.

PROBLEMS:
{problems}

RULES:
- Keep the same style and structure, and about the same length ({int(words * 0.9)} to {int(words * 1.1)} words).
- Do not add statistics, brands, real people, stock tips, tax or legal advice.
- If a number is used, present it clearly as an example ("for example, imagine...") and make the maths correct.
- Plain spoken sentences only: no markdown, emojis, hashtags or notes in brackets.
- {ending_rule}

CURRENT NARRATION:
\"\"\"{script['narration']}\"\"\"

Return ONLY valid JSON: {{"narration": "the corrected full narration"}}
"""
    low, high = int(words * 0.65), int(words * 1.35)

    def validate(result):
        text = result.get("narration") if isinstance(result, dict) else None
        if not isinstance(text, str) or not low <= len(text.split()) <= high:
            return f"narration missing or not between {low} and {high} words"
        return None

    return generate_json(prompt, temperature=0.4, max_tokens=8000, validate=validate)["narration"]


def check_and_fix(script, plan, research_text, style, video_type, long_narration="", output_dir=Path("output")):
    """Return the (possibly corrected) script. Raises RuntimeError when it cannot be fixed (strict mode)."""
    from common import clean_for_speech  # local import: keeps this file easy to test

    history = []
    for round_number in range(MAX_REVISIONS + 1):
        print(f"  Script check ({video_type}), round {round_number + 1}...", flush=True)
        issues = rule_issues(script["narration"], video_type, research_text)
        try:
            issues += ai_review(script, plan, research_text, style, video_type, long_narration)
        except RuntimeError as error:
            # The reviewer itself is down. Rules still ran. Do not block a good script for this.
            print(f"  AI reviewer not available ({error}). Using rule checks only.", flush=True)

        errors = [i for i in issues if i["severity"] == "error"]
        history.append({"round": round_number + 1, "errors": len(errors), "issues": issues})
        print(f"  -> {len(errors)} error(s), {len(issues) - len(errors)} warning(s)", flush=True)
        for item in errors:
            print(f"     ERROR: \"{item['quote'][:80]}\" -> {item['problem'][:120]}", flush=True)

        if not errors:
            _save_report(output_dir, video_type, "passed", history)
            return script

        if round_number == MAX_REVISIONS:
            break
        script["narration"] = clean_for_speech(revise(script, errors, style, video_type))

    _save_report(output_dir, video_type, "failed", history)
    if STRICT:
        raise RuntimeError(f"The {video_type} script did not pass the check after {MAX_REVISIONS} revisions. "
                           f"See output/scripts/{video_type}_check.json")
    print("  WARNING: script still has errors, but SCRIPT_CHECK_STRICT=0 so the run continues.", flush=True)
    return script


def _save_report(output_dir, video_type, status, history):
    folder = Path(output_dir) / "scripts"
    folder.mkdir(parents=True, exist_ok=True)
    save_json(folder / f"{video_type}_check.json", {"status": status, "rounds": history})
