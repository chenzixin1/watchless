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
