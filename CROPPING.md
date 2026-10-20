# Public-stream screenshot crop candidates / private originals

## Public GitHub Actions
The existing 05:00 and 17:00 JST scheduled workflow tries to capture one frame near
10:00 of an ended, public, verified SELF broadcast (at most one video per run).
It uses yt-dlp and ffmpeg; YouTube may block or change stream delivery. Failures
are harmless to Pages and are retried only after 7 days.

OpenCV detects a prominent face and crops a 4:5 upper-body suggestion. Anime-like
faces may not be detected, so left/center/right choices are generated for manual
review instead. **This does not identify Saiki or other participants.**

Only PUBLIC crop suggestions go into `images/auto_crops/` (GitHub Pages/public).
`data/auto_crops.json` is a public index of suggestions. The site shows these
options in an existing video's **Edit → Screenshots** panel. Choosing a candidate
copies it to the user's local IndexedDB; the old screenshot stays available.
No automatic changes to existing representative images, savings, or notes.

Do not use this pipeline for members-only content or personal screenshots.
Never commit local originals or Drive backups to this repository.

## Already-collected private screenshots: process locally
```sh
python -m pip install Pillow numpy opencv-python-headless
python scripts/crop_screenshots.py --input /path/to/screenshots --output /path/to/private-crop-preview
```
Images and `manifest.json` are created locally, without uploads. Review them,
then use the site's existing **Edit → Add Screenshot** button to import.
Default crop is face-to-upper-body (4:5); uncertain images produce three options.
Keep your private screenshots and output folder **outside the public repository**.

## Important limitations
This workflow is best effort: YouTube playback capture can fail on cloud Actions
runners; a green deployment does NOT mean any images were captured.
The workflow never accesses browser localStorage, browser IndexedDB, or Drive
appDataFolder, and cannot learn from those private images on GitHub Actions.
Only the image-crop proportions were calibrated using existing private examples;
the private image bytes are never committed here.
