#!/usr/bin/env python3
"""Shared helpers for the local video-notes pipeline."""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw, ImageFont


YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
INLINE_SECONDS_RE = re.compile(
    r"^\[(\d+(?:\.\d+)?)s\s*-\s*(\d+(?:\.\d+)?)s\]\s*(.*?)$"
)
SRT_TIME_RE = re.compile(
    r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})"
)


def extract_video_id(value: str) -> str | None:
    raw = str(value or "").strip()
    if YOUTUBE_ID_RE.fullmatch(raw):
        return raw
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    host = parsed.netloc.lower().split(":", 1)[0]
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/", 1)[0]
        return candidate if YOUTUBE_ID_RE.fullmatch(candidate) else None
    if host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
        query_id = parse_qs(parsed.query).get("v", [""])[0]
        if YOUTUBE_ID_RE.fullmatch(query_id):
            return query_id
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            return parts[1] if YOUTUBE_ID_RE.fullmatch(parts[1]) else None
    return None


def safe_slug(value: str, fallback: str = "video") -> str:
    normalized = normalize_display_text(value)
    cleaned = re.sub(r"[\\/:：*?？\"<>|]+", "-", normalized.strip())
    cleaned = re.sub(r"\s+", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-.")
    return cleaned[:120] or fallback


def normalize_display_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return "".join(char for char in normalized if unicodedata.category(char)[0] != "C").strip()


def timestamp_to_seconds(value: str) -> float:
    normalized = value.strip().replace(",", ".")
    hours, minutes, seconds = normalized.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def format_timestamp(seconds: float, include_hours: bool = True) -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if include_hours or hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _clean_text(rows: list[str]) -> str:
    text = " ".join(row.strip() for row in rows if row.strip())
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_transcript_file(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    inline: list[dict[str, Any]] = []
    for line in text.splitlines():
        match = INLINE_SECONDS_RE.match(line.strip())
        if match:
            inline.append(
                {
                    "start_sec": float(match.group(1)),
                    "end_sec": float(match.group(2)),
                    "text": _clean_text([match.group(3)]),
                }
            )
    if inline:
        return [cue for cue in inline if cue["text"]]

    blocks = re.split(r"\r?\n\r?\n+", text.strip())
    cues: list[dict[str, Any]] = []
    for block in blocks:
        rows = [row.strip() for row in block.splitlines() if row.strip()]
        time_index = next((i for i, row in enumerate(rows) if "-->" in row), -1)
        if time_index < 0:
            continue
        match = SRT_TIME_RE.search(rows[time_index])
        if not match:
            continue
        cue_text = _clean_text(rows[time_index + 1 :])
        if cue_text:
            cues.append(
                {
                    "start_sec": timestamp_to_seconds(match.group(1)),
                    "end_sec": timestamp_to_seconds(match.group(2)),
                    "text": cue_text,
                }
            )
    return cues


def write_timestamped_transcript(cues: list[dict[str, Any]], path: Path) -> None:
    lines = ["Full Transcript:", "", "Utterances with timing:"]
    for cue in cues:
        lines.append(
            f"[{float(cue['start_sec']):.3f}s - {float(cue['end_sec']):.3f}s] {cue['text']}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def group_cues(cues: list[dict[str, Any]], target_seconds: float = 90.0) -> list[dict[str, Any]]:
    if not cues:
        return []
    scenes: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    scene_start = float(cues[0]["start_sec"])
    for cue in cues:
        cue_start = float(cue["start_sec"])
        if current and cue_start - scene_start >= target_seconds:
            scenes.append(
                {
                    "start_sec": scene_start,
                    "end_sec": float(current[-1]["end_sec"]),
                    "cue_texts": [item["text"] for item in current],
                }
            )
            current = []
            scene_start = cue_start
        current.append(cue)
    if current:
        scenes.append(
            {
                "start_sec": scene_start,
                "end_sec": float(current[-1]["end_sec"]),
                "cue_texts": [item["text"] for item in current],
            }
        )
    return scenes


def emit_progress(stage: str, status: str, **payload: Any) -> None:
    event = {"event": "video_notes_progress", "stage": stage, "status": status, **payload}
    print("VIDEO_NOTES_PROGRESS " + json.dumps(event, ensure_ascii=False), flush=True)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def source_fingerprint(path: Path) -> str:
    stat = path.stat()
    digest = hashlib.sha256()
    digest.update(str(path.resolve()).encode())
    digest.update(str(stat.st_size).encode())
    digest.update(str(stat.st_mtime_ns).encode())
    return digest.hexdigest()


def probe_video(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,duration:format=duration,size",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    stream = (payload.get("streams") or [{}])[0]
    fmt = payload.get("format") or {}
    duration = stream.get("duration") or fmt.get("duration") or 0
    return {
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "frame_rate": stream.get("r_frame_rate") or "0/0",
        "duration_sec": float(duration),
        "size_bytes": int(fmt.get("size") or path.stat().st_size),
    }


def extract_video_frame(video: Path, seconds: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0.0, seconds):.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            "-y",
            str(output),
        ],
        check=True,
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg did not create a frame at {seconds:.3f}s")


def make_contact_sheet(
    images: list[Path],
    labels: list[str],
    output: Path,
    columns: int = 4,
    thumb_width: int = 320,
) -> None:
    if not images:
        raise ValueError("Cannot build a contact sheet without images")
    first = Image.open(images[0]).convert("RGB")
    thumb_height = max(1, round(thumb_width * first.height / first.width))
    label_height = 34
    rows = (len(images) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), "#15181d")
    font = ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)
    for index, image_path in enumerate(images):
        image = Image.open(image_path).convert("RGB")
        image.thumbnail((thumb_width, thumb_height))
        x = (index % columns) * thumb_width
        y = (index // columns) * (thumb_height + label_height)
        canvas.paste(image, (x, y))
        draw.text((x + 8, y + thumb_height + 9), labels[index], fill="white", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=92)
