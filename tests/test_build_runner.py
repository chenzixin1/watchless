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
