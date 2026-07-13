import base64
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "01_transcribe_video.py"


def load_module():
    spec = importlib.util.spec_from_file_location("watchless_transcribe", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class FakeResponse:
    status_code = 200
    text = '{"result":{"text":"hello","utterances":[]}}'
    headers = {
        "X-Api-Status-Code": "20000000",
        "X-Api-Message": "OK",
        "X-Tt-Logid": "test-log-id",
    }

    def json(self):
        return {"result": {"text": "hello", "utterances": []}}


class DirectUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_flash_request_embeds_local_audio_and_returns_result(self):
        audio_bytes = b"local-audio"
        with tempfile.NamedTemporaryFile(suffix=".mp3") as audio:
            audio.write(audio_bytes)
            audio.flush()
            transcriber = self.module.AudioTranscriber(api_key="test-api-key")

            with patch.object(self.module.requests, "post", return_value=FakeResponse()) as post:
                result = transcriber.recognize_audio(audio.name, lang="zh-CN")

        self.assertEqual(result["result"]["text"], "hello")
        _, kwargs = post.call_args
        self.assertEqual(
            kwargs["json"]["audio"]["data"],
            base64.b64encode(audio_bytes).decode("ascii"),
        )
        self.assertNotIn("url", kwargs["json"]["audio"])
        self.assertEqual(
            kwargs["headers"]["X-Api-Resource-Id"],
            "volc.bigasr.auc_turbo",
        )
        self.assertTrue(post.call_args.args[0].endswith("/api/v3/auc/bigmodel/recognize/flash"))

    def test_source_has_no_cloudflare_or_boto_dependency(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("R2Uploader", source)
        self.assertNotIn("boto3", source)
        self.assertNotIn("--r2-", source)

    def test_audio_over_two_hours_is_rejected_before_upload(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3") as audio:
            transcriber = self.module.AudioTranscriber(api_key="test-api-key")
            with (
                patch.object(self.module, "probe_media_duration_seconds", return_value=7201),
                patch.object(self.module.requests, "post") as post,
            ):
                with self.assertRaisesRegex(ValueError, "2 hours"):
                    transcriber.recognize_audio(audio.name)
            post.assert_not_called()

    def test_auto_provider_prefers_volcengine_when_key_exists(self):
        with patch.object(self.module, "local_whisper_available", return_value=True):
            provider = self.module.select_transcription_provider("auto", "configured-key")
        self.assertEqual(provider, "volcengine")

    def test_auto_provider_requires_volcengine_key(self):
        with patch.object(self.module, "local_whisper_available", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "Whisper is used only"):
                self.module.select_transcription_provider("auto", None)

    def test_local_config_credentials_are_discovered_without_exposing_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.py"
            config_path.write_text(
                'ACCESS_KEY = "local-secret"\nAPP_KEY = "local-app"\n', encoding="utf-8"
            )
            key, app_key, source = self.module.resolve_volcengine_credentials(
                config_path=config_path
            )
        self.assertEqual(key, "local-secret")
        self.assertEqual(app_key, "local-app")
        self.assertIn("local config", source)

    def test_default_config_candidates_are_watchless_first_and_session_independent(self):
        candidates = self.module.local_config_candidates()
        expected = Path.home() / ".config" / "watchless" / "config.py"
        self.assertIn(expected.resolve(), candidates)
        self.assertFalse(any("session-notes-maker" in str(path) for path in candidates))

    def test_local_whisper_result_matches_existing_transcript_schema(self):
        class FakeModel:
            def transcribe(self, audio_path, **kwargs):
                self.audio_path = audio_path
                self.kwargs = kwargs
                return {
                    "text": "你好，世界。",
                    "segments": [
                        {"start": 0.25, "end": 1.5, "text": "你好，"},
                        {"start": 1.5, "end": 2.75, "text": "世界。"},
                    ],
                }

        class FakeWhisper:
            def __init__(self):
                self.model = FakeModel()

            def load_model(self, model_name, **kwargs):
                self.model_name = model_name
                self.load_kwargs = kwargs
                return self.model

        fake_whisper = FakeWhisper()
        transcriber = self.module.LocalWhisperTranscriber(
            model_name="small",
            language="zh-CN",
            whisper_module=fake_whisper,
        )
        result = transcriber.recognize_audio("audio.mp3", show_utterances=True)

        self.assertEqual(result["result"]["text"], "你好，世界。")
        self.assertEqual(
            result["result"]["utterances"],
            [
                {"start_time": 250, "end_time": 1500, "text": "你好，"},
                {"start_time": 1500, "end_time": 2750, "text": "世界。"},
            ],
        )
        self.assertEqual(fake_whisper.model_name, "small")
        self.assertEqual(fake_whisper.model.kwargs["language"], "zh")

    def test_volcengine_result_normalizes_words_and_speakers_for_video_use(self):
        normalized = self.module.normalized_word_transcript(
            {
                "result": {
                    "text": "你好",
                    "utterances": [
                        {
                            "speaker": "2",
                            "words": [
                                {"text": "你", "start_time": 100, "end_time": 200},
                                {"text": "好", "start_time": 210, "end_time": 300},
                            ],
                        }
                    ],
                }
            }
        )
        self.assertEqual([word["speaker_id"] for word in normalized["words"]], ["speaker_2", "speaker_2"])
        self.assertEqual(normalized["words"][0]["start"], 0.1)

    def test_existing_speaker_prefix_is_not_duplicated(self):
        normalized = self.module.normalized_word_transcript(
            {
                "result": {
                    "utterances": [
                        {
                            "speaker": "speaker_3",
                            "text": "测试",
                            "start_time": 0,
                            "end_time": 100,
                        }
                    ]
                }
            }
        )
        self.assertEqual(normalized["words"][0]["speaker_id"], "speaker_3")


if __name__ == "__main__":
    unittest.main()
