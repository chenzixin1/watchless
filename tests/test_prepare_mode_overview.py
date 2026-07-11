import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "02_prepare_mode_overview.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_mode_overview", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sample_timestamps_cover_video_without_touching_ends():
    module = load_module()
    timestamps = module.sample_timestamps(duration=100.0, samples=5)
    assert len(timestamps) == 5
    assert timestamps[0] == 3.0
    assert timestamps[-1] == 97.0
    assert timestamps == sorted(timestamps)


def test_single_sample_is_valid():
    module = load_module()
    assert module.sample_timestamps(duration=10.0, samples=1) == [0.3]
