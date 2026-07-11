import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "01_acquire_source.py"


def load_module():
    spec = importlib.util.spec_from_file_location("acquire_source", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ytdlp_attempts_retry_with_browser_cookies_only_second():
    module = load_module()
    attempts = module.build_ytdlp_attempts(
        "https://www.youtube.com/watch?v=tzEWYNQmnmc",
        Path("/tmp/out/%(title)s-%(id)s.%(ext)s"),
        max_height=1080,
        language="zh",
        cookies_from_browser="chrome",
    )
    assert len(attempts) == 2
    assert "--cookies-from-browser" not in attempts[0]
    cookie_index = attempts[1].index("--cookies-from-browser")
    assert attempts[1][cookie_index + 1] == "chrome"
    assert "bv*[height<=1080]+ba/b[height<=1080]" in attempts[0]


def test_classify_ytdlp_error_maps_login_and_rate_limit():
    module = load_module()
    assert module.classify_ytdlp_error("Sign in to confirm you're not a bot") == "login_required"
    assert module.classify_ytdlp_error("HTTP Error 429: Too Many Requests") == "rate_limited"


def test_subtitle_candidates_prefer_requested_language(tmp_path):
    module = load_module()
    video = tmp_path / "talk.mp4"
    video.write_bytes(b"video")
    english = tmp_path / "talk.en.srt"
    chinese = tmp_path / "talk.zh-Hans.srt"
    english.write_text("English", encoding="utf-8")
    chinese.write_text("中文", encoding="utf-8")

    assert module._subtitle_candidates(video, "zh")[0] == chinese
    assert module._subtitle_candidates(video, "en")[0] == english
