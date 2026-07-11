# Video Notes Maker

`video-notes-maker` is a standalone Codex skill that converts a YouTube URL or local video into detailed screenshot-led notes. It combines two processing styles behind one scene-manifest contract:

- Editorial video: transcript-led scenes, candidate filmstrips, and Codex-selected keyframes.
- Presentation video: denser candidate filmstrips, Codex-reviewed slide frames, and complete speech blocks.

Both routes produce a faithful light-plus draft, a detailed visual explainer, HTML, PDF, and a shareable ZIP.

## What stays local

The runtime does not depend on PodSum, MCP, Cloudflare, APIFY, D1, or R2. YouTube acquisition uses local `yt-dlp`, Node challenge support, optional Chrome browser cookies, and `ffmpeg`. Cookie values are never exported by this project. The visual workflow does not use OpenCV, SSIM, face detection, or image-scoring heuristics: `ffmpeg` extracts candidate images and Codex reads them directly.

## Install

```bash
git clone https://github.com/chenzixin1/video-notes-maker.git ~/Developer/video-notes-maker
cd ~/Developer/video-notes-maker
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt

brew install ffmpeg yt-dlp pandoc poppler
mkdir -p ~/.codex/skills
ln -sfn ~/Developer/video-notes-maker ~/.codex/skills/video-notes-maker
```

Google Chrome is required for HTML-to-PDF rendering. Local Whisper is optional:

```bash
.venv/bin/pip install -r scripts/requirements-whisper.txt
```

Volcengine ASR can be configured in `scripts/config.py` using `scripts/config.example.py`; real keys are ignored by Git.

## Codex workflow

The Skill uses one stage-oriented entry point. From the directory where outputs should be created:

```bash
~/.codex/skills/video-notes-maker/.venv/bin/python \
  ~/.codex/skills/video-notes-maker/scripts/00_build_video_notes.py \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  --stage prepare
```

The command prints `PROJECT_DIR`. Codex then inspects the generated mode contact sheet and continues:

```bash
~/.codex/skills/video-notes-maker/.venv/bin/python \
  ~/.codex/skills/video-notes-maker/scripts/00_build_video_notes.py \
  --stage scenes --project-dir "$PROJECT_DIR" --mode editorial

~/.codex/skills/video-notes-maker/.venv/bin/python \
  ~/.codex/skills/video-notes-maker/scripts/00_build_video_notes.py \
  --stage select --project-dir "$PROJECT_DIR"

~/.codex/skills/video-notes-maker/.venv/bin/python \
  ~/.codex/skills/video-notes-maker/scripts/00_build_video_notes.py \
  --stage batches --project-dir "$PROJECT_DIR"

# Codex writes every requested work/codex-notes/scene_NNN.md.

~/.codex/skills/video-notes-maker/.venv/bin/python \
  ~/.codex/skills/video-notes-maker/scripts/00_build_video_notes.py \
  --stage finalize --project-dir "$PROJECT_DIR"
```

From the user's perspective this is one Skill run. Stages exist so Codex can inspect visual evidence, show progress images, and resume safely after interruption.

## Mode selection

The preparation stage writes `verify/mode-evidence.json` and `verify/mode-overview.jpg`, then marks mode selection as requiring Codex review rather than producing a computer-vision guess.

Codex uses `presentation` for stable PPT or slide recordings, including a small speaker picture-in-picture. It uses `editorial` for talking heads, documentaries, interviews, B-roll, animated graphics, or mixed layouts. Ambiguous videos default to editorial.

## Output layout

```text
outputs/video-notes/<title>-<video-id>/
├── work/
│   ├── source/
│   ├── transcript/
│   ├── acquisition.json
│   ├── mode-decision.json
│   ├── scene-manifest.json
│   ├── candidates/
│   ├── codex-batches/
│   └── codex-notes/
├── verify/
│   ├── mode-overview.jpg
│   ├── candidate-contact-sheets/
│   ├── selected-keyframes.jpg
│   └── pdf-pages-contact-sheet.jpg
├── share/
│   ├── *-light-polished.md
│   ├── *-visual-explainer.md
│   ├── *-visual-explainer.html
│   ├── *-visual-explainer.pdf
│   ├── keyframes/
│   └── source-materials/
└── *-video-notes.zip
```

The ZIP contains only `share/`. Downloaded video, candidates, browser state, logs, and credentials are excluded.

## Useful options

```text
--output-root PATH
--mode auto|editorial|presentation
--lang zh
--max-height 1080
--cookies-from-browser chrome
--no-browser-cookies
--provider auto|volcengine|whisper
--target-seconds 90
--batch-size 6
--no-zip
```

## Verification

```bash
python3 -m pytest -q
python3 -m py_compile scripts/*.py
```

Finalization verifies note coverage, Markdown/HTML image references, PDF rendering, and ZIP membership. The PDF is rendered back to PNG pages and summarized in a contact sheet for visual inspection.

## Provenance

This repository preserves the history of `chenzixin1/session-notes-maker` and evolves its presentation-video pipeline. The conversation-progress and timeline-inspection approach is informed by the MIT-licensed `browser-use/video-use` project; see `THIRD_PARTY_NOTICES.md`.
