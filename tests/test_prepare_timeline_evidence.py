import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "03_prepare_timeline_evidence.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_timeline_evidence", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_timeline_modes_use_semantic_rules_not_fixed_durations():
    module = load_module()
    assert set(module.MODE_BOUNDARY_RULES) == {"explainer", "conversation", "demo"}
    assert all("second" not in rule.lower() for rule in module.MODE_BOUNDARY_RULES.values())


def test_chaptered_conversation_writes_non_binding_chapter_hints(tmp_path, monkeypatch):
    module = load_module()
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fixture")
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("[0.000s - 10.000s] 完整问答。\n", encoding="utf-8")
    packed = tmp_path / "takes_packed.md"
    packed.write_text("packed", encoding="utf-8")
    transcript_json = tmp_path / "words.json"
    transcript_json.write_text("{}", encoding="utf-8")
    video_use = tmp_path / "video-use"
    helper = video_use / "helpers" / "timeline_view.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("# fixture\n", encoding="utf-8")
    monkeypatch.setattr(module, "probe_video", lambda _: {"duration_sec": 10.0})

    evidence = module.prepare_timeline(
        video,
        transcript,
        "conversation",
        tmp_path / "work",
        packed_transcript=packed,
        transcript_json=transcript_json,
        video_use_dir=video_use,
        conversation_profile="chaptered",
        source_chapters=[{"start_sec": 0.0, "end_sec": 10.0, "title": "主题一"}],
    )

    assert evidence["chapter_count"] == 1
    assert Path(evidence["chapter_hints"]).is_file()
    worksheet = Path(evidence["worksheet"]).read_text(encoding="utf-8")
    assert "coarse topic proposals" in worksheet
    assert "complete questions" in worksheet
