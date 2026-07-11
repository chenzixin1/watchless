#!/usr/bin/env python3
"""Acquire a local or YouTube source without persisting browser cookies."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from video_notes_common import (
    emit_progress,
    extract_video_id,
    normalize_display_text,
    probe_video,
    read_json,
    source_fingerprint,
    write_json,
)


DEFAULT_LANGUAGES = "zh-Hans,zh-CN,zh,zh-Hant,zh-TW,en,en-US,en-GB"


def preferred_languages(language: str) -> str:
    if language.lower().startswith("zh"):
        return DEFAULT_LANGUAGES
    return f"{language},{DEFAULT_LANGUAGES}"


def build_ytdlp_attempts(
    url: str,
    output_template: Path,
    max_height: int,
    language: str,
    cookies_from_browser: str | None,
) -> list[list[str]]:
    args = [
        "yt-dlp",
        "--no-playlist",
        "--js-runtimes",
        "node",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        preferred_languages(language),
        "--convert-subs",
        "srt",
        "--merge-output-format",
        "mp4",
        "--format",
        f"bv*[height<={max_height}]+ba/b[height<={max_height}]",
        "--output",
        str(output_template),
    ]
    attempts = [args + [url]]
    if cookies_from_browser:
        attempts.append(args + ["--cookies-from-browser", cookies_from_browser, url])
    return attempts


def classify_ytdlp_error(stderr: str) -> str:
    normalized = stderr.lower()
    if "sign in" in normalized or "not a bot" in normalized or "login required" in normalized:
        return "login_required"
    if "429" in normalized or "too many requests" in normalized or "rate limit" in normalized:
        return "rate_limited"
    if "private video" in normalized or "video unavailable" in normalized or "members-only" in normalized:
        return "unavailable"
    if "requested format is not available" in normalized or "only images are available" in normalized:
        return "no_playable_video"
    return "download_failed"


def _media_candidates(source_dir: Path) -> list[Path]:
    extensions = {".mp4", ".mkv", ".mov", ".webm"}
    return sorted(
        (path for path in source_dir.iterdir() if path.is_file() and path.suffix.lower() in extensions),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _subtitle_candidates(video: Path, language: str = "zh") -> list[Path]:
    candidates = list(video.parent.glob(f"{video.stem}*.srt")) + list(video.parent.glob(f"{video.stem}*.vtt"))
    preferred = preferred_languages(language).lower().split(",")

    def rank(path: Path) -> tuple[int, int, str]:
        name = path.name.lower()
        language_rank = next((index for index, value in enumerate(preferred) if f".{value}." in name), len(preferred))
        return language_rank, int("auto" in name), name

    return sorted(candidates, key=rank)


def acquire(
    source: str,
    work_dir: Path,
    max_height: int = 1080,
    language: str = "zh",
    cookies_from_browser: str | None = "chrome",
) -> dict[str, Any]:
    local = Path(source).expanduser()
    source_dir = work_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    cache_path = work_dir / "acquisition.json"
    if cache_path.is_file():
        cached = read_json(cache_path)
        cached_video = Path(cached.get("local_video") or "")
        if not cached_video.is_file() and cached_video.name:
            cached_video = source_dir / cached_video.name
        if cached.get("input") == source and cached_video.is_file():
            cached["local_video"] = str(cached_video.resolve())
            subtitles = _subtitle_candidates(cached_video, language)
            cached["subtitle"] = str(subtitles[0].resolve()) if subtitles else None
            cached["fingerprint"] = source_fingerprint(cached_video)
            write_json(cache_path, cached)
            emit_progress("download", "cached", completed=1, total=1, output=str(cached_video))
            return cached
    if local.is_file():
        video = local.resolve()
        metadata = probe_video(video)
        result = {
            "input": source,
            "video_id": None,
            "title": video.stem,
            "local_video": str(video),
            "subtitle": next((str(path.resolve()) for path in _subtitle_candidates(video, language)), None),
            "download_method": "local",
            "fingerprint": source_fingerprint(video),
            **metadata,
        }
        write_json(work_dir / "acquisition.json", result)
        return result

    video_id = extract_video_id(source)
    if not video_id:
        raise ValueError("Input is neither a local video nor a supported YouTube URL")

    template = source_dir / "%(title)s-%(id)s.%(ext)s"
    errors: list[tuple[str, str]] = []
    for index, command in enumerate(
        build_ytdlp_attempts(source, template, max_height, language, cookies_from_browser), start=1
    ):
        emit_progress("download", "running", completed=index - 1, total=2, attempt=index)
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode == 0 and _media_candidates(source_dir):
            break
        errors.append((classify_ytdlp_error(completed.stderr), completed.stderr[-2000:]))
    else:
        code = errors[-1][0] if errors else "download_failed"
        detail = errors[-1][1] if errors else "yt-dlp did not return an error message"
        raise RuntimeError(f"YOUTUBE_{code.upper()}: {detail}")

    video = _media_candidates(source_dir)[0]
    info_path = next(iter(source_dir.glob(f"*{video_id}*.info.json")), None)
    info: dict[str, Any] = {}
    if info_path:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    metadata = probe_video(video)
    subtitles = _subtitle_candidates(video, language)
    result = {
        "input": source,
        "video_id": video_id,
        "title": normalize_display_text(info.get("title") or video.stem),
        "local_video": str(video.resolve()),
        "subtitle": str(subtitles[0].resolve()) if subtitles else None,
        "info_json": str(info_path.resolve()) if info_path else None,
        "download_method": "yt-dlp-browser" if errors else "yt-dlp-anonymous",
        "fingerprint": source_fingerprint(video),
        **metadata,
    }
    write_json(work_dir / "acquisition.json", result)
    emit_progress("download", "complete", completed=2, total=2, output=str(video))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--max-height", type=int, default=1080)
    parser.add_argument("--lang", default="zh")
    parser.add_argument("--cookies-from-browser", default="chrome")
    parser.add_argument("--no-browser-cookies", action="store_true")
    args = parser.parse_args()
    result = acquire(
        args.source,
        args.work_dir.resolve(),
        max_height=args.max_height,
        language=args.lang,
        cookies_from_browser=None if args.no_browser_cookies else args.cookies_from_browser,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
