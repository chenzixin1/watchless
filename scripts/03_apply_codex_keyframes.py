#!/usr/bin/env python3
"""Record Codex's direct visual choice for every scene keyframe."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from video_notes_common import emit_progress, format_timestamp, make_contact_sheet, read_json, write_json


def apply_selections(manifest_path: Path, selections: dict[str, int] | None = None) -> dict:
    manifest = read_json(manifest_path)
    scenes = manifest.get("scenes") or []
    selections = selections or {}
    unknown = set(selections) - {str(scene["id"]) for scene in scenes}
    if unknown:
        raise ValueError(f"Unknown scene ids: {sorted(unknown)}")

    for scene in scenes:
        paths = [Path(value) for value in scene.get("candidate_paths") or []]
        times = scene.get("candidate_timestamps_sec") or []
        if not paths or len(paths) != len(times):
            raise ValueError(f"Scene {scene['id']} has invalid candidates")
        default_index = int(scene.get("preferred_candidate") or (len(paths) // 2 + 1))
        selected_index = int(selections.get(str(scene["id"]), default_index))
        if not 1 <= selected_index <= len(paths):
            raise ValueError(f"Scene {scene['id']} candidate {selected_index} is out of range")
        source = paths[selected_index - 1]
        seconds = float(times[selected_index - 1])
        suffix = source.suffix.lower() if source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} else ".jpg"
        destination = manifest_path.parent / "keyframes" / (
            f"scene_{int(scene['id']):03d}_{format_timestamp(seconds).replace(':', '-')}{suffix}"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        scene["frame_timestamp_sec"] = seconds
        scene["frame_path"] = str(destination.resolve())
        scene["selected_candidate"] = selected_index
        scene["selection_method"] = "codex_visual_review"

    overview = manifest_path.parent.parent / "verify" / "selected-keyframes.jpg"
    make_contact_sheet(
        [Path(scene["frame_path"]) for scene in scenes],
        [f"{int(scene['id']):02d} {format_timestamp(scene['frame_timestamp_sec'])}" for scene in scenes],
        overview,
        columns=5,
    )
    manifest["keyframe_review"] = {"status": "complete", "reviewer": "Codex"}
    write_json(manifest_path, manifest)
    emit_progress("keyframe_review", "complete", completed=len(scenes), total=len(scenes), image=str(overview))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--selections", type=Path, help='JSON object such as {"1": 2, "2": 5}')
    parser.add_argument("--accept-defaults", action="store_true")
    args = parser.parse_args()
    if bool(args.selections) == bool(args.accept_defaults):
        parser.error("choose exactly one of --selections or --accept-defaults")
    selections = read_json(args.selections.resolve()) if args.selections else {}
    result = apply_selections(args.manifest.resolve(), selections)
    print(json.dumps(result["keyframe_review"], ensure_ascii=False))


if __name__ == "__main__":
    main()
