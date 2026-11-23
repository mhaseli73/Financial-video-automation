# Financial-video-automation

AI-automated "Money Explained" finance video generator (stickman style).
Every day it picks a topic, writes a script, makes images and a voiceover, renders one
long video (about 4 min) and one Short, makes thumbnails and uploads both to YouTube.

## Pipeline (`python pipeline.py`)

1. `main.py` - Gemini picks a topic (themes rotate, duplicates are blocked)
2. `researcher.py` - short Wikipedia background
3. `script_generator.py` - long script, then a Short teaser of it
4. `scene_planner.py` - splits the script into scenes, Gemini adds a picture idea per scene
5. `visual_fetcher.py` - stickman images (Pollinations)
6. `voiceover_generator.py` - edge-tts voice
7. `video_renderer.py` - images + voice + music -> mp4
8. `thumbnail_generator.py` - JPEG thumbnails
9. `youtube_uploader.py` - upload
10. topic is saved to `output/decision_history.json` (only after a successful upload)

Each day a different video style is used (see `styles.py`: structure, colors, title, zoom, music).

If a run fails, running it again continues from the failed step (state in `output/run_state.json`,
valid for 12 hours). Delete that file to force a fresh start.

## Secrets / settings

- `GEMINI_API_KEY`, `YT_TOKEN_JSON` (GitHub secrets)
- Optional env vars: `YT_PRIVACY_STATUS` (private/unlisted/public, default private),
  `GEMINI_PRIMARY_MODEL`, `GEMINI_FALLBACK_MODEL`, `TTS_VOICE`, `IMAGE_DELAY_SECONDS`
