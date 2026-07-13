#!/usr/bin/env python3
"""Prepare an audio-first semantic boundary review using video-use artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from video_notes_common import parse_transcript_file, probe_video, read_json, write_json


MODE_BOUNDARY_RULES = {
    "explainer": "One complete argument, example, or visual function per scene. Camera cuts alone are not boundaries.",
    "conversation": "One complete question-answer exchange or topic unit per scene. Do not split every speaker turn.",
    "demo": "One executable action, workflow step, or observable UI result per scene. Preserve prerequisites and outcomes.",
}


def prepare_timeline(
    video: Path,
    transcript: Path,
    mode: str,
    work_dir: Path,
    packed_transcript: Path | None = None,
    transcript_json: Path | None = None,
    video_use_dir: Path | None = None,
    conversation_profile: str | None = None,
    source_chapters: list[dict] | None = None,
) -> dict:
    if mode == "editorial":
        mode = "explainer"
    if mode not in MODE_BOUNDARY_RULES:
        raise ValueError(f"Unsupported mode: {mode}")
    cues = parse_transcript_file(transcript)
    if not cues:
        raise ValueError("Transcript contains no timed utterances")
    if not packed_transcript or not packed_transcript.is_file():
        raise ValueError("video-use takes_packed.md is required")
    if not transcript_json or not transcript_json.is_file():
        raise ValueError("video-use-compatible word transcript JSON is required")
    if not video_use_dir or not (video_use_dir / "helpers" / "timeline_view.py").is_file():
        raise ValueError("video-use timeline_view.py is required")

    timeline_dir = work_dir / "timeline"
    verify_dir = work_dir.parent / "verify" / "boundary-timelines"
    worksheet = timeline_dir / "boundary-review.md"
    chapter_hints_path = timeline_dir / "chapter-hints.json"
    worksheet.parent.mkdir(parents=True, exist_ok=True)
    verify_dir.mkdir(parents=True, exist_ok=True)
    duration = probe_video(video)["duration_sec"]
    rows = [
                "# Semantic Boundary Review",
                "",
                f"Mode: {mode}",
                f"Conversation profile: {conversation_profile or 'n/a'}",
                f"Rule: {MODE_BOUNDARY_RULES[mode]}",
                "",
                f"Primary transcript: `{packed_transcript.resolve()}`",
                f"Word timeline: `{transcript_json.resolve()}`",
                "",
                "Read the packed transcript first. Propose boundaries at phrase ends using semantic completion, silence gaps, and speaker handoffs.",
                "For every proposed boundary T, run video-use timeline_view on approximately T-4s to T+4s and inspect the filmstrip, waveform, words, and silence shading.",
                "Do not scan the whole video on a fixed interval. Visuals are used only to confirm or adjust actual decision points.",
                "",
    ]
    chapters = source_chapters or []
    if mode == "conversation" and chapters:
        write_json(chapter_hints_path, {"source": "official_metadata", "chapters": chapters})
        rows.extend(
            [
                f"Official chapter hints: `{chapter_hints_path.resolve()}`",
                "Use official chapters only as coarse topic proposals. Merge or split them to preserve complete questions, answers, examples, and qualifications.",
                "",
            ]
        )
    rows.extend(
        [
                "Write scene-boundaries.json as:",
                '{"mode":"' + mode + '","scenes":[{"end_sec":42.35,"reason":"complete argument and clean pause"}]}',
                f"The final end_sec must cover the final cue at {cues[-1]['end_sec']:.3f}s (video duration {duration:.3f}s).",
                "",
        ]
    )
    worksheet.write_text("\n".join(rows), encoding="utf-8")
    evidence = {
        "mode": mode,
        "segmentation": "audio_first_semantic_review",
        "packed_transcript": str(packed_transcript.resolve()),
        "transcript_json": str(transcript_json.resolve()),
        "worksheet": str(worksheet.resolve()),
        "boundary_verify_dir": str(verify_dir.resolve()),
        "timeline_view": str((video_use_dir / "helpers" / "timeline_view.py").resolve()),
        "video": str(video.resolve()),
        "final_cue_end_sec": float(cues[-1]["end_sec"]),
        "conversation_profile": conversation_profile if mode == "conversation" else None,
        "chapter_hints": str(chapter_hints_path.resolve()) if chapters else None,
        "chapter_count": len(chapters),
    }
    write_json(timeline_dir / "timeline-evidence.json", evidence)
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--mode", choices=list(MODE_BOUNDARY_RULES) + ["editorial"], required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--packed-transcript", type=Path, required=True)
    parser.add_argument("--transcript-json", type=Path, required=True)
    parser.add_argument("--video-use-dir", type=Path, required=True)
    parser.add_argument(
        "--conversation-profile",
        choices=["general", "studio", "edited", "news", "chaptered"],
    )
    parser.add_argument("--chapter-hints", type=Path, help="JSON array of normalized official chapters")
    args = parser.parse_args()
    chapters = read_json(args.chapter_hints.resolve()) if args.chapter_hints else []
    if isinstance(chapters, dict):
        chapters = chapters.get("chapters") or []
    print(
        json.dumps(
            prepare_timeline(
                args.video.resolve(),
                args.transcript.resolve(),
                args.mode,
                args.work_dir.resolve(),
                args.packed_transcript.resolve(),
                args.transcript_json.resolve(),
                args.video_use_dir.resolve(),
                conversation_profile=args.conversation_profile,
                source_chapters=chapters,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
