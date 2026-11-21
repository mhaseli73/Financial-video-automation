import os
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_youtube_client():
    token_json_str = os.getenv("YT_TOKEN_JSON")
    if not token_json_str:
        if Path("token.json").exists():
            return build("youtube", "v3", credentials=Credentials.from_authorized_user_file("token.json", SCOPES))
        raise RuntimeError("YT_TOKEN_JSON environment variable is missing.")

    creds_info = json.loads(token_json_str)
    creds = Credentials.from_authorized_user_info(creds_info, SCOPES)
    return build("youtube", "v3", credentials=creds)

def upload_video(youtube, file_path, title, description, tags, is_short=False):
    print(f"Uploading {file_path} to YouTube...")
    
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": "27" # 27 = Education
        },
        "status": {
            "privacyStatus": "private", # CHANGED TO PRIVATE FOR REVIEW
            "selfDeclaredMadeForKids": False
        }
    }

    if is_short and "#Shorts" not in body["snippet"]["title"]:
        body["snippet"]["title"] += " #Shorts"

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response['id']
    print(f"✅ Successfully uploaded! Video ID: {video_id}")

    thumbnail_path = Path("output/thumbnail.jpg")
    if thumbnail_path.exists():
        print("Uploading custom thumbnail...")
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))).execute()
            print("✅ Thumbnail set successfully!")
        except Exception as e:
            print(f"⚠️ Failed to upload thumbnail: {e}")
    
    return video_id

def main():
    output_dir = Path("output")
    plan_file = output_dir / "video_plan.json"
    if not plan_file.exists():
        raise FileNotFoundError("video_plan.json not found.")
        
    with open(plan_file, encoding="utf-8") as f:
        plans = json.load(f)
        
    topic = plans[0]["destination"]
    angle = plans[0]["topic_angle"]
    
    youtube = get_youtube_client()

    # --- LONG VIDEO ---
    long_video = output_dir / "long_final_video.mp4"
    if long_video.exists():
        long_title = f"{topic} Explained"
        long_desc = f"In this video, we explore {angle}.\n\nDisclaimer: This video is for educational purposes only and does not constitute financial advice.\n\n#explained #finance #psychology"
        long_tags = ["finance", "explained", "psychology", "money", "investing"]
        
        upload_video(youtube, str(long_video), long_title, long_desc, long_tags, is_short=False)

    # --- SHORT VIDEO ---
    short_video = output_dir / "short_final_video.mp4"
    if short_video.exists():
        short_title = f"Don't make this money mistake! 💸"
        short_desc = f"A quick lesson on {topic}. {angle}\n\n#shorts #finance #money"
        short_tags = ["shorts", "finance", "money", "tips"]
        
        upload_video(youtube, str(short_video), short_title, short_desc, short_tags, is_short=True)

if __name__ == "__main__":
    main()
