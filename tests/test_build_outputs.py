import importlib.util
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "05_build_outputs.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_outputs", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_markdown_keeps_one_image_and_text_block_per_scene(tmp_path):
    module = load_module()
    image = tmp_path / "frame.png"
    Image.new("RGB", (320, 180), "black").save(image)
    manifest = {
        "source": {"title": "测试视频"},
        "scenes": [
            {
                "id": 1,
                "start_sec": 0.0,
                "end_sec": 60.0,
                "frame_path": str(image),
                "transcript_text": "原始内容。",
            }
        ],
    }
    notes = {
        1: {
            "title": "第一节",
            "light_plus": "忠实打磨稿。",
            "explainer": "完整解说稿。",
        }
    }
    light, explainer = module.build_markdown_documents(manifest, notes, "keyframes")
    assert light.count("![") == 1
    assert explainer.count("![") == 1
    assert "忠实打磨稿。" in light
    assert "忠实打磨稿。" in explainer
    assert "完整解说稿。" in explainer
    assert "### 完整内容" in explainer
    assert "### 画面说明" in explainer
    assert "00:00-01:00" in explainer
