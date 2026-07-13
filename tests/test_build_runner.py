import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "00_build_video_notes.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_video_notes", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_relocate_acquisition_paths_after_project_rename(tmp_path):
    module = load_module()
    old = tmp_path / "youtube-id" / "work" / "source"
    new_work = tmp_path / "title-id" / "work"
    new_source = new_work / "source"
    new_source.mkdir(parents=True)
    video = new_source / "title-id.mp4"
    subtitle = new_source / "title-id.zh-Hans.srt"
    info = new_source / "title-id.info.json"
    for path in (video, subtitle, info):
        path.write_text("fixture", encoding="utf-8")

    acquisition = {
        "local_video": str(old / video.name),
        "subtitle": str(old / subtitle.name),
        "info_json": str(old / info.name),
    }
    repaired = module.relocate_acquisition_paths(acquisition, new_work)

    assert repaired["local_video"] == str(video.resolve())
    assert repaired["subtitle"] == str(subtitle.resolve())
    assert repaired["info_json"] == str(info.resolve())


def test_route_decision_normalizes_alias_and_preserves_strategies(tmp_path):
    module = load_module()
    project = tmp_path / "project"
    decision = module.save_route_decision(
        project,
        "presentation",
        strategies=["slide-state"],
        reasons=["stable slide region"],
    )
    assert decision["selected"] == "slides"
    assert decision["visual_strategies"] == ["slide-state"]
    assert (project / "work" / "route-decision.json").is_file()


def test_conversation_route_records_profile(tmp_path):
    module = load_module()
    decision = module.save_route_decision(
        tmp_path,
        "conversation",
        strategies=["speaker", "evidence"],
        conversation_profile="news",
    )
    assert decision["conversation_profile"] == "news"


def test_non_conversation_route_rejects_conversation_profile(tmp_path):
    module = load_module()
    try:
        module.save_route_decision(tmp_path, "explainer", conversation_profile="news")
    except ValueError as exc:
        assert "only valid" in str(exc)
    else:
        raise AssertionError("non-conversation routes must reject conversation profiles")


def test_source_chapters_are_normalized(tmp_path):
    module = load_module()
    info = tmp_path / "source.info.json"
    info.write_text(
        '{"chapters":[{"start_time":0,"end_time":75,"title":"开场"},'
        '{"start_time":75,"end_time":75,"title":"无效"}]}',
        encoding="utf-8",
    )
    assert module.source_chapters({"info_json": str(info)}) == [
        {"start_sec": 0.0, "end_sec": 75.0, "title": "开场"}
    ]


def test_auto_route_requires_confirmed_decision(tmp_path):
    module = load_module()
    args = type(
        "Args",
        (),
        {"visual_strategy": None, "mode_reason": None, "conversation_profile": None},
    )()
    try:
        module.resolve_route(tmp_path, "auto", args)
    except RuntimeError as exc:
        assert "requires Codex confirmation" in str(exc)
    else:
        raise AssertionError("auto routing should require an explicit Codex-confirmed route")
