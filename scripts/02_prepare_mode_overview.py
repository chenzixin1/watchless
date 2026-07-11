#!/usr/bin/env python3
"""Create a time-sampled contact sheet for direct Codex mode review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from video_notes_common import (
    emit_progress,
    extract_video_frame,
    format_timestamp,
    make_contact_sheet,
    probe_video,
    write_json,
)


def sample_timestamps(duration: float, samples: int) -> list[float]:
    if samples < 1:
        raise ValueError("samples must be positive")
    return [
        min(max(0.0, duration - 0.2), max(0.0, duration * (0.03 + 0.94 * index / max(1, samples - 1))))
        for index in range(samples)
    ]


def prepare_overview(video: Path, verify_dir: Path, samples: int = 16) -> dict:
    metadata = probe_video(video)
    timestamps = sample_timestamps(metadata["duration_sec"], samples)
    frame_dir = verify_dir / "mode-samples"
    frames: list[Path] = []
    labels: list[str] = []
    for index, seconds in enumerate(timestamps, start=1):
        path = frame_dir / f"sample_{index:02d}_{format_timestamp(seconds).replace(':', '-')}.jpg"
        extract_video_frame(video, seconds, path)
        frames.append(path)
        labels.append(f"{index:02d} {format_timestamp(seconds)}")

    overview = verify_dir / "mode-overview.jpg"
    make_contact_sheet(frames, labels, overview, columns=4)
    evidence = {
        "suggested_mode": "codex_review_required",
        "confidence": None,
        "sample_timestamps_sec": [round(value, 3) for value in timestamps],
        "media": metadata,
        "overview": str(overview.resolve()),
        "decision_rule": "Codex directly inspects the contact sheet. Talking-head, interview, B-roll, or ambiguous video uses editorial; stable slide-led video uses presentation.",
    }
    write_json(verify_dir / "mode-evidence.json", evidence)
    emit_progress("mode", "ready", image=str(overview), suggested_mode="codex_review_required")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--verify-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=16)
    args = parser.parse_args()
    print(json.dumps(prepare_overview(args.video.resolve(), args.verify_dir.resolve(), args.samples), indent=2))


if __name__ == "__main__":
    main()
