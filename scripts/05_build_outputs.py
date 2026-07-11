#!/usr/bin/env python3
"""Build light-plus and visual explainer share artifacts from scene notes."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from video_notes_common import emit_progress, format_timestamp, make_contact_sheet, read_json


NOTE_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _scene_time(scene: dict[str, Any]) -> str:
    include_hours = float(scene["end_sec"]) >= 3600
    return (
        f"{format_timestamp(scene['start_sec'], include_hours=include_hours)}-"
        f"{format_timestamp(scene['end_sec'], include_hours=include_hours)}"
    )


def build_markdown_documents(
    manifest: dict[str, Any], notes: dict[int, dict[str, str]], image_dir_name: str
) -> tuple[str, str]:
    title = manifest.get("source", {}).get("title") or "Video Notes"
    light_parts = [f"# {title} - Light Plus", ""]
    explainer_parts = [f"# {title} - 图文解说", "", "> 一张关键画面对应一段完整解说，按原视频时间推进。", ""]
    for scene in manifest.get("scenes") or []:
        scene_id = int(scene["id"])
        note = notes.get(scene_id)
        if not note:
            raise ValueError(f"Missing Codex note for scene {scene_id}")
        frame_name = Path(scene["frame_path"]).name
        image_ref = f"{image_dir_name}/{frame_name}"
        heading = note.get("title") or f"场景 {scene_id}"
        time_range = _scene_time(scene)
        light_parts.extend(
            [
                f"## {scene_id:02d}. {heading}（{time_range}）",
                "",
                f"![场景 {scene_id}](<{image_ref}>)",
                "",
                note["light_plus"].strip(),
                "",
            ]
        )
        explainer_parts.extend(
            [
                f"## {scene_id:02d}. {heading}（{time_range}）",
                "",
                f"![场景 {scene_id}](<{image_ref}>)",
                "",
                "### 完整内容",
                "",
                note["light_plus"].strip(),
                "",
                "### 画面说明",
                "",
                note["explainer"].strip(),
                "",
            ]
        )
    return "\n".join(light_parts).rstrip() + "\n", "\n".join(explainer_parts).rstrip() + "\n"


def parse_note(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8").strip()
    matches = list(NOTE_SECTION_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip().lower()] = text[match.end() : end].strip()
    title = sections.get("标题") or sections.get("title") or path.stem
    light = sections.get("light-plus") or sections.get("轻量打磨稿") or sections.get("light plus")
    explainer = sections.get("visual explainer") or sections.get("图文解说") or sections.get("详细解说")
    if not light or not explainer:
        raise ValueError(f"Note {path} must contain Light-plus and Visual explainer sections")
    return {"title": title, "light_plus": light, "explainer": explainer}


def load_notes(notes_dir: Path) -> dict[int, dict[str, str]]:
    notes: dict[int, dict[str, str]] = {}
    for path in notes_dir.glob("scene_*.md"):
        match = re.search(r"scene_(\d+)", path.stem)
        if match:
            notes[int(match.group(1))] = parse_note(path)
    return notes


def _style_markdown(text: str) -> str:
    style = """<style>
body { max-width: 1100px; margin: 0 auto; padding: 48px 64px; font-family: 'Songti SC','STSong',serif; line-height: 1.85; color: #202832; }
h1,h2,h3 { font-family: 'PingFang SC','Hiragino Sans GB',sans-serif; line-height: 1.35; }
h2 { margin-top: 2.5em; border-left: 5px solid #e66b23; padding-left: .7em; break-after: avoid; }
h3 { margin-top: 1.5em; margin-bottom: .5em; color: #46515d; break-after: avoid; }
img { display:block; width:100%; height:auto; margin: 1em auto; box-shadow: 0 8px 28px rgba(0,0,0,.16); break-inside: avoid; }
p { font-size: 1.05rem; }
@media print { body { max-width: none; padding: 0; } h2 { break-before: page; } h2, h3, img { break-inside: avoid; } }
</style>"""
    return style + "\n\n" + text


def _find_chrome() -> Path | None:
    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    ]
    return next((path for path in candidates if path.is_file()), None)


def build_share(manifest_path: Path, notes_dir: Path, output_root: Path, no_zip: bool = False) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    notes = load_notes(notes_dir)
    scene_ids = {int(scene["id"]) for scene in manifest.get("scenes") or []}
    if set(notes) != scene_ids:
        missing = sorted(scene_ids - set(notes))
        extra = sorted(set(notes) - scene_ids)
        raise ValueError(f"Codex note coverage mismatch: missing={missing}, extra={extra}")

    share = output_root / "share"
    if share.exists():
        shutil.rmtree(share)
    keyframes = share / "keyframes"
    sources = share / "source-materials"
    keyframes.mkdir(parents=True)
    sources.mkdir(parents=True)
    for scene in manifest["scenes"]:
        shutil.copy2(scene["frame_path"], keyframes / Path(scene["frame_path"]).name)

    title = manifest.get("source", {}).get("title") or "video-notes"
    safe_name = re.sub(r"[\\/:*?\"<>|]+", "-", title).strip() or "video-notes"
    light_text, explainer_text = build_markdown_documents(manifest, notes, "keyframes")
    light_path = share / f"{safe_name}-light-polished.md"
    explainer_path = share / f"{safe_name}-visual-explainer.md"
    light_path.write_text(light_text, encoding="utf-8")
    explainer_path.write_text(_style_markdown(explainer_text), encoding="utf-8")

    transcript = Path(manifest["transcript"]["path"])
    shutil.copy2(transcript, sources / transcript.name)
    html_path = share / f"{safe_name}-visual-explainer.html"
    subprocess.run(
        ["pandoc", str(explainer_path), "--standalone", "--metadata", f"pagetitle={title}", "-o", str(html_path)],
        check=True,
    )
    emit_progress("html", "complete", output=str(html_path))

    pdf_path = share / f"{safe_name}-visual-explainer.pdf"
    chrome = _find_chrome()
    if not chrome:
        raise RuntimeError("Google Chrome or Chromium is required for PDF output")
    subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--allow-file-access-from-files",
            f"--print-to-pdf={pdf_path}",
            "--no-pdf-header-footer",
            html_path.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    emit_progress("pdf", "complete", output=str(pdf_path))

    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise RuntimeError("Poppler pdftoppm is required for PDF visual verification")
    pdf_pages = output_root / "verify" / "pdf-pages"
    if pdf_pages.exists():
        shutil.rmtree(pdf_pages)
    pdf_pages.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [pdftoppm, "-png", "-r", "90", str(pdf_path), str(pdf_pages / "page")],
        check=True,
        capture_output=True,
    )
    rendered_pages = sorted(pdf_pages.glob("page-*.png"))
    if not rendered_pages:
        raise RuntimeError("PDF rendering produced no pages")
    pdf_overview = output_root / "verify" / "pdf-pages-contact-sheet.jpg"
    make_contact_sheet(
        rendered_pages,
        [f"page {index}" for index in range(1, len(rendered_pages) + 1)],
        pdf_overview,
        columns=4,
        thumb_width=240,
    )
    emit_progress("pdf_verify", "complete", image=str(pdf_overview), pages=len(rendered_pages))

    zip_path = output_root / f"{safe_name}-video-notes.zip"
    if not no_zip:
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for path in share.rglob("*"):
                if path.is_file():
                    archive.write(path, Path("share") / path.relative_to(share))

    return {
        "light_markdown": str(light_path),
        "explainer_markdown": str(explainer_path),
        "html": str(html_path),
        "pdf": str(pdf_path),
        "zip": str(zip_path) if not no_zip else None,
        "images": len(manifest["scenes"]),
        "pdf_pages": len(rendered_pages),
        "pdf_overview": str(pdf_overview),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--notes-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--no-zip", action="store_true")
    args = parser.parse_args()
    result = build_share(
        args.manifest.resolve(), args.notes_dir.resolve(), args.output_root.resolve(), no_zip=args.no_zip
    )
    print(result)


if __name__ == "__main__":
    main()
