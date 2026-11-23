"""Small helpers that are shared by several scripts."""
import json
import re
from pathlib import Path

from PIL import ImageFont

OUTPUT_DIR = Path("output")

FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "arialbd.ttf",
]

_EMOJI = re.compile("[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f\u200d]")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def find_font(size, bold=True):
    """Return a real TrueType font. The old code used 'arialbd.ttf', which does not
    exist on Linux, so Pillow used a tiny default font and text was unreadable."""
    for candidate in FONT_CANDIDATES_BOLD:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def headline(topic, max_chars=40):
    """'The Minimum Payment Trap: How Credit ...' -> 'The Minimum Payment Trap'."""
    core = (topic or "").split(":")[0].strip() or (topic or "").strip()
    if len(core) <= max_chars:
        return core
    cut = core[:max_chars].rsplit(" ", 1)[0]
    return cut or core[:max_chars]


def clean_for_speech(text):
    """Remove things a voice would read out loud by mistake (markdown, emojis, [notes])."""
    text = re.sub(r"\[[^\]]*\]", " ", text or "")
    text = _EMOJI.sub("", text)
    text = re.sub(r"[*_#`~]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def wrap_lines(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fit_text_block(draw, text, max_width, max_height, start_size, min_size=30, max_lines=4):
    """Find the biggest font size where the wrapped text fits in the box."""
    size = start_size
    while True:
        font = find_font(size)
        lines = wrap_lines(draw, text, font, max_width)
        line_h = int(size * 1.2)
        widest = max((draw.textlength(l, font=font) for l in lines), default=0)
        if (len(lines) <= max_lines and widest <= max_width and line_h * len(lines) <= max_height) \
                or size <= min_size:
            return font, lines, line_h
        size -= 4


def draw_centered_lines(draw, lines, font, center_x, center_y, line_h,
                        fill, stroke_width=0, stroke_fill=(0, 0, 0)):
    top = center_y - line_h * len(lines) / 2
    for i, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        draw.text((center_x - w / 2, top + i * line_h), line, font=font, fill=fill,
                  stroke_width=stroke_width, stroke_fill=stroke_fill)
    return top, top + line_h * len(lines)
