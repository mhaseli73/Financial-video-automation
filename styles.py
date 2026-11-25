"""Video styles. Each day one style is chosen, so videos do not all look and sound the same.
A style changes: script structure, length, opening type, picture colors, title color/position,
zoom amount and background music. The style is saved in the history, and the last 3 styles
are not used again."""
import os
import random

STYLES = {
    "problem_solution": {
        "structure": (
            "1. THE HOOK: a relatable money problem (first 2 sentences).\n"
            "2. THE EXPLANATION: why this happens (psychology, maths or how the system works).\n"
            "3. THE SOLUTION: 3 clear, practical steps.\n"
            "4. End with a question for the audience."),
        "hook": "Open with a relatable everyday money problem.",
        "words": (580, 620),
        "accent": "red", "title_color": (255, 235, 0), "title_y": 0.5, "zoom": 0.08,
    },
    "myth_vs_fact": {
        "structure": (
            "Present 4 common money MYTHS about this topic. For each one: say the myth, say "
            "why people believe it, then give the simple truth. Finish with one short rule to remember "
            "and a question for the audience."),
        "hook": "Open with: 'Almost everyone believes this about money, and it is wrong.'",
        "words": (520, 580),
        "accent": "blue", "title_color": (120, 220, 255), "title_y": 0.5, "zoom": 0.06,
    },
    "story": {
        "structure": (
            "Tell it as ONE short story about a cartoon character (give him a simple first name). "
            "Follow him through a money situation in 3 stages: the mistake, the moment he notices, "
            "the change he makes. Explain the idea through what happens to him. Finish with the "
            "lesson in two sentences and a question for the audience."),
        "hook": "Open in the middle of the story, with the character in trouble.",
        "words": (600, 680),
        "accent": "green", "title_color": (150, 255, 150), "title_y": 0.8, "zoom": 0.10,
    },
    "what_if": {
        "structure": (
            "Build the video around a 'What if...?' question. Use ONE simple example with round, "
            "clearly illustrative numbers (say 'for example'; never present them as real statistics). "
            "Show what happens after 1 year, 10 years and 30 years, then explain the lesson and "
            "give 2 practical takeaways. End with a question for the audience."),
        "hook": "Open with a surprising 'What if...?' question.",
        "words": (540, 600),
        "accent": "orange", "title_color": (255, 170, 60), "title_y": 0.5, "zoom": 0.12,
    },
    "countdown": {
        "structure": (
            "Make it a countdown of 5 items (signs, traps or habits) related to the topic, from 5 down "
            "to 1. Give each item about the same time: name it, explain it, give a quick fix. "
            "Finish with a one-sentence summary and a question for the audience."),
        "hook": "Open by saying how many items there are and why the last one is the most important.",
        "words": (560, 620),
        "accent": "purple", "title_color": (230, 160, 255), "title_y": 0.8, "zoom": 0.07,
    },
    "question_answer": {
        "structure": (
            "Write it as a conversation: a curious viewer asks 4 short questions about the topic "
            "and you answer each one clearly in simple words. Questions should be real things "
            "beginners ask. Finish with the single most important idea and a question for the audience."),
        "hook": "Open with the question beginners ask most about this topic.",
        "words": (500, 560),
        "accent": "teal", "title_color": (100, 255, 230), "title_y": 0.5, "zoom": 0.09,
    },
}


def pick_style(history):
    """Choose a style that was not used in the last 3 videos."""
    recent = [h.get("style") for h in history[-3:] if isinstance(h, dict)]
    choices = [s for s in STYLES if s not in recent] or list(STYLES)
    return random.choice(choices)


def get_style(style_id):
    return STYLES.get(style_id) or STYLES["problem_solution"]


# ---------------------------------------------------------------------------------------------
# PICTURE STYLE. Default is "cartoon". Set the env var IMAGE_STYLE=stickman to go back to the old look.
# ---------------------------------------------------------------------------------------------
VISUALS = {
    "cartoon": {
        "name": "cartoon",
        "character": ("a friendly original cartoon character: a young man with short brown hair, "
                      "a blue shirt and a big smile"),
        "prefix": ("Colorful flat vector cartoon illustration, friendly characters with big expressive "
                   "faces, clean bold outlines, bright cheerful colors with {accent} as the main accent color, "
                   "simple clean background, original characters (not similar to any existing cartoon or brand), "
                   "no text, no letters, no logos, showing: "),
        "scene_rules": ("colorful CARTOON illustration about FINANCE (friendly cartoon characters with money, "
                        "credit cards, charts, piggy banks, wallets; stressed or happy about money)"),
        "fallback": "A friendly cartoon character thinking about money, with a coin and a chart. Scene about: ",
    },
    "stickman": {
        "name": "stickman",
        "character": "a simple stickman",
        "prefix": ("Stickman drawing, thick black marker, white background, minimalist cartoon, "
                   "with {accent} marker accents, no text, no letters, of: "),
        "scene_rules": ("simple STICKMAN cartoon about FINANCE (stickmen with money, credit cards, charts, "
                        "piggy banks, graphs, wallets; stressed or happy about money)"),
        "fallback": "A stickman thinking about money, with a coin and a chart. Scene about: ",
    },
}


def visual():
    return VISUALS.get(os.getenv("IMAGE_STYLE", "cartoon").lower(), VISUALS["cartoon"])


def image_prefix(accent):
    return visual()["prefix"].format(accent=accent)
