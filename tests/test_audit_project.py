import importlib.util
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "06_audit_project.py"


def load_module():
    spec = importlib.util.spec_from_file_location("audit_project", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_complete_project(tmp_path):
    project = tmp_path / "project"
    work = project / "work"
    notes = work / "codex-notes"
    notes.mkdir(parents=True)
    transcript = work / "transcript.txt"
    transcript.write_text("[0.000s - 10.000s] 完整内容。\n", encoding="utf-8")
    frame = work / "frame.jpg"
    Image.new("RGB", (32, 18), "blue").save(frame)
    manifest = {
        "source": {"duration_sec": 10.0},
        "mode": {"selected": "conversation", "conversation_profile": "news"},
        "transcript": {"path": str(transcript)},
        "keyframe_review": {"status": "complete"},
        "scenes": [
            {
                "id": 1,
                "start_sec": 0.0,
                "end_sec": 10.0,
                "transcript_text": "完整内容。",
                "frame_path": str(frame),
                "candidate_paths": [str(frame)],
                "candidate_reasons": ["evidence trigger: 图表"],
            }
        ],
    }
    (work / "scene-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    (work / "speaker-map.json").write_text('{"status":"complete"}', encoding="utf-8")
    (notes / "scene_001.md").write_text("fixture", encoding="utf-8")
    return project


def test_quality_audit_checks_coverage_and_evidence_candidates(tmp_path):
    module = load_module()
    project = build_complete_project(tmp_path)
    module.record_usage(
        project,
        stage="notes",
        model="test-model",
        input_tokens=100,
        output_tokens=20,
        cost_usd=0.01,
    )
    report = module.audit_project(project)
    assert report["status"] == "pass"
    assert report["transcript"]["exact_ordered_coverage"] is True
    assert report["evidence_trigger_candidates"] == 1
    assert report["token_usage"]["total_tokens"] == 120
    assert (project / "verify" / "quality-audit.md").is_file()


def test_usage_ledger_calculates_cost_only_from_explicit_rates(tmp_path):
    module = load_module()
    ledger = module.record_usage(
        tmp_path,
        stage="keyframe-review",
        model="test-model",
        input_tokens=1_000_000,
        cached_input_tokens=200_000,
        output_tokens=100_000,
        input_rate_per_million=2.0,
        cached_input_rate_per_million=0.5,
        output_rate_per_million=8.0,
    )
    assert ledger["totals"]["total_tokens"] == 1_100_000
    assert ledger["totals"]["cost_usd"] == 2.5
