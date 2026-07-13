import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "04_prepare_codex_scene_batches.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_codex_scene_batches", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_batch_prompt_requires_near_verbatim_dialogue_and_safe_speaker_labels(tmp_path):
    module = load_module()
    prompt = module.batch_text(
        [
            {
                "id": 1,
                "start_sec": 0.0,
                "end_sec": 60.0,
                "frame_path": "/tmp/frame.jpg",
                "transcript_text": "说话人1: 原始问答。",
            }
        ],
        tmp_path,
        mode="conversation",
        speaker_map={
            "status": "complete",
            "speakers": {"说话人1": "Jason", "说话人2": None},
            "identities": {
                "Jason": {
                    "display_name": "Jason",
                    "confidence": "high",
                    "evidence": [{"source": "official description", "claim": "guest credit"}],
                }
            },
            "turn_overrides": [
                {"start_sec": 10.0, "end_sec": 12.0, "name": "主持人"}
            ],
        },
        conversation_profile="news",
    )

    assert "not summarization" in prompt
    assert "Keep first-person speech and dialogue" in prompt
    assert "otherwise keep '说话人N'" in prompt
    assert "Never guess gender or identity" in prompt
    assert "plain talking-head frame" in prompt
    assert "Preserve dialogue turns" in prompt
    assert '"说话人1": "Jason"' in prompt
    assert '"说话人2": null' in prompt
    assert '"turn_overrides"' in prompt
    assert '"confidence": "high"' in prompt
    assert "Conversation profile: news" in prompt
    assert "lower thirds, tickers, data graphics" in prompt


def test_conversation_batches_require_completed_speaker_research(tmp_path):
    module = load_module()
    manifest = tmp_path / "work" / "scene-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '{"mode":{"selected":"conversation"},"scenes":['
        '{"id":1,"start_sec":0,"end_sec":10,"frame_path":"/tmp/frame.jpg",'
        '"transcript_text":"说话人1: 测试。"}]}',
        encoding="utf-8",
    )
    (manifest.parent / "speaker-map.json").write_text(
        '{"status":"needs_identity_research","speakers":{"说话人1":null}}',
        encoding="utf-8",
    )

    try:
        module.prepare_batches(
            manifest,
            tmp_path / "batches",
            tmp_path / "notes",
        )
    except RuntimeError as exc:
        assert "speaker identity pass is incomplete" in str(exc)
    else:
        raise AssertionError("conversation batches should require completed identity research")
