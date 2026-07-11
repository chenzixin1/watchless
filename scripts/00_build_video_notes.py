#!/usr/bin/env python3
"""Stage-oriented entry point for the Codex video-notes workflow."""

from __future__ import annotations

import argparse
import json
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
KEYFRAMES = load_script("03_apply_codex_keyframes.py")
BATCHES = load_script("04_prepare_codex_scene_batches.py")
OUTPUTS = load_script("05_build_outputs.py")


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
    subtitle = acquisition.get("subtitle")
    if subtitle and Path(subtitle).is_file():
        cues = parse_transcript_file(Path(subtitle))
        if cues:
            write_timestamped_transcript(cues, transcript)
    if not transcript.is_file():
        command = [
            sys.executable,
            str(SCRIPT_DIR / "01_transcribe_video.py"),
            acquisition["local_video"],
            "--output",
            str(transcript),
            "--provider",
            args.provider,
        ]
        subprocess.run(command, check=True)
    evidence = OVERVIEW.prepare_overview(Path(acquisition["local_video"]), verify, args.mode_samples)
    state = {
        "source": source,
        "project_dir": str(project.resolve()),
        "acquisition": str((work / "acquisition.json").resolve()),
        "transcript": str(transcript.resolve()),
        "mode_evidence": str((verify / "mode-evidence.json").resolve()),
        "suggested_mode": evidence["suggested_mode"],
    }
    write_json(work / "run-state.json", state)
    emit_progress("prepare", "complete", output=str(project), image=evidence["overview"])
    return project


def build_scenes(project: Path, mode: str, args: argparse.Namespace) -> Path:
    work = project / "work"
    state = read_json(work / "run-state.json")
    acquisition = read_json(Path(state["acquisition"]))
    evidence = read_json(Path(state["mode_evidence"]))
    selected = evidence["suggested_mode"] if mode == "auto" else mode
    if selected not in {"editorial", "presentation"}:
        selected = "editorial"
    write_json(
        work / "mode-decision.json",
        {
            "selected": selected,
            "confidence": evidence.get("confidence"),
            "reasons": args.mode_reason or ["Codex inspected the mode overview"],
        },
    )
    manifest = SCENES.build_manifest(
        Path(acquisition["local_video"]),
        Path(state["transcript"]),
        selected,
        work,
        title=acquisition.get("title"),
        video_id=acquisition.get("video_id"),
        target_seconds=args.target_seconds,
    )
    manifest["mode"] = read_json(work / "mode-decision.json")
    write_json(work / "scene-manifest.json", manifest)
    return work / "scene-manifest.json"


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
    return OUTPUTS.build_share(
        work / "scene-manifest.json",
        work / "codex-notes",
        project,
        no_zip=no_zip,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?")
    parser.add_argument("--stage", choices=["prepare", "scenes", "select", "batches", "finalize"], required=True)
    parser.add_argument("--project-dir", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path("outputs/video-notes"))
    parser.add_argument("--mode", choices=["auto", "editorial", "presentation"], default="auto")
    parser.add_argument("--mode-reason", action="append")
    parser.add_argument("--lang", default="zh")
    parser.add_argument("--max-height", type=int, default=1080)
    parser.add_argument("--cookies-from-browser", default="chrome")
    parser.add_argument("--no-browser-cookies", action="store_true")
    parser.add_argument("--provider", choices=["auto", "volcengine", "whisper"], default="auto")
    parser.add_argument("--mode-samples", type=int, default=16)
    parser.add_argument("--target-seconds", type=float, default=90.0)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--selections", type=Path)
    parser.add_argument("--no-zip", action="store_true")
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
    if args.stage == "scenes":
        print(build_scenes(project, args.mode, args))
    elif args.stage == "select":
        print(json.dumps(confirm_keyframes(project, args.selections)["keyframe_review"], ensure_ascii=False))
    elif args.stage == "batches":
        for path in prepare_batches(project, args.batch_size):
            print(path)
    else:
        print(json.dumps(finalize(project, args.no_zip), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
