import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "video_notes_common.py"


def load_module():
    spec = importlib.util.spec_from_file_location("video_notes_common", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_video_id_supports_common_youtube_urls():
    module = load_module()
    expected = "tzEWYNQmnmc"
    assert module.extract_video_id(f"https://www.youtube.com/watch?v={expected}") == expected
    assert module.extract_video_id(f"https://youtu.be/{expected}") == expected
    assert module.extract_video_id(f"https://www.youtube.com/shorts/{expected}") == expected


def test_safe_slug_keeps_chinese_and_removes_path_characters():
    module = load_module()
    assert module.safe_slug("AI/存储：超级周期? ") == "AI-存储-超级周期"
    assert module.safe_slug("\u2060Why OpenAI") == "Why-OpenAI"
    assert module.normalize_display_text("\u2060Why OpenAI") == "Why OpenAI"


def test_parse_srt_cues_preserves_timing_and_text(tmp_path):
    module = load_module()
    srt = tmp_path / "sample.srt"
    srt.write_text(
        "1\n00:00:01,200 --> 00:00:03,500\n第一句\n\n"
        "2\n00:00:04,000 --> 00:00:06,000\n第二句\n",
        encoding="utf-8",
    )
    cues = module.parse_transcript_file(srt)
    assert cues == [
        {"start_sec": 1.2, "end_sec": 3.5, "text": "第一句"},
        {"start_sec": 4.0, "end_sec": 6.0, "text": "第二句"},
    ]


def test_group_cues_covers_every_cue_once():
    module = load_module()
    cues = [
        {"start_sec": float(i * 30), "end_sec": float(i * 30 + 10), "text": f"句子{i}。"}
        for i in range(8)
    ]
    scenes = module.group_cues(cues, target_seconds=90)
    flattened = [text for scene in scenes for text in scene["cue_texts"]]
    assert flattened == [f"句子{i}。" for i in range(8)]
    assert scenes[0]["start_sec"] == 0.0
    assert scenes[-1]["end_sec"] == 220.0
