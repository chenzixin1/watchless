import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "03_build_scene_manifest.py"


def load_module():
    spec = importlib.util.spec_from_file_location("scene_manifest", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_editorial_scenes_is_chronological_and_complete():
    module = load_module()
    cues = [
        {"start_sec": float(i * 20), "end_sec": float(i * 20 + 8), "text": f"内容{i}。"}
        for i in range(12)
    ]
    scenes = module.build_editorial_scene_records(cues, target_seconds=80)
    assert scenes[0]["start_sec"] == 0.0
    assert scenes[-1]["end_sec"] == 228.0
    assert [scene["id"] for scene in scenes] == list(range(1, len(scenes) + 1))
    assert "".join(scene["transcript_text"] for scene in scenes) == "".join(f"内容{i}。" for i in range(12))


def test_validate_manifest_rejects_frame_outside_scene():
    module = load_module()
    manifest = {
        "schema_version": 1,
        "scenes": [
            {
                "id": 1,
                "start_sec": 10.0,
                "end_sec": 20.0,
                "frame_timestamp_sec": 25.0,
                "frame_path": "/tmp/frame.png",
                "transcript_text": "内容",
            }
        ],
    }
    errors = module.validate_manifest(manifest, check_files=False)
    assert any("outside scene" in error for error in errors)


def test_speaker_labels_preserve_first_seen_order():
    module = load_module()
    assert module.speaker_labels(
        "说话人2: 提问。说话人1：回答。说话人2: 追问。"
    ) == ["说话人2", "说话人1"]


def test_four_video_modes_have_no_time_defaults():
    module = load_module()
    assert module.SUPPORTED_MODES == {"slides", "explainer", "conversation", "demo"}
    assert not hasattr(module, "MODE_DEFAULT_SECONDS")


def test_candidate_positions_are_mode_specific():
    module = load_module()
    assert len(module.candidate_positions("conversation", ["speaker"])) == 5
    assert len(module.candidate_positions("conversation", ["speaker"], "studio")) == 3
    assert len(module.candidate_positions("conversation", ["speaker", "evidence"], "news")) == 8
    assert len(module.candidate_positions("conversation", ["speaker", "broll"], "edited")) == 9
    assert module.candidate_positions("demo", ["screen-state"])[-1] == 0.97
    assert len(module.candidate_positions("explainer", ["dense-visual"])) == 9


def test_news_conversation_adds_local_candidates_for_spoken_evidence():
    module = load_module()
    scene = {"start_sec": 0.0, "end_sec": 60.0}
    cues = [
        {"start_sec": 10.0, "end_sec": 12.0, "text": "我们来看这张芯片需求图表。"},
        {"start_sec": 30.0, "end_sec": 34.0, "text": "这里继续讨论长期需求。"},
    ]
    candidates = module.semantic_candidate_times(
        scene,
        cues,
        "conversation",
        ["speaker", "evidence"],
        conversation_profile="news",
    )
    reasons = [reason for _, reason in candidates]
    assert any(reason.startswith("evidence trigger") for reason in reasons)
    assert any(10.0 <= seconds <= 13.5 for seconds, reason in candidates if reason.startswith("evidence trigger"))


def test_studio_conversation_does_not_add_evidence_candidates_by_default():
    module = load_module()
    candidates = module.semantic_candidate_times(
        {"start_sec": 0.0, "end_sec": 60.0},
        [{"start_sec": 10.0, "end_sec": 12.0, "text": "请看这个图表。"}],
        "conversation",
        ["speaker"],
        conversation_profile="studio",
    )
    assert len(candidates) == 3
    assert all(reason == "distributed scene coverage" for _, reason in candidates)


def test_candidates_are_clamped_before_decodable_media_end():
    module = load_module()
    candidates = module.semantic_candidate_times(
        {"start_sec": 90.0, "end_sec": 100.8},
        [],
        "conversation",
        ["speaker"],
        conversation_profile="news",
        video_duration=100.0,
    )
    assert max(seconds for seconds, _ in candidates) <= 99.8


def test_semantic_boundaries_cover_every_cue_once():
    module = load_module()
    cues = [
        {"start_sec": i * 10.0, "end_sec": i * 10.0 + 8.0, "text": f"句子{i}。"}
        for i in range(5)
    ]
    scenes = module.build_boundary_scene_records(
        cues,
        {
            "scenes": [
                {"end_cue": 2, "reason": "第一个论点结束"},
                {"end_cue": 5, "reason": "第二个论点结束"},
            ]
        },
    )
    assert [scene["end_cue"] for scene in scenes] == [2, 5]
    assert "".join(scene["transcript_text"] for scene in scenes) == "".join(
        cue["text"] for cue in cues
    )


def test_word_boundary_snaps_forward_to_complete_utterance():
    module = load_module()
    cues = [
        {"start_sec": 0.0, "end_sec": 10.0, "text": "第一句。"},
        {"start_sec": 10.5, "end_sec": 20.0, "text": "第二句。"},
        {"start_sec": 20.5, "end_sec": 30.0, "text": "第三句。"},
    ]
    scenes = module.build_boundary_scene_records(
        cues,
        {
            "scenes": [
                {"end_sec": 15.0, "reason": "word boundary inside second utterance"},
                {"end_sec": 30.0, "reason": "end"},
            ]
        },
    )
    assert scenes[0]["end_cue"] == 2
    assert scenes[0]["boundary_actual_sec"] == 20.0
    assert scenes[1]["start_cue"] == 3
