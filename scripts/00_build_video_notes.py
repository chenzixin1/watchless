#!/usr/bin/env python3
"""Stage-oriented entry point for the Codex video-notes workflow."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from video_notes_common import (
    emit_progress,
    extract_video_id,
    parse_transcript_file,
    read_json,
    safe_slug,
    write_json,
    write_timestamped_transcript,
)

import importlib.util


def load_script(name: str):
    path = SCRIPT_DIR / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACQUIRE = load_script("01_acquire_source.py")
OVERVIEW = load_script("02_prepare_mode_overview.py")
SCENES = load_script("03_build_scene_manifest.py")
TIMELINE = load_script("03_prepare_timeline_evidence.py")
KEYFRAMES = load_script("03_apply_codex_keyframes.py")
BATCHES = load_script("04_prepare_codex_scene_batches.py")
OUTPUTS = load_script("05_build_outputs.py")
AUDIT = load_script("06_audit_project.py")

MODE_ALIASES = {"presentation": "slides", "editorial": "explainer"}
SUPPORTED_MODES = {"slides", "explainer", "conversation", "demo"}
CONVERSATION_PROFILES = {"general", "studio", "edited", "news", "chaptered"}
DEFAULT_STRATEGIES = {
    "slides": ["slide-state"],
    "explainer": ["evidence", "dense-visual"],
    "conversation": ["speaker"],
    "demo": ["screen-state", "evidence"],
}


def resolve_initial_project(source: str, output_root: Path) -> Path:
    local = Path(source).expanduser()
    if local.is_file():
        return output_root / safe_slug(local.stem)
    video_id = extract_video_id(source)
    if not video_id:
        raise ValueError("Unsupported input")
    existing = sorted(output_root.glob(f"*-{video_id}"))
    return existing[0] if existing else output_root / f"youtube-{video_id}"


def relocate_acquisition_paths(acquisition: dict, work: Path) -> dict:
    """Repair absolute artifact paths after the project directory is renamed."""
    source_dir = work / "source"
    for key in ("local_video", "subtitle", "info_json"):
        value = acquisition.get(key)
        if not value or Path(value).is_file():
            continue
        relocated = source_dir / Path(value).name
        if relocated.is_file():
            acquisition[key] = str(relocated.resolve())
    return acquisition


def resolve_video_use_skill() -> Path:
    candidates = [
        Path(os.environ.get("VIDEO_USE_SKILL_DIR", "")).expanduser(),
        Path("/Volumes/1TB/1Tprojects/video use"),
        Path.home() / ".codex" / "skills" / "video-use",
    ]
    for candidate in candidates:
        if candidate and (candidate / "helpers" / "pack_transcripts.py").is_file():
            return candidate.resolve()
    raise RuntimeError(
        "video-use helpers were not found. Set VIDEO_USE_SKILL_DIR to the directory containing its SKILL.md."
    )


def cues_to_word_transcript(cues: list[dict]) -> dict:
    """Adapt timestamped subtitles to the video-use transcript schema."""
    words = []
    speaker_re = re.compile(r"^(?:说话人|S)([^:：\s]+)\s*[:：]\s*(.*)$")
    for cue in cues:
        text = str(cue.get("text") or "").strip()
        speaker_id = None
        match = speaker_re.match(text)
        if match:
            speaker_id = f"speaker_{match.group(1)}"
            text = match.group(2).strip()
        if not text:
            continue
        item = {
            "text": text,
            "type": "word",
            "start": float(cue["start_sec"]),
            "end": float(cue["end_sec"]),
        }
        if speaker_id:
            item["speaker_id"] = speaker_id
        words.append(item)
    return {
        "text": "".join(item["text"] for item in words),
        "words": words,
        "metadata": {"provider": "source_subtitles", "word_timestamps": False},
    }


def build_packed_transcript(work: Path, transcript_json: Path) -> Path:
    video_use = resolve_video_use_skill()
    edit_dir = work / "video-use"
    packed = edit_dir / "takes_packed.md"
    subprocess.run(
        [
            sys.executable,
            str(video_use / "helpers" / "pack_transcripts.py"),
            "--edit-dir",
            str(edit_dir),
        ],
        check=True,
    )
    if not packed.is_file():
        raise RuntimeError("video-use did not create takes_packed.md")
    return packed


def prepare(source: str, output_root: Path, args: argparse.Namespace) -> Path:
    project = resolve_initial_project(source, output_root)
    work = project / "work"
    verify = project / "verify"
    acquisition = ACQUIRE.acquire(
        source,
        work,
        max_height=args.max_height,
        language=args.lang,
        cookies_from_browser=None if args.no_browser_cookies else args.cookies_from_browser,
    )
    video_id = acquisition.get("video_id")
    final_name = safe_slug(acquisition.get("title") or Path(acquisition["local_video"]).stem)
    if video_id:
        final_name += f"-{video_id}"
    final_project = output_root / final_name
    if final_project != project and not final_project.exists():
        project.rename(final_project)
        project = final_project
        work = project / "work"
        verify = project / "verify"
        acquisition = read_json(work / "acquisition.json")
        acquisition = relocate_acquisition_paths(acquisition, work)
        write_json(work / "acquisition.json", acquisition)

    transcript_dir = work / "transcript"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    transcript = transcript_dir / f"{safe_slug(acquisition['title'])}_transcript.txt"
    video_use_transcripts = work / "video-use" / "transcripts"
    video_use_transcripts.mkdir(parents=True, exist_ok=True)
    transcript_json = video_use_transcripts / f"{safe_slug(acquisition['title'])}.json"
    subtitle = acquisition.get("subtitle")
    if args.use_source_subtitles and subtitle and Path(subtitle).is_file():
        cues = parse_transcript_file(Path(subtitle))
        if cues:
            write_timestamped_transcript(cues, transcript)
            transcript_json.write_text(
                json.dumps(cues_to_word_transcript(cues), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    if not transcript.is_file() or not transcript_json.is_file():
        command = [
            sys.executable,
            str(SCRIPT_DIR / "01_transcribe_video.py"),
            acquisition["local_video"],
            "--output",
            str(transcript),
            "--provider",
            args.provider,
            "--json-output",
            str(transcript_json),
        ]
        subprocess.run(command, check=True)
    if not transcript_json.is_file():
        raise RuntimeError("Word-level transcript JSON is missing")
    packed_transcript = build_packed_transcript(work, transcript_json)
    evidence = OVERVIEW.prepare_overview(Path(acquisition["local_video"]), verify, args.mode_samples)
    state = {
        "source": source,
        "project_dir": str(project.resolve()),
        "acquisition": str((work / "acquisition.json").resolve()),
        "transcript": str(transcript.resolve()),
        "transcript_json": str(transcript_json.resolve()),
        "packed_transcript": str(packed_transcript.resolve()),
        "mode_evidence": str((verify / "mode-evidence.json").resolve()),
        "suggested_mode": evidence["suggested_mode"],
    }
    write_json(work / "run-state.json", state)
    emit_progress("prepare", "complete", output=str(project), image=evidence["overview"])
    return project


def normalize_mode(mode: str) -> str:
    return MODE_ALIASES.get(mode, mode)


def save_route_decision(
    project: Path,
    mode: str,
    strategies: list[str] | None = None,
    reasons: list[str] | None = None,
    conversation_profile: str | None = None,
) -> dict:
    selected = normalize_mode(mode)
    if selected not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported mode: {mode}")
    profile = conversation_profile or ("general" if selected == "conversation" else None)
    if profile and selected != "conversation":
        raise ValueError("--conversation-profile is only valid for conversation mode")
    if profile and profile not in CONVERSATION_PROFILES:
        raise ValueError(f"Unsupported conversation profile: {profile}")
    decision = {
        "selected": selected,
        "requested": mode,
        "visual_strategies": list(dict.fromkeys(strategies or DEFAULT_STRATEGIES[selected])),
        "conversation_profile": profile,
        "reasons": reasons or ["Codex inspected the whole-video overview and transcript evidence"],
        "status": "confirmed",
    }
    write_json(project / "work" / "route-decision.json", decision)
    write_json(project / "work" / "mode-decision.json", decision)
    return decision


def resolve_route(project: Path, requested_mode: str, args: argparse.Namespace) -> dict:
    selected = normalize_mode(requested_mode)
    if selected == "auto":
        path = project / "work" / "route-decision.json"
        if not path.is_file():
            raise RuntimeError(
                "Automatic routing requires Codex confirmation. Inspect verify/mode-overview.jpg, "
                "then run --stage route with an explicit mode."
            )
        return read_json(path)
    return save_route_decision(
        project,
        selected,
        strategies=args.visual_strategy,
        reasons=args.mode_reason,
        conversation_profile=getattr(args, "conversation_profile", None),
    )


def source_chapters(acquisition: dict) -> list[dict]:
    """Read normalized official YouTube chapters without making them hard boundaries."""
    info_path = acquisition.get("info_json")
    if not info_path or not Path(info_path).is_file():
        return []
    try:
        raw = read_json(Path(info_path)).get("chapters") or []
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    chapters = []
    for item in raw:
        start = item.get("start_time")
        end = item.get("end_time")
        if start is None or end is None or float(end) <= float(start):
            continue
        chapters.append(
            {
                "start_sec": float(start),
                "end_sec": float(end),
                "title": str(item.get("title") or "Untitled chapter"),
            }
        )
    return chapters


def build_scenes(project: Path, mode: str, args: argparse.Namespace) -> Path:
    work = project / "work"
    state = read_json(work / "run-state.json")
    acquisition = read_json(Path(state["acquisition"]))
    route = resolve_route(project, mode, args)
    selected = route["selected"]
    manifest = SCENES.build_manifest(
        Path(acquisition["local_video"]),
        Path(state["transcript"]),
        selected,
        work,
        title=acquisition.get("title"),
        video_id=acquisition.get("video_id"),
        target_seconds=args.target_seconds,
        boundaries=args.boundaries.resolve() if args.boundaries else None,
        visual_strategies=route.get("visual_strategies") or [],
        conversation_profile=route.get("conversation_profile"),
        slide_rect=args.slide_rect,
        slide_backend=args.slide_backend,
        slide_interval=args.slide_interval,
        slide_threshold=args.slide_threshold,
    )
    mode_details = manifest.get("mode") or {}
    mode_details.update(read_json(work / "mode-decision.json"))
    manifest["mode"] = mode_details
    write_json(work / "scene-manifest.json", manifest)
    return work / "scene-manifest.json"


def prepare_timeline(project: Path, mode: str, args: argparse.Namespace) -> dict:
    work = project / "work"
    state = read_json(work / "run-state.json")
    acquisition = read_json(Path(state["acquisition"]))
    route = resolve_route(project, mode, args)
    selected = route["selected"]
    if selected == "slides":
        raise RuntimeError(
            "Slides mode uses hybrid-keyframe + SSIM and does not need semantic timeline boundaries"
        )
    return TIMELINE.prepare_timeline(
        Path(acquisition["local_video"]),
        Path(state["transcript"]),
        selected,
        work,
        packed_transcript=Path(state["packed_transcript"]),
        transcript_json=Path(state["transcript_json"]),
        video_use_dir=resolve_video_use_skill(),
        conversation_profile=route.get("conversation_profile"),
        source_chapters=source_chapters(acquisition),
    )


def prepare_batches(project: Path, batch_size: int) -> list[Path]:
    work = project / "work"
    return BATCHES.prepare_batches(
        work / "scene-manifest.json",
        work / "codex-batches",
        work / "codex-notes",
        batch_size=batch_size,
    )


def confirm_keyframes(project: Path, selections: Path | None) -> dict:
    manifest = project / "work" / "scene-manifest.json"
    chosen = read_json(selections.resolve()) if selections else {}
    return KEYFRAMES.apply_selections(manifest, chosen)


def finalize(project: Path, no_zip: bool) -> dict:
    work = project / "work"
    result = OUTPUTS.build_share(
        work / "scene-manifest.json",
        work / "codex-notes",
        project,
        no_zip=no_zip,
    )
    result["quality_audit"] = AUDIT.audit_project(project)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?")
    parser.add_argument(
        "--stage",
        choices=["prepare", "route", "timeline", "scenes", "select", "batches", "audit", "usage", "finalize"],
        required=True,
    )
    parser.add_argument("--project-dir", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path("outputs/video-notes"))
    parser.add_argument(
        "--mode",
        choices=["auto", "slides", "explainer", "conversation", "demo", "presentation", "editorial"],
        default="auto",
    )
    parser.add_argument("--mode-reason", action="append")
    parser.add_argument(
        "--conversation-profile",
        choices=sorted(CONVERSATION_PROFILES),
        help="Conversation subtype: studio, edited, news, chaptered, or general",
    )
    parser.add_argument(
        "--visual-strategy",
        action="append",
        choices=["slide-state", "speaker", "evidence", "broll", "dense-visual", "document-evidence", "screen-state"],
    )
    parser.add_argument("--slide-rect", help="Relative PPT crop x1,y1,x2,y2; defaults to full frame")
    parser.add_argument("--slide-backend", choices=["hybrid-keyframe", "accurate"], default="hybrid-keyframe")
    parser.add_argument("--slide-interval", type=float, default=2.0)
    parser.add_argument("--slide-threshold", type=float, default=0.90)
    parser.add_argument("--lang", default="zh")
    parser.add_argument("--max-height", type=int, default=1080)
    parser.add_argument("--cookies-from-browser", default="chrome")
    parser.add_argument("--no-browser-cookies", action="store_true")
    parser.add_argument(
        "--use-source-subtitles",
        action="store_true",
        help="Use supplied/manual subtitles instead of the default Volcengine transcription",
    )
    parser.add_argument("--provider", choices=["auto", "volcengine", "whisper"], default="volcengine")
    parser.add_argument("--mode-samples", type=int, default=16)
    parser.add_argument(
        "--target-seconds",
        type=float,
        help="Explicit fixed-time compatibility fallback; semantic boundaries are preferred",
    )
    parser.add_argument("--boundaries", type=Path)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--selections", type=Path)
    parser.add_argument("--no-zip", action="store_true")
    parser.add_argument("--usage-stage", help="Model-heavy stage name for --stage usage")
    parser.add_argument("--model-name", help="Model identifier for --stage usage")
    parser.add_argument("--input-tokens", type=int)
    parser.add_argument("--output-tokens", type=int)
    parser.add_argument("--cached-input-tokens", type=int, default=0)
    parser.add_argument("--cost-usd", type=float)
    parser.add_argument("--input-rate-per-million", type=float)
    parser.add_argument("--cached-input-rate-per-million", type=float)
    parser.add_argument("--output-rate-per-million", type=float)
    args = parser.parse_args()

    if args.stage == "prepare":
        if not args.source:
            parser.error("source is required for --stage prepare")
        project = prepare(args.source, args.output_root.resolve(), args)
        print(f"PROJECT_DIR={project.resolve()}")
        return
    if not args.project_dir:
        parser.error("--project-dir is required after prepare")
    project = args.project_dir.resolve()
    if args.stage == "route":
        if args.mode == "auto":
            parser.error("--stage route requires an explicit --mode")
        print(
            json.dumps(
                save_route_decision(
                    project,
                    args.mode,
                    args.visual_strategy,
                    args.mode_reason,
                    args.conversation_profile,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.stage == "timeline":
        print(json.dumps(prepare_timeline(project, args.mode, args), ensure_ascii=False, indent=2))
    elif args.stage == "scenes":
        print(build_scenes(project, args.mode, args))
    elif args.stage == "select":
        print(json.dumps(confirm_keyframes(project, args.selections)["keyframe_review"], ensure_ascii=False))
    elif args.stage == "batches":
        for path in prepare_batches(project, args.batch_size):
            print(path)
    elif args.stage == "audit":
        print(json.dumps(AUDIT.audit_project(project), ensure_ascii=False, indent=2))
    elif args.stage == "usage":
        required = {
            "--usage-stage": args.usage_stage,
            "--model-name": args.model_name,
            "--input-tokens": args.input_tokens,
            "--output-tokens": args.output_tokens,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            parser.error("--stage usage requires " + ", ".join(missing))
        print(
            json.dumps(
                AUDIT.record_usage(
                    project,
                    stage=args.usage_stage,
                    model=args.model_name,
                    input_tokens=args.input_tokens,
                    output_tokens=args.output_tokens,
                    cached_input_tokens=args.cached_input_tokens,
                    cost_usd=args.cost_usd,
                    input_rate_per_million=args.input_rate_per_million,
                    cached_input_rate_per_million=args.cached_input_rate_per_million,
                    output_rate_per_million=args.output_rate_per_million,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(json.dumps(finalize(project, args.no_zip), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
