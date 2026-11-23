import json
import shutil
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import main
import researcher
import script_generator
import scene_planner
import visual_fetcher
import voiceover_generator
import video_renderer
import thumbnail_generator
import youtube_uploader

OUTPUT = Path("output")
STATE_FILE = OUTPUT / "run_state.json"
KEEP = {"decision_history.json", "bgm.mp3"}
RESUME_HOURS = 12  # a failed run can be continued for 12 hours

STEPS = [
    ("Topic Selection", main.main),
    ("Topic Research", researcher.main),
    ("Video Script Generation", script_generator.main),
    ("Scene Planning", scene_planner.main),
    ("Visual Acquisition", visual_fetcher.main),
    ("Voiceover Generation", voiceover_generator.main),
    ("Video Rendering", video_renderer.main),
    ("Thumbnail Generation", thumbnail_generator.main),
    ("YouTube Upload", youtube_uploader.main),
    ("Save Topic History", main.record_history),
]


def run_step(name, function):
    print(f"\n{'=' * 50}", flush=True)
    print(f"STARTING: {name}", flush=True)
    start_time = time.time()
    try:
        function()
        print(f"COMPLETED: {name} ({round(time.time() - start_time, 2)} seconds)", flush=True)
    except Exception as error:
        print(f"FAILED: {name}: {error}", flush=True)
        traceback.print_exc()
        raise


def load_state():
    """Return the finished steps of an unfinished run, or None when we must start fresh."""
    if not STATE_FILE.exists():
        return None
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        started = datetime.fromisoformat(state["started"])
        age_hours = (datetime.now(timezone.utc) - started).total_seconds() / 3600
        return state if age_hours < RESUME_HOURS else None
    except (ValueError, KeyError, OSError):
        return None


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def clean_generated_files():
    """Start of a NEW run: delete everything from older runs (keep history and music).
    Needed because the image step now reuses existing images when it resumes."""
    OUTPUT.mkdir(exist_ok=True)
    for item in OUTPUT.iterdir():
        if item.name in KEEP:
            continue
        shutil.rmtree(item) if item.is_dir() else item.unlink()


def run_pipeline():
    print("Starting Money Explained Video AI Pipeline...", flush=True)

    state = load_state()
    if state:
        print(f"Resuming an unfinished run. Done so far: {state['done']}", flush=True)
    else:
        clean_generated_files()
        state = {"started": datetime.now(timezone.utc).isoformat(), "done": []}
        save_state(state)

    # Why: the workflow retries the whole script when it fails. Before, every retry picked
    # a NEW topic, made all images again (~25 min) and could upload the same video twice.
    for name, function in STEPS:
        if name in state["done"]:
            print(f"Skipping (already done): {name}", flush=True)
            continue
        run_step(name, function)
        state["done"].append(name)
        save_state(state)

    # Run is complete: remove the resume files so the next run starts clean.
    STATE_FILE.unlink(missing_ok=True)
    youtube_uploader.STATE_FILE.unlink(missing_ok=True)
    print("\nPipeline completed successfully! Videos and thumbnails are on YouTube.", flush=True)


if __name__ == "__main__":
    run_pipeline()
