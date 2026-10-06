# Stock Video Tool

A desktop app (Python / PySide6) for preparing stock video clips for sale on
Envato. Drag in video files and the tool helps you describe, title, tag, and
convert each clip, then exports an Envato-ready CSV.

## What it does

- **Drag-and-drop** video files; stats and four 720p thumbnails are generated
  automatically (via `ffmpeg`/`ffprobe`).
- **AI assist** (through [OpenRouter](https://openrouter.ai)): generate a
  description from the thumbnails, then marketable titles, then ~45 keywords and
  an Envato category. Every step is editable, and the per-request cost is shown.
- **Editable prompts**: the description, titles, and tags prompts are all
  configurable in Settings.
- **Copy metadata** (title, description, tags, category) from one clip to others.
- **Processing queue**: convert H265 clips to H264 (near-lossless, muted) and
  strip audio from clips that have it — written atomically so interrupted runs
  leave no partial files.
- **Local persistence**: generated fields are saved by filename and reloaded when
  you re-add a file (thumbnails are always regenerated).
- **CSV export** with the full Envato column set; a 50-keyword hard limit is
  enforced before export.

## Requirements

- Python 3.13
- `ffmpeg` and `ffprobe` on your `PATH`
- An OpenRouter API key (added in Settings) for the AI steps

## Setup

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e .
```

## Run

```bash
PYTHONPATH=src .venv/bin/python -m stock_video_tool.app
```

## Tests

```bash
.venv/bin/python -m pytest -q
```

See [TESTS.md](TESTS.md) for a description of every test in the suite.
