---
name: watchless
description: Use when turning a YouTube URL or local presentation, explainer, interview, podcast, or product-demo video into complete screenshot-led notes, faithful light-polished text, HTML, PDF, or a shareable ZIP.
---

# Watchless

> [English](SKILL.md) | [简体中文](SKILL.zh-CN.md)

Turn one video into a complete visual article. The transcript is the factual source; screenshots preserve the visual evidence. The reader should not need to watch the original video.

## Hard Requirements

- Run locally. Do not call PodSum, its website, MCP, Cloudflare, APIFY, D1, or R2.
- Keep the source immutable and reuse cached downloads and transcripts.
- Use Volcengine word-level ASR by default. Do not silently replace it with YouTube automatic captions or local Whisper.
- Keep the output chronological and complete. Light-plus is not a summary: preserve reasoning, examples, figures, caveats, disagreement, questions, answers, and repeated emphasis.
- Show process images during the run: whole-video route overview, boundary evidence where applicable, candidate frames, selected frames, and PDF page overview.
- Use no OpenCV anywhere in this Skill.
- Visual algorithms are route-specific. `slides` uses ffmpeg keyframe recall plus local SSIM refinement. `explainer`, `conversation`, and `demo` do not use SSIM, perceptual hash, histogram scoring, face scoring, or other visual ranking; Codex directly reads their candidate images.
- Resolve speaker identities for every `conversation` video before writing notes. Keep `Speaker N` when evidence remains weak or conflicting.
- Record model token usage and cost in `work/token-usage.json` whenever the runtime exposes real counts. Never invent unavailable usage or silently apply stale prices.
- Do not claim completion until HTML image references, rendered PDF pages, and ZIP contents pass verification.

## Private-Use Compliance Gate

Before acquiring a remote source, confirm that the user owns the content, has permission to process it, or has independently established another lawful basis. If authorization is unclear, stop and request an authorized local file instead of downloading.

- This repository and its outputs are private by default. Do not publish or distribute generated notes without a separate rights, privacy, confidentiality, and attribution review.
- Chrome browser cookies may be read only from the user's local browser profile. Never export, print, copy, upload, log, or commit cookie values. Cookie access does not establish a right to download or reuse content.
- Never use this Skill to bypass DRM, paywalls, members-only access, private-video access, geographic restrictions, CAPTCHAs, account enforcement, or other access controls.
- Before sending non-public or sensitive audio to Volcengine, confirm that the user is authorized to make that third-party transfer. Use explicitly requested local Whisper or stop when authorization is unavailable.
- Resolve speaker names only from explicit public metadata, self-introduction, lower thirds, or similarly reliable evidence. Do not perform face or voice biometric identification. Keep `Speaker N` when uncertain and require human review before external use.
- Use the minimum screenshots and quotations needed for any approved external use. Do not publish a complete transcript or visual reconstruction that substitutes for the source without a separate legal review.

Read `LEGAL.en.md` before running this Skill on third-party, confidential, commercial, or sensitive material. These controls reduce risk but do not constitute legal advice.

## Route Model

Choose one content route after directly inspecting `verify/mode-overview.jpg` and the transcript. Then add visual strategies. Do not route from the title or channel alone.

| Route | Observable pattern | Segmentation | Frame extraction |
| --- | --- | --- | --- |
| `slides` | Stable PPT, slide deck, document pages, or a fixed presentation region | Every meaningful slide/build state | Hybrid H.264 keyframe recall, local SSIM refinement, accurate scan fallback |
| `explainer` | Scripted visual argument: presenter, charts, animation, maps, documents, B-roll | Complete argument/example/visual function | Dense time-distributed candidates inside each semantic scene; Codex selects |
| `conversation` | Interview, panel, podcast, or question-and-answer exchange | Complete Q&A or topic unit, not every speaker turn | Active speaker/two-shot candidates; evidence or B-roll can override faces |
| `demo` | UI walkthrough, product demonstration, tutorial, or physical procedure | Executable step and observable result | Candidates biased toward before/after and completed states; Codex selects |

Visual strategies are composable:

- `slide-state`: stable, complete slide/build state.
- `speaker`: active speaker or useful group shot.
- `evidence`: chart, quote, interface, object, or source that carries the claim.
- `broll`: relevant external footage in an edited interview or documentary.
- `dense-visual`: increase candidate density for XiaoLin-style edited explainers.
- `document-evidence`: prefer papers, article excerpts, tables, and diagrams.
- `screen-state`: prefer a legible UI result rather than cursor motion or transitions.

For `conversation`, also choose one extraction profile without creating a new main route:

| Profile | Use when | Candidate behavior |
| --- | --- | --- |
| `studio` | Stable studio/remote podcast with little visual evidence | Three representative speaker/group candidates per semantic scene |
| `edited` | Interview with B-roll, locations, documents, or archival footage | Nine distributed candidates plus local evidence-trigger candidates |
| `news` | Broadcast interview with lower thirds, tickers, charts, and product graphics | Eight distributed candidates plus local evidence-trigger candidates |
| `chaptered` | Long interview whose official chapters are useful topic hints | Five candidates; chapters seed review but never force a boundary through an answer |
| `general` | Evidence is insufficient to choose a more specific profile | Backward-compatible five-candidate behavior |

Typical routing examples:

- XiaoLin-style scripted finance/technology video: `explainer + dense-visual + evidence`.
- Best Partners paper/article explanation: `explainer + document-evidence`.
- a16z or YC Lightcone studio podcast: `conversation + speaker`.
- Silicon Valley 101 edited field interview: `conversation + evidence + broll`.
- YC Design Review screen walkthrough: `demo + screen-state + evidence`.
- Low-information entertainment chat: `conversation + speaker`, with fewer, larger topic units.

## Workflow

Set `SKILL_DIR` to this Skill directory. Run commands from the workspace where `outputs/video-notes/` should be created.

### 1. Acquire, transcribe, and inspect the whole video

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" "$SOURCE" --stage prepare
```

Read `PROJECT_DIR` from output. Display `verify/mode-overview.jpg`, inspect the transcript and source metadata, and decide the route from observable structure.

### 2. Confirm route and visual strategies

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage route --project-dir "$PROJECT_DIR" \
  --mode explainer \
  --visual-strategy dense-visual \
  --visual-strategy evidence \
  --mode-reason "scripted host alternates with explanatory charts and B-roll"
```

Later stages may use `--mode auto`; they read the confirmed `work/route-decision.json`. An explicit `--mode` remains a manual override. Compatibility aliases: `presentation -> slides`, `editorial -> explainer`.

For a Bloomberg-style news interview:

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage route --project-dir "$PROJECT_DIR" \
  --mode conversation --conversation-profile news \
  --visual-strategy speaker --visual-strategy evidence \
  --mode-reason "broadcast interview with lower thirds and sparse data graphics"
```

### 3A. Slides route

Slides do not use semantic timeline boundaries. If the slide occupies only part of the frame, directly inspect the overview and pass a relative crop rectangle.

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage scenes --project-dir "$PROJECT_DIR" --mode auto \
  --slide-rect "0.04,0.08,0.72,0.92"
```

The default backend is `hybrid-keyframe`: scan H.264 keyframes at low resolution, compare the fixed slide region with SSIM, locally refine clustered changes on a 2-second grid, and fall back to `accurate` full scanning when keyframe recall is unavailable. Use `--slide-backend accurate`, `--slide-interval`, or `--slide-threshold` only when the default misses or over-splits states.

Display `verify/selected-keyframes.jpg`. Confirm that frames are complete slides, not black frames, fades, or partial transitions.

### 3B. Explainer, conversation, and demo routes

Prepare an audio-first semantic review:

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage timeline --project-dir "$PROJECT_DIR" --mode auto
```

Read `work/video-use/takes_packed.md` and `work/timeline/boundary-review.md`. Propose boundaries only at complete phrases and semantic transitions. For each real decision point `T`, inspect approximately `T-4s` to `T+4s` with `video-use/helpers/timeline_view.py`; do not scan the full video at fixed intervals.

When official chapters exist, the timeline stage writes `work/timeline/chapter-hints.json`. Treat chapters only as coarse topic proposals: merge or split them to preserve complete questions, answers, examples, and qualifications.

Write `work/timeline/scene-boundaries.json`:

```json
{"mode":"explainer","scenes":[{"end_sec":42.35,"reason":"hook and first claim complete"},{"end_sec":113.8,"reason":"chart explanation completes"}]}
```

The final boundary must cover the final transcript phrase. Then build scenes:

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage scenes --project-dir "$PROJECT_DIR" --mode auto \
  --boundaries "$PROJECT_DIR/work/timeline/scene-boundaries.json"
```

Display candidate contact sheets and `verify/selected-keyframes.jpg`. Select frames by direct inspection. For explainers, prefer visual evidence over a face; for conversations, prefer the active speaker unless evidence/B-roll adds information; for demos, prefer the completed UI or physical result.

For `edited` and `news` conversations, the scene builder also looks for spoken references such as charts, data, reports, papers, products, chips, and screens. It adds nearby candidates labeled `evidence` to the contact sheet. These are recall hints, not automatic visual scores; Codex must still inspect and choose the frame.

### 4. Confirm selected frames

If default candidates are suitable:

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage select --project-dir "$PROJECT_DIR"
```

Otherwise write selections such as `{"1":2,"7":5}` and pass `--selections`. Do not proceed until `keyframe_review.status=complete`.

### 5. Conversation speaker identity pass

For `conversation`, complete `work/speaker-map.json` before batches. Use evidence in this order:

1. YouTube metadata and official description: title, credits, chapters, linked show notes.
2. Self-introductions and reliable subtitles.
3. Lower thirds, on-screen names, camera handoffs, and visible turn agreement.
4. Official episode pages.
5. Earlier episodes from the same channel for recurring-host corroboration.

Record `display_name`, role, confidence, and evidence. `high` requires explicit naming plus turn agreement; `medium` is a documented inference; `low` remains `Speaker N`. Use timestamped `turn_overrides` when ASR merges people or changes labels for one person. Set `status=complete` only after checking handoffs throughout the video.

### 6. Write complete scene notes

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage batches --project-dir "$PROJECT_DIR"
```

Inspect every referenced image and transcript. Write each requested `work/codex-notes/scene_NNN.md`. Preserve the original order and voice; do not turn dialogue into third-person editorial narration. Visual descriptions must remain factual and useful.

If the runtime reports actual model usage, append it after each model-heavy phase. Pass current explicit rates only when cost should be calculated:

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage usage --project-dir "$PROJECT_DIR" \
  --usage-stage notes --model-name "$MODEL" \
  --input-tokens "$INPUT_TOKENS" --output-tokens "$OUTPUT_TOKENS" \
  --cached-input-tokens "$CACHED_INPUT_TOKENS" \
  --input-rate-per-million "$INPUT_RATE" \
  --cached-input-rate-per-million "$CACHED_RATE" \
  --output-rate-per-million "$OUTPUT_RATE"
```

### 7. Build and verify outputs

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage finalize --project-dir "$PROJECT_DIR"
```

Finalize automatically writes `verify/quality-audit.json` and `verify/quality-audit.md`. Display `verify/pdf-pages-contact-sheet.jpg`, read the audit, and resolve warnings about transcript coverage, note/frame counts, speaker identity, duplicate exact frames, or missing usage records. Report Markdown, HTML, PDF, ZIP, scene count, image count, page count, recorded tokens, and known cost. Unknown usage remains unknown.

## Fallbacks

After the compliance gate is satisfied, try anonymous `yt-dlp`, then local Chrome browser cookies without exporting them. Do not use the cookie fallback to defeat access controls. Volcengine credentials may be discovered from the environment, `scripts/config.py`, or `WATCHLESS_VOLCENGINE_CONFIG`; never print or copy credential values. Use source/manual subtitles only with `--use-source-subtitles`. Use local Whisper only when explicitly requested with `--provider whisper`. If acquisition still fails, report the classified error and request an authorized local video.

Stages are idempotent and resumable. `--target-seconds` is an explicit legacy fallback for non-slide modes, never the normal segmentation method.
