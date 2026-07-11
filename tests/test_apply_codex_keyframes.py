import importlib.util
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "03_apply_codex_keyframes.py"


def load_module():
    spec = importlib.util.spec_from_file_location("apply_codex_keyframes", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_apply_selections_records_codex_choice(tmp_path):
    module = load_module()
    work = tmp_path / "project" / "work"
    candidates = work / "candidates" / "scene_001"
    candidates.mkdir(parents=True)
    paths = []
    for index, color in enumerate(("red", "blue", "green"), start=1):
        path = candidates / f"candidate_{index}.jpg"
        Image.new("RGB", (80, 45), color).save(path)
        paths.append(str(path.resolve()))
    manifest = work / "scene-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "scenes": [
                    {
                        "id": 1,
                        "candidate_paths": paths,
                        "candidate_timestamps_sec": [10.0, 20.0, 30.0],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = module.apply_selections(manifest, {"1": 3})

    scene = result["scenes"][0]
    assert scene["selected_candidate"] == 3
    assert scene["frame_timestamp_sec"] == 30.0
    assert scene["selection_method"] == "codex_visual_review"
    assert Path(scene["frame_path"]).is_file()
    assert (tmp_path / "project" / "verify" / "selected-keyframes.jpg").is_file()
