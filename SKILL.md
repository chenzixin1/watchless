---
name: video-notes-maker
description: Use when turning a YouTube URL or local explanatory, interview, documentary, course, or presentation video into detailed screenshot-led notes, light-polished text, HTML, PDF, or a shareable ZIP.
---

# Video Notes Maker

Turn one video into a complete visual article. The transcript is the factual source; visuals explain and verify it.

## Hard Requirements

- Run locally. Do not call PodSum, its website, MCP, Cloudflare, APIFY, D1, or R2.
- Keep the source immutable and reuse cached downloads/transcripts.
- Do not use OpenCV, SSIM, or visual scoring. Use `ffmpeg` only to extract images; Codex decides by directly reading them.
- Continuously tell the user the current stage, completed count, and next step.
- Show process images in the conversation: mode overview, scene candidates, selected-keyframe overview, and PDF page overview.
- Preserve two texts: a faithful light-plus draft and a detailed one-image/one-block explainer.
- Do not claim completion until HTML image references, rendered PDF pages, and ZIP contents pass verification.

## Workflow

Set `SKILL_DIR` to the directory containing this `SKILL.md`. Run commands from the directory where the user wants `outputs/video-notes/` to be created, and invoke the Skill's own virtual environment.

1. Prepare source, subtitles, and mode evidence:

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" "$SOURCE" --stage prepare
```

Read `PROJECT_DIR` from output. Display `verify/mode-overview.jpg` and inspect it.

2. Choose mode without asking the user during a healthy run:

- `presentation`: stable slide region, low continuous motion, page replacements. Picture-in-picture is allowed.
- `editorial`: talking heads, B-roll, camera cuts, animated charts, or mixed layouts.
- Ambiguous inputs use `editorial`.

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" --stage scenes \
  --project-dir "$PROJECT_DIR" --mode editorial \
  --mode-reason "talking head and B-roll alternate with charts"
```

Display several images from `verify/candidate-contact-sheets/` and `verify/selected-keyframes.jpg`. Directly inspect them. If the middle candidates are all suitable, confirm them:

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" --stage select --project-dir "$PROJECT_DIR"
```

If any scene needs a different candidate, write a JSON object such as `{"1": 2, "7": 5}` and pass it with `--selections`. Unlisted scenes keep the middle candidate. Do not proceed until the manifest records `keyframe_review.status=complete`.

3. Prepare disjoint Codex batches:

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" --stage batches --project-dir "$PROJECT_DIR"
```

For every batch, inspect each image and transcript. Write the requested `work/codex-notes/scene_NNN.md` files exactly as specified. Preserve figures, examples, caveats, and disagreements. Do not add web research unless the user asks.

4. Build and verify all outputs:

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" --stage finalize --project-dir "$PROJECT_DIR"
```

Display `verify/pdf-pages-contact-sheet.jpg`. Report links to Markdown, HTML, PDF, and ZIP plus scene/image/page counts.

## Fallbacks

For YouTube, try anonymous `yt-dlp`, then Chrome browser cookies without exporting them. Prefer manual subtitles, then automatic subtitles, then Volcengine ASR, then local Whisper. If video download still fails, explain the classified failure and request a local file.

Use `--mode presentation|editorial`, `--provider`, or `--output-root` only when needed. For presentation mode, candidate windows are denser (at most 30 seconds) so Codex can retain slide changes. Stage commands are idempotent and can resume an interrupted run.
