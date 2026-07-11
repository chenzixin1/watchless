#!/usr/bin/env python3
"""Build presentation or editorial scene manifests and candidate images."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from video_notes_common import (
    emit_progress,
    extract_video_frame,
    format_timestamp,
    group_cues,
    make_contact_sheet,
    parse_transcript_file,
    probe_video,
    read_json,
    source_fingerprint,
    write_json,
)


def build_editorial_scene_records(
    cues: list[dict[str, Any]], target_seconds: float = 90.0
) -> list[dict[str, Any]]:
    grouped = group_cues(cues, target_seconds=target_seconds)
    records: list[dict[str, Any]] = []
    for index, scene in enumerate(grouped, start=1):
        records.append(
            {
                "id": index,
                "start_sec": float(scene["start_sec"]),
                "end_sec": float(scene["end_sec"]),
                "frame_timestamp_sec": None,
                "frame_path": None,
                "visual_role": "unknown",
                "transcript_text": "".join(scene["cue_texts"]),
            }
        )
    return records


def validate_manifest(manifest: dict[str, Any], check_files: bool = True) -> list[str]:
    errors: list[str] = []
    scenes = manifest.get("scenes") or []
    previous_end = -1.0
    for scene in scenes:
        scene_id = scene.get("id")
        start = float(scene.get("start_sec") or 0)
        end = float(scene.get("end_sec") or 0)
        frame_time = scene.get("frame_timestamp_sec")
        if end < start:
            errors.append(f"scene {scene_id}: end before start")
        if start < previous_end:
            errors.append(f"scene {scene_id}: overlaps previous scene")
        if frame_time is not None and not (start <= float(frame_time) <= end):
            errors.append(f"scene {scene_id}: frame timestamp outside scene")
        frame_path = scene.get("frame_path")
        if check_files and (not frame_path or not Path(frame_path).is_file()):
            errors.append(f"scene {scene_id}: frame file missing")
        if not str(scene.get("transcript_text") or "").strip():
            errors.append(f"scene {scene_id}: transcript text missing")
        previous_end = end
    if not scenes:
        errors.append("manifest contains no scenes")
    return errors


def extract_editorial_candidates(
    video: Path,
    scenes: list[dict[str, Any]],
    work_dir: Path,
    candidates_per_scene: int = 5,
) -> None:
    candidate_root = work_dir / "candidates"
    keyframe_root = work_dir / "keyframes"
    verify_root = work_dir.parent / "verify" / "candidate-contact-sheets"
    candidate_root.mkdir(parents=True, exist_ok=True)
    keyframe_root.mkdir(parents=True, exist_ok=True)
    sheets: list[Path] = []
    for index, scene in enumerate(scenes, start=1):
        start, end = float(scene["start_sec"]), float(scene["end_sec"])
        usable_end = max(start, end - 0.05)
        if candidates_per_scene == 1 or usable_end <= start:
            times = [(start + usable_end) / 2]
        else:
            step = (usable_end - start) / (candidates_per_scene + 1)
            times = [start + step * (offset + 1) for offset in range(candidates_per_scene)]
        scene_dir = candidate_root / f"scene_{index:03d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[tuple[float, Path]] = []
        for candidate_no, seconds in enumerate(times, start=1):
            path = scene_dir / f"candidate_{candidate_no:02d}_{format_timestamp(seconds).replace(':', '-')}.jpg"
            extract_video_frame(video, seconds, path)
            candidates.append((seconds, path))
        chosen_time, chosen_path = candidates[len(candidates) // 2]
        selected = keyframe_root / f"scene_{index:03d}_{format_timestamp(chosen_time).replace(':', '-')}.jpg"
        selected.write_bytes(chosen_path.read_bytes())
        scene["frame_timestamp_sec"] = chosen_time
        scene["frame_path"] = str(selected.resolve())
        scene["candidate_paths"] = [str(path.resolve()) for _, path in candidates]
        scene["candidate_timestamps_sec"] = [seconds for seconds, _ in candidates]
        scene["selection_method"] = "pending_codex_visual_review"
        sheet = verify_root / f"scene_{index:03d}.jpg"
        make_contact_sheet(
            [path for _, path in candidates],
            [format_timestamp(seconds) for seconds, _ in candidates],
            sheet,
            columns=min(candidates_per_scene, 5),
        )
        sheets.append(sheet)
        emit_progress("keyframes", "running", completed=index, total=len(scenes), image=str(sheet))

    overview = work_dir.parent / "verify" / "selected-keyframes.jpg"
    make_contact_sheet(
        [Path(scene["frame_path"]) for scene in scenes],
        [f"{scene['id']:02d} {format_timestamp(scene['frame_timestamp_sec'])}" for scene in scenes],
        overview,
        columns=5,
    )
    emit_progress("keyframes", "complete", completed=len(scenes), total=len(scenes), image=str(overview))


def build_manifest(
    video: Path,
    transcript: Path,
    mode: str,
    work_dir: Path,
    title: str | None = None,
    video_id: str | None = None,
    target_seconds: float = 90.0,
) -> dict[str, Any]:
    metadata = probe_video(video)
    if mode in {"editorial", "presentation"}:
        cues = parse_transcript_file(transcript)
        scene_seconds = min(target_seconds, 30.0) if mode == "presentation" else target_seconds
        scenes = build_editorial_scene_records(cues, target_seconds=scene_seconds)
        for scene in scenes:
            scene["visual_role"] = "slide" if mode == "presentation" else "unknown"
        extract_editorial_candidates(video, scenes, work_dir)
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    manifest = {
        "schema_version": 1,
        "source": {
            "title": title or video.stem,
            "video_id": video_id,
            "local_video": str(video.resolve()),
            "duration_sec": metadata["duration_sec"],
            "fingerprint": source_fingerprint(video),
        },
        "mode": {"selected": mode},
        "transcript": {"path": str(transcript.resolve())},
        "scenes": scenes,
    }
    errors = validate_manifest(manifest)
    if errors:
        raise RuntimeError("Invalid scene manifest:\n- " + "\n- ".join(errors))
    write_json(work_dir / "scene-manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--mode", choices=["editorial", "presentation"], required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--title")
    parser.add_argument("--video-id")
    parser.add_argument("--target-seconds", type=float, default=90.0)
    args = parser.parse_args()
    manifest = build_manifest(
        args.video.resolve(),
        args.transcript.resolve(),
        args.mode,
        args.work_dir.resolve(),
        title=args.title,
        video_id=args.video_id,
        target_seconds=args.target_seconds,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
