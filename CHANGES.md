# What was fixed

## Bugs that broke or damaged the videos
| File | Problem | Fix |
|---|---|---|
| video_renderer.py | Every image was shown for a fixed 5 s. 24 images = 120 s, so the last ~2 minutes of the long video (and the end of the Short) were **black**. | Each scene gets a share of the real audio length (by word count). Images now match the voice. |
| video_renderer.py | Zoom drifted to the top-left corner (crop used the old size). | Zoom is done inside a fixed-size frame, so it stays centered. |
| video_renderer.py | Intro title used ImageMagick + font `Arial-Bold`. On the runner this failed and `except: pass` hid it, so there was never a title. | Title is drawn with Pillow. No ImageMagick needed. |
| video_renderer.py | Output pixel format not set (can be 4:4:4, which some players can not play). | `yuv420p` + `faststart`, `preset=veryfast`. |
| thumbnail_generator.py | Font `arialbd.ttf` does not exist on Linux -> tiny default font. Title was also one long line, cut at 30 characters, and went outside the picture. | Real font, wrapped text that fits, shorter headline (text before `:`), dark band behind text, JPEG under 2 MB. |
| youtube_uploader.py | Title was `"<topic> Explained"`, often > 100 characters. For Shorts, ` #Shorts` was added AFTER cutting to 100 characters -> 108 characters -> API error. | Title is cut at a word and the suffix fits inside 100 characters. |
| youtube_uploader.py | The SEO title, description and tags written by Gemini were never used. | They are used now (with a safe fallback). The Short description links to the long video. |
| youtube_uploader.py | If the long video uploaded and the Short failed, the retry uploaded the long video **again**. | `output/uploaded.json` remembers uploaded videos. |
| scene_planner.py / voiceover_generator.py | Gemini was asked to cut the narration into scenes; it can shorten or rewrite it, and the voiceover was built from those scenes (missing sentences). | The text is split in Python by sentence. Gemini only writes the picture ideas. Voiceover uses the approved script. |
| scene_planner.py | An API error in the main model raised an exception, so the fallback model was never tried. `result` could also be `None`. | One shared `gemini_client.py` with correct fallback. |

## Logic / finance-conversion problems
| File | Problem | Fix |
|---|---|---|
| gemini_brain.py | "Rotate categories" rule, but the model never saw the last category. | Themes are saved in history and the last ones are sent to the model. |
| gemini_brain.py | Duplicate check only caught identical titles. | Also catches re-worded titles. Old travel entries are no longer sent to the model. |
| gemini_brain.py | Daily-quota check used "free tier" (also appears in per-minute errors) and missed `PerDay`. | Fixed. |
| gemini_brain.py / script_generator.py | `max_output_tokens` too small for models that count thinking tokens -> cut JSON. Bad JSON was not handled. | Bigger limits, JSON repair/retry, validation of required fields and word count. |
| main.py | Topic was saved to history at the START. Failed runs used up topics, and each retry added another entry. | Saved at the END (`record_history`), only after a successful upload. |
| main.py | Audience still "International travelers". | Finance audience. |
| researcher.py | Used the whole video title as a Wikipedia page name -> always 404 for finance titles. Bot name was "Travel...". | Wikipedia search with `research_query` from Gemini. |
| script_generator.py | 480-520 words = only about 3 minutes. Narration could contain markdown/emojis that the voice reads out. | 580-620 words, plain-speech rules, text cleaning. |
| visual_fetcher.py | No check that Pollinations returned a real image; failed image = missing scene; waited 45 s even after the last image. | Validation, retries, resume, placeholder stickman. Delay via `IMAGE_DELAY_SECONDS`. |
| voiceover_generator.py | Random voice per video (Short and long video sounded different). No retry for edge-tts. | One voice per run (or `TTS_VOICE`), retries. |
| pipeline.py | A retry started the whole pipeline again: new topic, all images again (~25 min). | Resume from the failed step (`output/run_state.json`). |
| daily.yml | Still named "Travel". `nick-invision/retry@v2` is old. ImageMagick policy path was wrong (`ImageMagick-7`; Ubuntu uses 6). Output was not saved when the run failed. | `nick-fields/retry@v3`, no ImageMagick, `if: always()` for the artifact, finance names. |

## Things to know (not code bugs)
- `privacyStatus` was always `private`. It is still the default. Set `YT_PRIVACY_STATUS=public` (or `unlisted`) in the workflow to change it. Note: API projects that are not audited by YouTube can only upload private videos.
- If your Google OAuth app is in "Testing" mode, the refresh token stops working after 7 days. Publish the app to avoid this.
- Custom thumbnails need a phone-verified YouTube channel.
- `output/decision_history.json` keeps the old travel entries. The code ignores them for finance topics.
- The Gemini model names (`gemini-3.8-flash`, `gemini-3.5-flash-lite`) exist in Google's docs. They can now be changed with `GEMINI_PRIMARY_MODEL` / `GEMINI_FALLBACK_MODEL`.

## New: daily video styles (`styles.py`)
Each day `main.py` picks one of 6 styles (problem/solution, myth vs fact, story, "what if", countdown, Q&A).
The last 3 styles are not used again, and the style is saved in `decision_history.json`.
A style changes:
- the **script structure**, opening type and length (500-680 words)
- the **picture accent color** (red, blue, green, orange, purple, teal)
- the **title color and position**, and the **zoom amount**
- the **background music**: put extra tracks in `output/` named `bgm_2.mp3`, `bgm_3.mp3`... (and keep `bgm.mp3`). The style chooses one. More tracks = more variety.

To add a style, add one entry to `STYLES` in `styles.py`.

## New: automatic script checker (`script_checker.py`)
Every script Gemini writes is checked before images, voice or upload are made.
1. **Rules (Python):** real brands/people, risky advice words, statistics that look invented (allowed only as an
   "example" or when the number is in the Wikipedia text), repeated sentences, very long sentences, wrong ending.
2. **AI editor (second Gemini call, low temperature):** logic, contradictions, wrong facts, wrong arithmetic,
   unsafe advice, off-topic parts. The Short is checked against the long script (it may only use its facts).
3. If there are errors, Gemini rewrites the script to fix them (max 2 rounds). If it still fails, the step stops,
   the workflow retries with a NEW script, and nothing is uploaded.
The report is saved in `output/scripts/long_check.json` and `short_check.json` (also in the workflow artifact).
Set `SCRIPT_CHECK_STRICT=0` to only warn and continue. An AI checker can still miss mistakes, so read some scripts yourself.
