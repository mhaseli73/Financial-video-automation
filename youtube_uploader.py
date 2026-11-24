import json
import os
import re
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from common import load_json, save_json

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
DISCLAIMER = ("Disclaimer: This video is for educational purposes only and is not "
              "financial, investment, tax or legal advice.")
STATE_FILE = Path("output/uploaded.json")


# ---------- text helpers (YouTube rejects titles > 100 chars and '<' '>' characters) ----------
def clean_text(text):
    return re.sub(r"[<>]", "", text or "").strip()


def make_title(title, is_short):
    title = re.sub(r"#shorts", "", clean_text(title), flags=re.I)
    title = re.sub(r"\s+", " ", title).strip()
    suffix = " #Shorts" if is_short else ""
    limit = 100 - len(suffix)  # the old code added '#Shorts' AFTER cutting to 100 -> 108 chars -> API error
    if len(title) > limit:
        title = title[:limit].rsplit(" ", 1)[0]
    return title + suffix


def make_description(text):
    # YouTube limit is 5000 BYTES, not characters.
    return clean_text(text).encode("utf-8")[:4900].decode("utf-8", errors="ignore")


def make_tags(tags):
    clean, total = [], 0
    for tag in tags or []:
        tag = clean_text(str(tag)).lstrip("#")
        cost = len(tag) + (2 if " " in tag else 0) + 1
        if tag and tag.lower() not in [t.lower() for t in clean] and total + cost <= 450:
            clean.append(tag)
            total += cost
    return clean


# ---------- upload state: protects against uploading the same video twice on a retry ----------
def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _load_credentials():
    token_json_str = os.getenv("YT_TOKEN_JSON")
    if token_json_str:
        return Credentials.from_authorized_user_info(json.loads(token_json_str), SCOPES)
    if Path("token.json").exists():
        return Credentials.from_authorized_user_file("token.json", SCOPES)
    raise RuntimeError("YT_TOKEN_JSON environment variable is missing.")


def get_youtube_client():
    return build("youtube", "v3", credentials=_load_credentials())


def check_credentials():
    """Quick login test. The workflow runs this FIRST, so an expired token is found in
    seconds and not after 40 minutes of rendering."""
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request

    creds = _load_credentials()
    try:
        creds.refresh(Request())
    except RefreshError as error:
        raise SystemExit(
            f"\nYOUTUBE LOGIN FAILED: {error}\n"
            "The YouTube token is expired or revoked. Make a new one with get_youtube_token.py "
            "and update the GitHub secret YT_TOKEN_JSON. To stop this from happening every 7 days, "
            "set the OAuth app to 'In production' in Google Cloud Console.")
    print("YouTube login OK")


def upload_video(youtube, file_path, title, description, tags, thumbnail_path, is_short=False):
    privacy = os.getenv("YT_PRIVACY_STATUS", "private").lower()
    if privacy not in ("private", "unlisted", "public"):
        privacy = "private"

    print(f"Uploading {file_path} to YouTube ({privacy})...")
    body = {
        "snippet": {
            "title": make_title(title, is_short),
            "description": make_description(description),
            "tags": make_tags(tags),
            "categoryId": "27",  # Education
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk(num_retries=5)  # retries short network/server errors
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"Successfully uploaded! Video ID: {video_id}")

    if thumbnail_path and thumbnail_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg"),
            ).execute()
            print("Thumbnail set successfully!")
        except Exception as error:  # noqa: BLE001  (channel may not be verified for thumbnails)
            print(f"Warning: failed to upload thumbnail: {error}")

    return video_id


def read_script(output_dir, video_type):
    path = output_dir / "scripts" / f"{video_type}_script.json"
    return load_json(path) if path.exists() else {}


def main():
    output_dir = Path("output")
    plan_file = output_dir / "video_plan.json"
    if not plan_file.exists():
        raise FileNotFoundError("video_plan.json not found.")

    plans = load_json(plan_file)
    topic = plans[0]["destination"]
    angle = plans[0]["topic_angle"]

    state = load_state()
    youtube = get_youtube_client()

    # --- LONG VIDEO ---
    long_video = output_dir / "long_final_video.mp4"
    if "long" not in state and long_video.exists():
        # The old code ignored the SEO title/description/tags that Gemini wrote and used
        # "<whole topic> Explained", which was often over 100 characters.
        script = read_script(output_dir, "long")
        title = script.get("title") or f"{topic} Explained"
        description = (
            (script.get("description") or f"In this video, we explore {angle}.")
            + f"\n\n{DISCLAIMER}\n\n#finance #money #explained"
        )
        tags = (script.get("tags") or []) + ["finance", "money", "explained", "personal finance"]
        state["long"] = upload_video(youtube, str(long_video), title, description, tags,
                                     output_dir / "long_thumbnail.jpg", is_short=False)
        save_json(STATE_FILE, state)

    # --- SHORT VIDEO ---
    short_video = output_dir / "short_final_video.mp4"
    if "short" not in state and short_video.exists():
        script = read_script(output_dir, "short")
        title = script.get("title") or "Don't make this money mistake!"
        description = script.get("description") or f"A quick lesson on {topic}. {angle}"
        if state.get("long"):
            description += f"\n\nFull video: https://youtu.be/{state['long']}"
        description += f"\n\n{DISCLAIMER}\n\n#shorts #finance #money"
        tags = (script.get("tags") or []) + ["shorts", "finance", "money"]
        state["short"] = upload_video(youtube, str(short_video), title, description, tags,
                                      output_dir / "short_thumbnail.jpg", is_short=True)
        save_json(STATE_FILE, state)


if __name__ == "__main__":
    main()
