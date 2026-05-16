# yt

Simple YouTube shorts automation that combines multiple clips, applies video polish, and adds optional transition/background audio.

## Requirements

- `ffmpeg` and `ffprobe` installed and available in your `PATH`
- Python 3.10+

## Usage

```bash
python yt_automation.py \
  /absolute/path/clip1.mp4 /absolute/path/clip2.mp4 /absolute/path/clip3.mp4 \
  --output /absolute/path/final_video.mp4
```

### Usage with optional music and transition SFX

```bash
python yt_automation.py \
  /absolute/path/clip1.mp4 /absolute/path/clip2.mp4 /absolute/path/clip3.mp4 \
  --music /absolute/path/background.mp3 \
  --sound-effect /absolute/path/whoosh.wav \
  --output /absolute/path/final_video.mp4
```

### What it does

- Concatenates your short clips in the order you pass them
- Applies vertical-video formatting and mild visual enhancement
- Normalizes primary clip audio
- Optionally mixes looping background music
- Optionally adds transition sound effects at each clip boundary
