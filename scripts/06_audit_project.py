#!/usr/bin/env python3
"""Audit output completeness and keep an explicit token/cost ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from video_notes_common import parse_transcript_file, read_json, write_json


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_project(project: Path) -> dict[str, Any]:
    project = project.resolve()
    work = project / "work"
    manifest = read_json(work / "scene-manifest.json")
    scenes = manifest.get("scenes") or []
    transcript_path = Path(manifest["transcript"]["path"])
    cues = parse_transcript_file(transcript_path)
    source_text = _compact_text("".join(str(cue.get("text") or "") for cue in cues))
    scene_text = _compact_text("".join(str(scene.get("transcript_text") or "") for scene in scenes))
    length_ratio = min(len(source_text), len(scene_text)) / max(1, max(len(source_text), len(scene_text)))

    notes_dir = work / "codex-notes"
    note_paths = sorted(notes_dir.glob("scene_*.md")) if notes_dir.is_dir() else []
    selected_paths = [Path(scene["frame_path"]) for scene in scenes if scene.get("frame_path")]
    existing_selected = [path for path in selected_paths if path.is_file()]
    hashes = [_file_sha256(path) for path in existing_selected]
    duplicate_selected = len(hashes) - len(set(hashes))
    candidate_count = sum(len(scene.get("candidate_paths") or []) for scene in scenes)
    evidence_candidates = sum(
        1
        for scene in scenes
        for reason in scene.get("candidate_reasons") or []
        if str(reason).startswith("evidence trigger")
    )
    mode = manifest.get("mode") or {}
    speaker_map_path = work / "speaker-map.json"
    speaker_status = read_json(speaker_map_path).get("status") if speaker_map_path.is_file() else None
    token_path = work / "token-usage.json"
    token_ledger = read_json(token_path) if token_path.is_file() else {"entries": [], "totals": {}}

    warnings = []
    if source_text != scene_text:
        warnings.append("Scene transcript does not exactly cover the source transcript in order")
    if len(note_paths) != len(scenes):
        warnings.append(f"Codex note coverage mismatch: expected {len(scenes)}, found {len(note_paths)}")
    if len(existing_selected) != len(scenes):
        warnings.append("One or more selected frame files are missing")
    if duplicate_selected:
        warnings.append(f"Found {duplicate_selected} byte-identical selected frame(s)")
    if mode.get("selected") == "conversation" and speaker_status != "complete":
        warnings.append("Conversation speaker identity pass is incomplete")
    if (manifest.get("keyframe_review") or {}).get("status") != "complete":
        warnings.append("Codex keyframe review is incomplete")
    if not token_ledger.get("entries"):
        warnings.append("No model token usage has been recorded; do not estimate or fabricate unavailable counts")

    report = {
        "status": "pass" if not warnings else "needs_review",
        "mode": mode.get("selected"),
        "conversation_profile": mode.get("conversation_profile"),
        "duration_sec": (manifest.get("source") or {}).get("duration_sec"),
        "transcript": {
            "cue_count": len(cues),
            "source_characters": len(source_text),
            "scene_characters": len(scene_text),
            "exact_ordered_coverage": source_text == scene_text,
            "length_ratio": round(length_ratio, 6),
        },
        "scenes": len(scenes),
        "notes": len(note_paths),
        "selected_frames": len(existing_selected),
        "candidate_frames": candidate_count,
        "evidence_trigger_candidates": evidence_candidates,
        "byte_identical_selected_frames": duplicate_selected,
        "speaker_map_status": speaker_status,
        "token_usage": token_ledger.get("totals") or {},
        "warnings": warnings,
    }
    verify = project / "verify"
    write_json(verify / "quality-audit.json", report)
    lines = [
        "# Video Notes Quality Audit",
        "",
        f"- Status: {report['status']}",
        f"- Mode: {report['mode']}",
        f"- Conversation profile: {report['conversation_profile'] or 'n/a'}",
        f"- Transcript exact ordered coverage: {report['transcript']['exact_ordered_coverage']}",
        f"- Scenes / notes / selected frames: {len(scenes)} / {len(note_paths)} / {len(existing_selected)}",
        f"- Candidate frames: {candidate_count} ({evidence_candidates} evidence-triggered)",
        f"- Byte-identical selected frames: {duplicate_selected}",
        f"- Speaker map: {speaker_status or 'n/a'}",
        f"- Recorded tokens: {(report['token_usage'] or {}).get('total_tokens', 0)}",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {warning}" for warning in warnings] or ["- None"])
    (verify / "quality-audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def record_usage(
    project: Path,
    *,
    stage: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
    cost_usd: float | None = None,
    input_rate_per_million: float | None = None,
    output_rate_per_million: float | None = None,
    cached_input_rate_per_million: float | None = None,
) -> dict[str, Any]:
    for name, value in {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens,
    }.items():
        if value < 0:
            raise ValueError(f"{name} cannot be negative")
    if cached_input_tokens > input_tokens:
        raise ValueError("cached_input_tokens cannot exceed input_tokens")
    if cost_usd is None and input_rate_per_million is not None and output_rate_per_million is not None:
        cached_rate = (
            cached_input_rate_per_million
            if cached_input_rate_per_million is not None
            else input_rate_per_million
        )
        uncached = input_tokens - cached_input_tokens
        cost_usd = (
            uncached * input_rate_per_million
            + cached_input_tokens * cached_rate
            + output_tokens * output_rate_per_million
        ) / 1_000_000
    entry = {
        "stage": stage,
        "model": model,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": round(cost_usd, 8) if cost_usd is not None else None,
        "rates_per_million": {
            "input": input_rate_per_million,
            "cached_input": cached_input_rate_per_million,
            "output": output_rate_per_million,
        },
    }
    path = project.resolve() / "work" / "token-usage.json"
    ledger = read_json(path) if path.is_file() else {"schema_version": 1, "entries": []}
    ledger.setdefault("entries", []).append(entry)
    entries = ledger["entries"]
    known_costs = [item["cost_usd"] for item in entries if item.get("cost_usd") is not None]
    ledger["totals"] = {
        "input_tokens": sum(item["input_tokens"] for item in entries),
        "cached_input_tokens": sum(item.get("cached_input_tokens", 0) for item in entries),
        "output_tokens": sum(item["output_tokens"] for item in entries),
        "total_tokens": sum(item["total_tokens"] for item in entries),
        "cost_usd": round(sum(known_costs), 8) if len(known_costs) == len(entries) else None,
        "entries": len(entries),
    }
    write_json(path, ledger)
    return ledger


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--record-usage", action="store_true")
    parser.add_argument("--stage")
    parser.add_argument("--model")
    parser.add_argument("--input-tokens", type=int)
    parser.add_argument("--output-tokens", type=int)
    parser.add_argument("--cached-input-tokens", type=int, default=0)
    parser.add_argument("--cost-usd", type=float)
    parser.add_argument("--input-rate-per-million", type=float)
    parser.add_argument("--cached-input-rate-per-million", type=float)
    parser.add_argument("--output-rate-per-million", type=float)
    args = parser.parse_args()
    if args.record_usage:
        if args.stage is None or args.model is None or args.input_tokens is None or args.output_tokens is None:
            parser.error("usage recording requires --stage, --model, --input-tokens, and --output-tokens")
        result = record_usage(
            args.project,
            stage=args.stage,
            model=args.model,
            input_tokens=args.input_tokens,
            output_tokens=args.output_tokens,
            cached_input_tokens=args.cached_input_tokens,
            cost_usd=args.cost_usd,
            input_rate_per_million=args.input_rate_per_million,
            cached_input_rate_per_million=args.cached_input_rate_per_million,
            output_rate_per_million=args.output_rate_per_million,
        )
    else:
        result = audit_project(args.project)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
