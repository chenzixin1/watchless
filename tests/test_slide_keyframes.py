import importlib.util
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "02_extract_slide_keyframes.py"


def load_module():
    spec = importlib.util.spec_from_file_location("slide_keyframes", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_relative_rect_validation_and_pixel_conversion():
    module = load_module()
    relative = module.parse_relative_rect("0.1,0.2,0.9,0.8")
    assert module.pixel_rect(relative, 1000, 500) == (100, 100, 800, 300)
    with pytest.raises(ValueError):
        module.parse_relative_rect("0.9,0.2,0.1,0.8")


def test_ssim_change_times_detects_structural_change():
    module = load_module()
    white = np.full((32, 32), 255, dtype=np.uint8)
    black = np.zeros((32, 32), dtype=np.uint8)
    frames = [
        {"time_sec": 0.0, "gray": white},
        {"time_sec": 2.0, "gray": white.copy()},
        {"time_sec": 4.0, "gray": black},
    ]
    assert module.change_times(frames, threshold=0.9) == [0.0, 4.0]


def test_cluster_and_dedupe_keep_stable_slide_starts():
    module = load_module()
    assert module.cluster_times([1.0, 3.0, 30.0]) == [[1.0, 3.0], [30.0]]
    assert module.dedupe_times([0.0, 0.2, 2.0, 2.4]) == [0.0, 2.0]
