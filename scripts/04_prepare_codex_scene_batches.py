#!/usr/bin/env python3
"""Prepare disjoint scene batches for Codex light-plus and explainer notes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from video_notes_common import format_timestamp, read_json


MODE_INSTRUCTIONS = {
    "slides": (
        "Treat the slide as primary evidence. Preserve all lecture content aligned to this slide, "
        "and describe legible titles, labels, figures, table values, and diagram relationships."
    ),
    "explainer": (
        "Preserve the scripted explanation in full. Prefer meaningful charts, animation states, "
        "interfaces, demonstrations, maps, or B-roll over a presenter face when choosing frames."
    ),
    "conversation": (
        "Preserve dialogue turns and speaker labels exactly. Keep visual captions brief unless an "
        "on-screen graphic adds information; do not turn the exchange into reported prose."
    ),
    "demo": (
        "Preserve the procedure in executable order. Describe the visible UI state, action, input, "
        "and resulting state; prefer a completed result frame over a transient cursor movement."
    ),
}

CONVERSATION_PROFILE_INSTRUCTIONS = {
    "general": "Use complete question-answer or topic units and avoid repetitive portraits.",
    "studio": "Use fewer representative speaker or group frames; the transcript carries most information.",
    "edited": "Prefer informative B-roll, documents, locations, or objects when they add evidence beyond the speaker shot.",
    "news": "Inspect lower thirds, tickers, data graphics, product images, and quoted figures; preserve them when they carry the claim.",
    "chaptered": "Treat official chapters as coarse hints only and preserve complete questions, answers, examples, and qualifications.",
}


def batch_text(
    scenes: list[dict],
    notes_dir: Path,
    mode: str = "explainer",
    speaker_map=None,
    visual_strategies: list[str] | None = None,
    conversation_profile: str | None = None,
) -> str:
    parts = [
        "# Video Notes Codex Batch",
        "",
        "Inspect every referenced image and use the transcript as the factual source.",
        "Write one file per scene to the notes directory. This is faithful light polish, not summarization or article rewriting.",
        f"Video mode: {mode}. {MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS['explainer'])}",
        f"Visual strategies: {', '.join(visual_strategies or []) or 'mode default'}.",
        "",
        "Light-plus rules:",
        "- Preserve the original speaking order, question-and-answer structure, reasoning path, examples, figures, caveats, disagreements, and repeated emphasis.",
        "- Only fix ASR errors, punctuation, broken sentences, obvious stutters, and meaningless filler. Do not merge distant points or reorganize the argument.",
        "- Keep first-person speech and dialogue. Do not convert it into third-person narration such as 'the host said' or 'the guest believes' unless those words are in the source.",
        "- Apply the completed speaker map and timestamped turn overrides; otherwise keep '说话人N' for unresolved identities. Never guess gender or identity beyond the recorded evidence/confidence.",
        "- Do not shorten for elegance. If the polished text loses substantive clauses from the transcript, it is wrong even when the summary is accurate.",
        "- Do not add web facts or conclusions that the speakers did not state.",
        "",
        "Visual explainer rules:",
        "- State only useful visible facts: the named speaker when established, on-screen text, charts, interfaces, demonstrations, objects, and actions.",
        "- For a plain talking-head frame, use one short factual caption. Do not invent emotion, intent, symbolism, or explain how the shot 'reinforces' the argument.",
        "- The complete spoken content belongs in Light-plus; do not replace it with visual commentary.",
        "",
        "Each file must use this exact shape:",
        "",
        "## 标题",
        "Short descriptive scene title; do not turn it into a synthesized thesis",
        "",
        "## Light-plus",
        "Near-verbatim corrected scene text following all rules above.",
        "",
        "## Visual explainer",
        "A concise factual description of useful visible information.",
        "",
        f"Notes directory: `{notes_dir.resolve()}`",
        "",
    ]
    if mode == "conversation":
        profile = conversation_profile or "general"
        parts.insert(
            6,
            f"Conversation profile: {profile}. {CONVERSATION_PROFILE_INSTRUCTIONS.get(profile, CONVERSATION_PROFILE_INSTRUCTIONS['general'])}",
        )
    if mode == "conversation" and speaker_map:
        parts.extend(
            [
                "Completed speaker identity record (null means keep the ASR label; timestamped overrides take precedence over global labels):",
                json.dumps(speaker_map, ensure_ascii=False),
                "",
            ]
        )
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
    mode = (manifest.get("mode") or {}).get("selected", "explainer")
    visual_strategies = (manifest.get("mode") or {}).get("visual_strategies") or []
    conversation_profile = (manifest.get("mode") or {}).get("conversation_profile")
    speaker_map_path = manifest_path.parent / "speaker-map.json"
    speaker_map = read_json(speaker_map_path) if speaker_map_path.is_file() else None
    if mode == "conversation" and (
        not speaker_map or speaker_map.get("status") != "complete"
    ):
        raise RuntimeError(
            "Conversation speaker identity pass is incomplete. Research source metadata, "
            "self-introductions, subtitles, frames, official episode pages, and channel history; "
            "then set work/speaker-map.json status to complete."
        )
    paths: list[Path] = []
    for offset in range(0, len(scenes), batch_size):
        batch = scenes[offset : offset + batch_size]
        path = output_dir / f"batch_{offset // batch_size + 1:02d}.md"
        path.write_text(
            batch_text(
                batch,
                notes_dir,
                mode=mode,
                speaker_map=speaker_map,
                visual_strategies=visual_strategies,
                conversation_profile=conversation_profile,
            ),
            encoding="utf-8",
        )
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
