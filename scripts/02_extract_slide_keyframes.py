#!/usr/bin/env python3
"""Extract stable slide states with ffmpeg keyframes and local SSIM refinement."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
from skimage.metrics import structural_similarity

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from video_notes_common import extract_video_frame, make_contact_sheet, probe_video


PTS_RE = re.compile(r"pts_time:([0-9.]+)")


def parse_relative_rect(value: str | None) -> tuple[float, float, float, float]:
    if not value:
        return (0.0, 0.0, 1.0, 1.0)
    parts = tuple(float(part.strip()) for part in value.split(","))
    if len(parts) != 4:
        raise ValueError("slide rect must be x1,y1,x2,y2")
    x1, y1, x2, y2 = parts
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ValueError("slide rect coordinates must satisfy 0 <= x1 < x2 <= 1")
    return parts


def pixel_rect(
    relative: tuple[float, float, float, float], width: int, height: int
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = relative
    x = int(round(x1 * width))
    y = int(round(y1 * height))
    crop_width = max(2, int(round((x2 - x1) * width)))
    crop_height = max(2, int(round((y2 - y1) * height)))
    crop_width -= crop_width % 2
    crop_height -= crop_height % 2
    return x, y, crop_width, crop_height


def ssim_score(previous: np.ndarray, current: np.ndarray) -> float:
    data_range = max(int(previous.max()) - int(previous.min()), 1)
    return float(structural_similarity(previous, current, data_range=data_range))


def change_times(frames: list[dict[str, Any]], threshold: float) -> list[float]:
    if not frames:
        return []
    changes = [float(frames[0]["time_sec"])]
    for previous, current in zip(frames, frames[1:]):
        if ssim_score(previous["gray"], current["gray"]) < threshold:
            changes.append(float(current["time_sec"]))
    return changes


def cluster_times(times: list[float], gap_sec: float = 12.0) -> list[list[float]]:
    clusters: list[list[float]] = []
    for value in sorted(times):
        if not clusters or value - clusters[-1][-1] > gap_sec:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return clusters


def merge_windows(windows: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[list[float]] = []
    for start, end in sorted(windows):
        if not merged or start > merged[-1][1] + 1e-6:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def _read_raw_gray(
    command: list[str], frame_width: int, frame_height: int
) -> tuple[list[np.ndarray], str]:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    frame_size = frame_width * frame_height
    frames: list[np.ndarray] = []
    while True:
        payload = process.stdout.read(frame_size)
        if not payload:
            break
        if len(payload) != frame_size:
            raise RuntimeError("ffmpeg returned a partial grayscale frame")
        frames.append(
            np.frombuffer(payload, dtype=np.uint8)
            .reshape((frame_height, frame_width))
            .copy()
        )
    process.stdout.close()
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    if process.wait() != 0:
        raise RuntimeError(stderr[-2000:] or "ffmpeg grayscale extraction failed")
    return frames, stderr


def keyframe_scan(
    video: Path,
    crop: tuple[int, int, int, int],
    detect_width: int,
) -> list[dict[str, Any]]:
    x, y, crop_width, crop_height = crop
    detect_height = max(2, round(crop_height * detect_width / crop_width))
    detect_height -= detect_height % 2
    video_filter = (
        f"crop={crop_width}:{crop_height}:{x}:{y},"
        f"scale={detect_width}:{detect_height},format=gray,showinfo"
    )
    frames, stderr = _read_raw_gray(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "info",
            "-skip_frame",
            "nokey",
            "-i",
            str(video),
            "-an",
            "-sn",
            "-vf",
            video_filter,
            "-vsync",
            "0",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-",
        ],
        detect_width,
        detect_height,
    )
    times = [float(match.group(1)) for match in PTS_RE.finditer(stderr)]
    return [
        {"time_sec": time_sec, "gray": gray}
        for time_sec, gray in zip(times, frames)
    ]


def interval_scan(
    video: Path,
    crop: tuple[int, int, int, int],
    detect_width: int,
    interval_sec: float,
    start_sec: float,
    end_sec: float,
) -> list[dict[str, Any]]:
    if end_sec <= start_sec:
        return []
    x, y, crop_width, crop_height = crop
    detect_height = max(2, round(crop_height * detect_width / crop_width))
    detect_height -= detect_height % 2
    frames, _ = _read_raw_gray(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start_sec:.6f}",
            "-t",
            f"{end_sec - start_sec:.6f}",
            "-i",
            str(video),
            "-an",
            "-sn",
            "-vf",
            (
                f"fps={1.0 / interval_sec:.9f},crop={crop_width}:{crop_height}:{x}:{y},"
                f"scale={detect_width}:{detect_height},format=gray"
            ),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-",
        ],
        detect_width,
        detect_height,
    )
    return [
        {"time_sec": start_sec + index * interval_sec, "gray": gray}
        for index, gray in enumerate(frames)
    ]


def dedupe_times(times: list[float], min_gap_sec: float = 0.75) -> list[float]:
    result: list[float] = []
    for value in sorted(max(0.0, item) for item in times):
        if not result or value - result[-1] >= min_gap_sec:
            result.append(value)
    return result


def detect_slide_starts(
    video: Path,
    slide_rect: str | None = None,
    interval_sec: float = 2.0,
    threshold: float = 0.90,
    detect_width: int = 240,
    backend: str = "hybrid-keyframe",
) -> dict[str, Any]:
    metadata = probe_video(video)
    duration = float(metadata["duration_sec"])
    relative = parse_relative_rect(slide_rect)
    crop = pixel_rect(relative, metadata["width"], metadata["height"])

    starts: list[float] = []
    used_backend = backend
    if backend == "hybrid-keyframe":
        keyframes = keyframe_scan(video, crop, detect_width)
        candidates = change_times(keyframes, threshold)
        windows: list[tuple[float, float]] = []
        starts = [0.0]
        for cluster in cluster_times(candidates):
            if len(cluster) == 1:
                starts.append(round(cluster[0] / interval_sec) * interval_sec)
            else:
                windows.append(
                    (
                        max(0.0, cluster[0] - 2 * interval_sec),
                        min(duration, cluster[-1] + 3 * interval_sec),
                    )
                )
        windows.append((max(0.0, duration - 4 * interval_sec), duration))
        for start, end in merge_windows(windows):
            starts.extend(
                change_times(
                    interval_scan(video, crop, detect_width, interval_sec, start, end),
                    threshold,
                )
            )
        if len(keyframes) < 2:
            used_backend = "accurate"

    if backend == "accurate" or used_backend == "accurate":
        starts = change_times(
            interval_scan(video, crop, detect_width, interval_sec, 0.0, duration),
            threshold,
        )

    starts = [value for value in dedupe_times([0.0, *starts]) if value < duration]
    return {
        "backend": used_backend,
        "threshold": threshold,
        "interval_sec": interval_sec,
        "slide_rect": list(relative),
        "duration_sec": duration,
        "starts": starts,
    }


def materialize_slide_frames(
    video: Path,
    detection: dict[str, Any],
    output_dir: Path,
) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    starts = detection["starts"]
    duration = float(detection["duration_sec"])
    relative = tuple(detection["slide_rect"])
    metadata = probe_video(video)
    x, y, width, height = pixel_rect(relative, metadata["width"], metadata["height"])
    crop_is_full = relative == (0.0, 0.0, 1.0, 1.0)
    records: list[dict[str, Any]] = []
    images: list[Path] = []
    labels: list[str] = []
    for index, start in enumerate(starts, start=1):
        end = starts[index] if index < len(starts) else duration
        capture = max(start, end - min(0.35, max(0.05, (end - start) / 4)))
        output = output_dir / f"slide_{index:03d}_{capture:010.3f}.png"
        if crop_is_full:
            extract_video_frame(video, capture, output)
        else:
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{capture:.3f}",
                    "-i",
                    str(video),
                    "-vf",
                    f"crop={width}:{height}:{x}:{y}",
                    "-frames:v",
                    "1",
                    "-y",
                    str(output),
                ],
                check=True,
            )
        images.append(output)
        labels.append(f"{index:03d} {start:.1f}s-{end:.1f}s")
        records.append(
            {
                "id": index,
                "start_sec": start,
                "end_sec": end,
                "frame_timestamp_sec": capture,
                "frame_path": str(output.resolve()),
                "candidate_paths": [str(output.resolve())],
                "candidate_timestamps_sec": [capture],
                "selection_method": "hybrid_ssim_pending_codex_review",
                "preferred_candidate": 1,
            }
        )
    if images:
        make_contact_sheet(images, labels, output_dir.parent.parent / "verify" / "selected-keyframes.jpg", columns=5)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--slide-rect")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--threshold", type=float, default=0.90)
    parser.add_argument("--detect-width", type=int, default=240)
    parser.add_argument("--backend", choices=["hybrid-keyframe", "accurate"], default="hybrid-keyframe")
    args = parser.parse_args()
    detection = detect_slide_starts(
        args.video.resolve(),
        slide_rect=args.slide_rect,
        interval_sec=args.interval,
        threshold=args.threshold,
        detect_width=args.detect_width,
        backend=args.backend,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = materialize_slide_frames(args.video.resolve(), detection, args.output_dir.resolve())
    print(json.dumps({**detection, "slides": records}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
