#!/usr/bin/env python3
"""Prepare disjoint scene batches for Codex light-plus and explainer notes."""

from __future__ import annotations

import argparse
from pathlib import Path

from video_notes_common import format_timestamp, read_json


def batch_text(scenes: list[dict], notes_dir: Path) -> str:
    parts = [
        "# Video Notes Codex Batch",
        "",
        "Inspect every referenced image and use the transcript as the factual source.",
        "Write one file per scene to the notes directory. Do not omit numbers, examples, caveats, or disagreements.",
        "",
        "Each file must use this exact shape:",
        "",
        "## 标题",
        "Short scene title",
        "",
        "## Light-plus",
        "Faithful corrected scene text.",
        "",
        "## Visual explainer",
        "One complete explanatory block connecting the image to the video's argument.",
        "",
        f"Notes directory: `{notes_dir.resolve()}`",
        "",
    ]
    for scene in scenes:
        parts.extend(
            [
                f"## Scene {scene['id']}",
                "",
                f"Time: {format_timestamp(scene['start_sec'])}-{format_timestamp(scene['end_sec'])}",
                f"Image: `{scene['frame_path']}`",
                f"Output: `{notes_dir.resolve() / f'scene_{int(scene['id']):03d}.md'}`",
                "",
                "Transcript:",
                scene["transcript_text"],
                "",
                "---",
                "",
            ]
        )
    return "\n".join(parts).rstrip() + "\n"


def prepare_batches(manifest_path: Path, output_dir: Path, notes_dir: Path, batch_size: int = 6) -> list[Path]:
    manifest = read_json(manifest_path)
    scenes = manifest.get("scenes") or []
    if not scenes:
        raise ValueError("Scene manifest is empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    notes_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for offset in range(0, len(scenes), batch_size):
        batch = scenes[offset : offset + batch_size]
        path = output_dir / f"batch_{offset // batch_size + 1:02d}.md"
        path.write_text(batch_text(batch, notes_dir), encoding="utf-8")
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--notes-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=6)
    args = parser.parse_args()
    paths = prepare_batches(
        args.manifest.resolve(), args.output_dir.resolve(), args.notes_dir.resolve(), args.batch_size
    )
    print(f"batches={len(paths)}")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
