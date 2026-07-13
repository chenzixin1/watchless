#!/usr/bin/env python3
"""Build slide, explainer, conversation, or demo scene manifests."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
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


SUPPORTED_MODES = {"slides", "explainer", "conversation", "demo"}
SPEAKER_RE = re.compile(r"(说话人[^:：\s]+)\s*[:：]")
EVIDENCE_TRIGGER_RE = re.compile(
    r"(?:图表|图中|画面|数据|数字|报告|研究|论文|页面|屏幕|产品|芯片|模型|"
    r"我们来看|可以看到|这里显示|如图|this\s+(?:chart|graph|figure|screen|slide)|"
    r"look\s+at|as\s+you\s+can\s+see|the\s+data|the\s+report|shown\s+here)",
    re.IGNORECASE,
)


def load_script(name: str):
    path = SCRIPT_DIR / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SLIDES = load_script("02_extract_slide_keyframes.py")


def build_editorial_scene_records(
    cues: list[dict[str, Any]], target_seconds: float
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


def speaker_labels(text: str) -> list[str]:
    """Return stable diarization labels in first-seen order."""
    return list(dict.fromkeys(SPEAKER_RE.findall(text or "")))


def build_boundary_scene_records(
    cues: list[dict[str, Any]], boundary_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Build scenes from Codex-reviewed, cue-aligned semantic boundaries."""
    boundaries = boundary_data.get("scenes") or []
    if not boundaries:
        raise ValueError("Scene boundary file contains no scenes")
    records = []
    start_index = 0
    for scene_id, boundary in enumerate(boundaries, start=1):
        requested_end = boundary.get("end_sec")
        if requested_end is not None:
            end_index = start_index
            # Keep the cue containing the requested word boundary in the earlier scene.
            # This snaps forward to a complete utterance instead of dropping its opening words.
            while end_index < len(cues) and float(cues[end_index]["start_sec"]) < float(requested_end) - 0.05:
                end_index += 1
            if scene_id == len(boundaries) and float(requested_end) >= float(cues[-1]["end_sec"]) - 0.15:
                end_index = len(cues)
        else:
            end_index = int(boundary.get("end_cue") or 0)
        if end_index <= start_index or end_index > len(cues):
            raise ValueError(f"Invalid boundary ending at cue {end_index} for scene {scene_id}")
        selected = cues[start_index:end_index]
        records.append(
            {
                "id": scene_id,
                "start_sec": float(selected[0]["start_sec"]),
                "end_sec": float(selected[-1]["end_sec"]),
                "frame_timestamp_sec": None,
                "frame_path": None,
                "visual_role": "unknown",
                "transcript_text": "".join(cue["text"] for cue in selected),
                "boundary_reason": str(boundary.get("reason") or "Codex semantic review"),
                "boundary_requested_sec": requested_end,
                "boundary_actual_sec": float(selected[-1]["end_sec"]),
                "start_cue": start_index + 1,
                "end_cue": end_index,
            }
        )
        start_index = end_index
    if start_index != len(cues):
        raise ValueError(
            f"Scene boundaries stop at cue {start_index}; the final boundary must cover all {len(cues)} cues"
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


def candidate_positions(
    mode: str,
    strategies: list[str],
    conversation_profile: str | None = None,
) -> list[float]:
    if mode == "demo":
        return [0.08, 0.25, 0.50, 0.72, 0.90, 0.97]
    if mode == "conversation":
        if conversation_profile == "studio":
            return [0.20, 0.50, 0.80]
        if conversation_profile == "news":
            return [0.08, 0.20, 0.32, 0.44, 0.56, 0.68, 0.80, 0.92]
        if conversation_profile == "edited" or "broll" in strategies:
            return [0.08, 0.19, 0.30, 0.41, 0.52, 0.63, 0.74, 0.85, 0.94]
        return [0.15, 0.325, 0.50, 0.675, 0.85]
    if any(item in strategies for item in ("dense-visual", "document-evidence", "broll")):
        return [0.08, 0.19, 0.30, 0.41, 0.52, 0.63, 0.74, 0.85, 0.94]
    return [0.10, 0.233, 0.367, 0.50, 0.633, 0.767, 0.90]


def evidence_trigger_times(
    cues: list[dict[str, Any]], scene: dict[str, Any]
) -> list[tuple[float, str]]:
    """Return local candidate times around spoken references to visual evidence."""
    start, end = float(scene["start_sec"]), float(scene["end_sec"])
    selected = [
        cue
        for cue in cues
        if float(cue["start_sec"]) < end and float(cue["end_sec"]) > start
    ]
    times: list[tuple[float, str]] = []
    for cue in selected:
        match = EVIDENCE_TRIGGER_RE.search(str(cue.get("text") or ""))
        if not match:
            continue
        cue_start = max(start, float(cue["start_sec"]))
        cue_end = min(end, float(cue["end_sec"]))
        midpoint = (cue_start + cue_end) / 2
        for seconds in (midpoint, min(end - 0.05, midpoint + 1.5)):
            if start <= seconds <= end and all(abs(seconds - existing[0]) >= 0.75 for existing in times):
                times.append((seconds, f"evidence trigger: {match.group(0)}"))
    return times


def semantic_candidate_times(
    scene: dict[str, Any],
    cues: list[dict[str, Any]],
    mode: str,
    strategies: list[str],
    conversation_profile: str | None = None,
    max_candidates: int = 14,
    video_duration: float | None = None,
) -> list[tuple[float, str]]:
    start, end = float(scene["start_sec"]), float(scene["end_sec"])
    media_end = max(0.0, float(video_duration) - 0.20) if video_duration is not None else end
    usable_end = max(start, min(end - 0.05, media_end))
    if usable_end <= start:
        return [((start + usable_end) / 2, "scene midpoint")]
    positions = candidate_positions(mode, strategies, conversation_profile)
    values = [
        (start + (usable_end - start) * position, "distributed scene coverage")
        for position in positions
    ]
    should_probe_evidence = mode == "conversation" and (
        conversation_profile in {"edited", "news"}
        or any(strategy in strategies for strategy in ("evidence", "broll", "document-evidence"))
    )
    if should_probe_evidence:
        values.extend(evidence_trigger_times(cues, scene))
    values.sort(key=lambda item: item[0])
    deduplicated: list[tuple[float, str]] = []
    for item in values:
        if deduplicated and abs(item[0] - deduplicated[-1][0]) < 0.75:
            if item[1].startswith("evidence trigger"):
                deduplicated[-1] = item
            continue
        deduplicated.append(item)
    if len(deduplicated) > max_candidates:
        indexes = [round(index * (len(deduplicated) - 1) / (max_candidates - 1)) for index in range(max_candidates)]
        deduplicated = [deduplicated[index] for index in dict.fromkeys(indexes)]
    return deduplicated


def extract_semantic_candidates(
    video: Path,
    scenes: list[dict[str, Any]],
    work_dir: Path,
    mode: str,
    strategies: list[str],
    cues: list[dict[str, Any]],
    conversation_profile: str | None = None,
    video_duration: float | None = None,
) -> None:
    candidate_root = work_dir / "candidates"
    keyframe_root = work_dir / "keyframes"
    verify_root = work_dir.parent / "verify" / "candidate-contact-sheets"
    candidate_root.mkdir(parents=True, exist_ok=True)
    keyframe_root.mkdir(parents=True, exist_ok=True)
    sheets: list[Path] = []
    for index, scene in enumerate(scenes, start=1):
        candidate_specs = semantic_candidate_times(
            scene,
            cues,
            mode,
            strategies,
            conversation_profile=conversation_profile,
            video_duration=video_duration,
        )
        scene_dir = candidate_root / f"scene_{index:03d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[tuple[float, Path]] = []
        reasons: list[str] = []
        for candidate_no, (seconds, reason) in enumerate(candidate_specs, start=1):
            path = scene_dir / f"candidate_{candidate_no:02d}_{format_timestamp(seconds).replace(':', '-')}.jpg"
            extract_video_frame(video, seconds, path)
            candidates.append((seconds, path))
            reasons.append(reason)
        chosen_index = -2 if mode == "demo" and len(candidates) > 1 else len(candidates) // 2
        chosen_time, chosen_path = candidates[chosen_index]
        selected = keyframe_root / f"scene_{index:03d}_{format_timestamp(chosen_time).replace(':', '-')}.jpg"
        selected.write_bytes(chosen_path.read_bytes())
        scene["frame_timestamp_sec"] = chosen_time
        scene["frame_path"] = str(selected.resolve())
        scene["candidate_paths"] = [str(path.resolve()) for _, path in candidates]
        scene["candidate_timestamps_sec"] = [seconds for seconds, _ in candidates]
        scene["candidate_reasons"] = reasons
        scene["selection_method"] = "pending_codex_visual_review"
        scene["preferred_candidate"] = chosen_index % len(candidates) + 1
        sheet = verify_root / f"scene_{index:03d}.jpg"
        make_contact_sheet(
            [path for _, path in candidates],
            [
                f"{format_timestamp(seconds)}{' evidence' if reasons[item].startswith('evidence trigger') else ''}"
                for item, (seconds, _) in enumerate(candidates)
            ],
            sheet,
            columns=min(len(candidates), 5),
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


def attach_slide_transcript(
    slides: list[dict[str, Any]], cues: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    for slide in slides:
        start, end = float(slide["start_sec"]), float(slide["end_sec"])
        selected = [cue for cue in cues if start <= float(cue["start_sec"]) < end]
        slide["transcript_text"] = "".join(cue["text"] for cue in selected) or "（此画面没有对应口述内容。）"
        slide["visual_role"] = "slide"
        slide["speaker_labels"] = speaker_labels(slide["transcript_text"])
    return slides


def build_manifest(
    video: Path,
    transcript: Path,
    mode: str,
    work_dir: Path,
    title: str | None = None,
    video_id: str | None = None,
    target_seconds: float | None = None,
    boundaries: Path | None = None,
    visual_strategies: list[str] | None = None,
    conversation_profile: str | None = None,
    slide_rect: str | None = None,
    slide_backend: str = "hybrid-keyframe",
    slide_interval: float = 2.0,
    slide_threshold: float = 0.90,
) -> dict[str, Any]:
    metadata = probe_video(video)
    requested_mode = mode
    mode = {"presentation": "slides", "editorial": "explainer"}.get(mode, mode)
    strategies = list(dict.fromkeys(visual_strategies or []))
    cues = parse_transcript_file(transcript)
    slide_detection = None
    if mode == "slides":
        if boundaries:
            raise ValueError("Slides mode derives boundaries from hybrid-keyframe + SSIM, not semantic boundary files")
        slide_detection = SLIDES.detect_slide_starts(
            video,
            slide_rect=slide_rect,
            interval_sec=slide_interval,
            threshold=slide_threshold,
            backend=slide_backend,
        )
        scenes = attach_slide_transcript(
            SLIDES.materialize_slide_frames(video, slide_detection, work_dir / "keyframes"),
            cues,
        )
        scene_seconds = None
        segmentation = "hybrid_keyframe_local_ssim"
    elif mode in {"explainer", "conversation", "demo"}:
        if boundaries:
            boundary_data = read_json(boundaries)
            boundary_mode = boundary_data.get("mode")
            if boundary_mode and boundary_mode != mode:
                raise ValueError(
                    f"Boundary mode {boundary_mode} does not match selected mode {mode}"
                )
            scenes = build_boundary_scene_records(cues, boundary_data)
            scene_seconds = None
            segmentation = "codex_semantic_boundaries"
        elif target_seconds:
            scene_seconds = target_seconds
            scenes = build_editorial_scene_records(cues, target_seconds=scene_seconds)
            segmentation = "explicit_time_fallback"
        else:
            raise ValueError(
                "Semantic scene boundaries are required. Run --stage timeline, review the evidence, "
                "and pass --boundaries scene-boundaries.json. Use --target-seconds only as an "
                "explicit compatibility fallback."
            )
        for scene in scenes:
            scene["visual_role"] = {
                "explainer": "explanatory_visual",
                "conversation": "speaker",
                "demo": "screen_state",
            }[mode]
            scene["speaker_labels"] = speaker_labels(scene["transcript_text"])
        extract_semantic_candidates(
            video,
            scenes,
            work_dir,
            mode,
            strategies,
            cues,
            conversation_profile=conversation_profile,
            video_duration=metadata["duration_sec"],
        )
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
        "mode": {
            "selected": mode,
            "requested": requested_mode,
            "target_seconds": scene_seconds,
            "segmentation": segmentation,
            "visual_strategies": strategies,
            "conversation_profile": conversation_profile if mode == "conversation" else None,
        },
        "slide_detection": slide_detection,
        "transcript": {"path": str(transcript.resolve())},
        "scenes": scenes,
    }
    errors = validate_manifest(manifest)
    if errors:
        raise RuntimeError("Invalid scene manifest:\n- " + "\n- ".join(errors))
    write_json(work_dir / "scene-manifest.json", manifest)
    if mode == "conversation":
        labels = list(
            dict.fromkeys(
                label for scene in scenes for label in scene.get("speaker_labels", [])
            )
        )
        write_json(
            work_dir / "speaker-map.json",
            {
                "status": "needs_identity_research",
                "conversation_profile": conversation_profile or "general",
                "instructions": (
                    "Research source metadata, transcript self-introductions, subtitles, frames, "
                    "official episode pages, and channel history. Use turn_overrides when ASR labels merge people."
                ),
                "speakers": {label: None for label in labels},
                "identities": {},
                "turn_overrides": [],
                "sources": [],
            },
        )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("transcript", type=Path)
    parser.add_argument(
        "--mode",
        choices=["slides", "explainer", "conversation", "demo", "presentation", "editorial"],
        required=True,
    )
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--title")
    parser.add_argument("--video-id")
    parser.add_argument("--target-seconds", type=float)
    parser.add_argument("--boundaries", type=Path)
    parser.add_argument("--visual-strategy", action="append")
    parser.add_argument(
        "--conversation-profile",
        choices=["general", "studio", "edited", "news", "chaptered"],
    )
    parser.add_argument("--slide-rect")
    parser.add_argument("--slide-backend", choices=["hybrid-keyframe", "accurate"], default="hybrid-keyframe")
    parser.add_argument("--slide-interval", type=float, default=2.0)
    parser.add_argument("--slide-threshold", type=float, default=0.90)
    args = parser.parse_args()
    manifest = build_manifest(
        args.video.resolve(),
        args.transcript.resolve(),
        args.mode,
        args.work_dir.resolve(),
        title=args.title,
        video_id=args.video_id,
        target_seconds=args.target_seconds,
        boundaries=args.boundaries.resolve() if args.boundaries else None,
        visual_strategies=args.visual_strategy,
        conversation_profile=args.conversation_profile,
        slide_rect=args.slide_rect,
        slide_backend=args.slide_backend,
        slide_interval=args.slide_interval,
        slide_threshold=args.slide_threshold,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
