#!/usr/bin/env python3
"""Extract audio and transcribe with Tencent ASR by default."""

from __future__ import annotations

import argparse
import base64
import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import requests
from moviepy.video.io.VideoFileClip import VideoFileClip


DEFAULT_RECOGNIZE_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
DEFAULT_RESOURCE_ID = "volc.bigasr.auc_turbo"
MAX_AUDIO_BYTES = 100 * 1024 * 1024
MAX_AUDIO_SECONDS = 2 * 60 * 60
LOCAL_CONFIG_ENV = "WATCHLESS_VOLCENGINE_CONFIG"
LEGACY_LOCAL_CONFIG_ENV = "VIDEO_NOTES_VOLCENGINE_CONFIG"


try:
    import config
except ImportError:
    class config:
        VOLCENGINE_API_KEY = "YOUR_VOLCENGINE_API_KEY"
        ACCESS_KEY = "YOUR_VOLCENGINE_ACCESS_KEY"
        APP_KEY = ""
        RECOGNIZE_URL = DEFAULT_RECOGNIZE_URL
        RESOURCE_ID = DEFAULT_RESOURCE_ID
        DEFAULT_LANGUAGE = "zh-CN"
        SUPPORTED_AUDIO_FORMATS = [".mp3", ".wav", ".ogg"]
        SUPPORTED_VIDEO_FORMATS = [".mp4", ".avi", ".mov", ".mkv"]


def _redact_secret(value, prefix=4, suffix=4):
    """Return a redacted representation for logs."""
    if value is None:
        return None
    value = str(value)
    if len(value) <= prefix + suffix:
        return "*" * len(value)
    return f"{value[:prefix]}***{value[-suffix:]}"


def _redact_mapping(data):
    """Redact common secret-bearing keys before printing debug logs."""
    redacted = {}
    for key, value in data.items():
        lowered = str(key).lower()
        if any(token in lowered for token in ("key", "secret", "authorization", "token")):
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted


def _configured_value(*names, default=None):
    for name in names:
        value = getattr(config, name, None)
        if value and not str(value).startswith("YOUR_"):
            return str(value)
    return default


def _usable_secret(value):
    return bool(value) and not str(value).startswith("YOUR_")


def _load_config_file(path):
    """Load a local Python config without adding it to sys.path."""
    path = Path(path).expanduser()
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"watchless_local_config_{uuid.uuid4().hex}", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def local_config_candidates(explicit_path=None):
    """Return safe, deterministic locations used by prior local installs."""
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())
    for env_name in (LOCAL_CONFIG_ENV, LEGACY_LOCAL_CONFIG_ENV):
        if os.environ.get(env_name):
            candidates.append(Path(os.environ[env_name]).expanduser())

    home = Path.home()
    candidates.extend(
        [
            home / ".config" / "watchless" / "config.py",
            home / ".codex" / "skills" / "watchless" / "scripts" / "config.py",
            home / ".config" / "video-notes-maker" / "config.py",
            home / ".codex" / "skills" / "video-notes-maker" / "scripts" / "config.py",
        ]
    )
    unique = []
    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def resolve_volcengine_credentials(cli_api_key=None, cli_app_key=None, config_path=None):
    """Resolve credentials without copying or printing secret values."""
    if _usable_secret(cli_api_key):
        return str(cli_api_key), str(cli_app_key or ""), "command line"

    env_key = os.environ.get("VOLCENGINE_API_KEY") or os.environ.get("VOLCENGINE_ACCESS_KEY")
    env_app = os.environ.get("VOLCENGINE_APP_KEY", "")
    if _usable_secret(env_key):
        return env_key, env_app, "environment"

    configured_key = _configured_value("VOLCENGINE_API_KEY", "ACCESS_KEY")
    configured_app = _configured_value("APP_KEY", default="")
    if _usable_secret(configured_key):
        return configured_key, configured_app, "scripts/config.py"

    for candidate in local_config_candidates(config_path):
        module = _load_config_file(candidate)
        if module is None:
            continue
        key = getattr(module, "VOLCENGINE_API_KEY", None) or getattr(module, "ACCESS_KEY", None)
        if _usable_secret(key):
            app_key = getattr(module, "APP_KEY", "")
            return str(key), str(app_key or ""), f"local config: {candidate}"
    return None, None, None


def _normalize_language(language):
    aliases = {
        "zh": "zh-CN",
        "en": "en-US",
        "ja": "ja-JP",
        "ko": "ko-KR",
    }
    return aliases.get(language, language)


def _normalize_whisper_language(language):
    """Convert locale-style language codes to Whisper's short codes."""
    if not language:
        return None
    return str(language).split("-", 1)[0].lower()


def local_whisper_available():
    """Return whether the optional OpenAI Whisper package is installed."""
    return importlib.util.find_spec("whisper") is not None


def select_transcription_provider(requested, api_key):
    """Resolve auto/explicit provider selection without making a network call."""
    if requested in ("tencent", "auto"):
        return "tencent"
    if requested == "volcengine":
        if not api_key:
            raise RuntimeError("Volcengine provider requires VOLCENGINE_API_KEY or --api-key")
        return "volcengine"
    if requested == "whisper":
        if not local_whisper_available():
            raise RuntimeError(
                "Local openai-whisper is not installed; "
                "run `pip install -r scripts/requirements-whisper.txt`"
            )
        return "whisper"
    raise ValueError(f"Unknown transcription provider: {requested}")


def _audio_format(audio_path):
    extension = Path(audio_path).suffix.lower()
    formats = {".mp3": "mp3", ".wav": "wav", ".ogg": "ogg"}
    if extension not in formats:
        raise ValueError(
            f"ASR Flash only accepts WAV, MP3, or OGG OPUS; got {extension or 'no extension'}"
        )
    return formats[extension]


def probe_media_duration_seconds(path):
    """Return media duration via ffprobe, or None when it cannot be read."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return None
        return float(completed.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def format_srt_timestamp(ms):
    """Convert milliseconds to SRT timestamp format."""
    total_ms = max(int(ms), 0)
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    seconds = (total_ms % 60000) // 1000
    milliseconds = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def build_srt_content(result, include_speaker=True):
    """Build SRT subtitle content from the API result."""
    utterances = result.get("result", {}).get("utterances", [])
    blocks = []
    sequence = 1
    for utterance in utterances:
        text = (utterance.get("text") or "").strip()
        if not text:
            continue
        speaker = utterance.get("speaker")
        if speaker in (None, ""):
            speaker = utterance.get("additions", {}).get("speaker")
        if include_speaker and speaker not in (None, ""):
            text = f"说话人{speaker}: {text}"
        blocks.append(
            f"{sequence}\n"
            f"{format_srt_timestamp(utterance.get('start_time', 0))} --> "
            f"{format_srt_timestamp(utterance.get('end_time', 0))}\n"
            f"{text}"
        )
        sequence += 1
    return "\n\n".join(blocks)


def save_transcript(result, output_file=None, srt_output_file=None):
    """Write the existing transcript text format and optional SRT file."""
    result_data = result.get("result", {})
    full_text = result_data.get("text", "No transcript text available in result object.")
    output = f"Full Transcript:\n{full_text}\n\n"

    utterances = result_data.get("utterances", [])
    if utterances:
        output += "Utterances with timing:\n"
        for utterance in utterances:
            start_time = utterance.get("start_time", 0) / 1000
            end_time = utterance.get("end_time", 0) / 1000
            text = utterance.get("text", "")
            speaker = utterance.get("speaker")
            if speaker in (None, ""):
                speaker = utterance.get("additions", {}).get("speaker")
            prefix = f"说话人{speaker}: " if speaker not in (None, "") else ""
            output += f"[{start_time:.2f}s - {end_time:.2f}s] {prefix}{text}\n"

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"Transcript saved to: {output_path}")
    else:
        print(output)

    if srt_output_file:
        srt_content = build_srt_content(result, include_speaker=True)
        if srt_content:
            srt_path = Path(srt_output_file)
            srt_path.parent.mkdir(parents=True, exist_ok=True)
            srt_path.write_text(srt_content, encoding="utf-8")
            print(f"SRT subtitle saved to: {srt_path}")
        else:
            print("Warning: No utterance timestamps returned; SRT was not created.")


def normalized_word_transcript(result, provider="volcengine"):
    """Return the word-level schema consumed by video-use helpers."""
    words = []
    for utterance in result.get("result", {}).get("utterances", []) or []:
        speaker = utterance.get("speaker")
        if speaker in (None, ""):
            speaker = utterance.get("additions", {}).get("speaker")
        if speaker in (None, ""):
            speaker_id = None
        else:
            speaker_text = str(speaker)
            speaker_id = speaker_text if speaker_text.startswith("speaker_") else f"speaker_{speaker_text}"
        utterance_words = utterance.get("words") or []
        if utterance_words:
            for word in utterance_words:
                text = (word.get("text") or "").strip()
                start_ms = word.get("start_time")
                end_ms = word.get("end_time")
                if not text or start_ms is None or end_ms is None:
                    continue
                item = {
                    "text": text,
                    "type": "word",
                    "start": float(start_ms) / 1000.0,
                    "end": float(end_ms) / 1000.0,
                }
                if speaker_id:
                    item["speaker_id"] = speaker_id
                words.append(item)
        else:
            text = (utterance.get("text") or "").strip()
            start_ms = utterance.get("start_time")
            end_ms = utterance.get("end_time")
            if text and start_ms is not None and end_ms is not None:
                item = {
                    "text": text,
                    "type": "word",
                    "start": float(start_ms) / 1000.0,
                    "end": float(end_ms) / 1000.0,
                }
                if speaker_id:
                    item["speaker_id"] = speaker_id
                words.append(item)
    words.sort(key=lambda item: (item["start"], item["end"]))
    return {
        "text": result.get("result", {}).get("text", ""),
        "words": words,
        "metadata": {**result.get("metadata", {}), "provider": provider, "word_timestamps": True},
    }


class AudioTranscriber:
    def __init__(
        self,
        api_key,
        app_key=None,
        recognize_url=None,
        resource_id=None,
        timeout=1800,
    ):
        self.api_key = api_key
        self.app_key = app_key
        self.recognize_url = recognize_url or _configured_value(
            "RECOGNIZE_URL", default=DEFAULT_RECOGNIZE_URL
        )
        self.resource_id = resource_id or _configured_value(
            "RESOURCE_ID", default=DEFAULT_RESOURCE_ID
        )
        self.timeout = timeout
        self.cache_dir = Path(__file__).resolve().parent / ".audiocache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def extract_audio_from_video(self, video_path):
        """Extract a compact mono MP3 from video and reuse it on later runs."""
        video_path = Path(video_path)
        cached_path = self.cache_dir / f"{video_path.stem}.mp3"
        if cached_path.exists():
            print(f"Using cached audio: {cached_path}")
            return str(cached_path)

        print(f"Extracting audio: {video_path} -> {cached_path}")
        clip = VideoFileClip(str(video_path))
        try:
            if clip.audio is None:
                raise ValueError("Video does not contain an audio track")
            clip.audio.write_audiofile(
                str(cached_path),
                codec="libmp3lame",
                bitrate="64k",
                fps=16000,
                ffmpeg_params=["-ac", "1"],
                logger=None,
            )
        except Exception:
            cached_path.unlink(missing_ok=True)
            raise
        finally:
            clip.close()
        return str(cached_path)

    def process_input_file(self, file_path):
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File does not exist: {path}")
        extension = path.suffix.lower()
        video_formats = set(getattr(config, "SUPPORTED_VIDEO_FORMATS", [".mp4", ".avi", ".mov", ".mkv"]))
        audio_formats = set(getattr(config, "SUPPORTED_AUDIO_FORMATS", [".mp3", ".wav", ".ogg"]))
        if extension in video_formats:
            return self.extract_audio_from_video(path)
        if extension in audio_formats:
            return str(path)
        raise ValueError(f"Unsupported media type: {extension}")

    def _headers(self, request_id):
        headers = {
            "Content-Type": "application/json",
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Request-Id": request_id,
            "X-Api-Sequence": "-1",
        }
        if self.app_key:
            headers["X-Api-App-Key"] = self.app_key
            headers["X-Api-Access-Key"] = self.api_key
        else:
            headers["X-Api-Key"] = self.api_key
        return headers

    def recognize_audio(self, audio_path, lang="zh-CN", punctuation=True, show_utterances=True):
        """Send local audio as Base64 and return the synchronous Flash result."""
        audio_path = Path(audio_path)
        file_size = audio_path.stat().st_size
        if file_size > MAX_AUDIO_BYTES:
            raise ValueError(
                f"Audio is {file_size / 1024 / 1024:.1f}MB; ASR Flash accepts at most 100MB"
            )
        duration = probe_media_duration_seconds(audio_path)
        if duration is not None and duration > MAX_AUDIO_SECONDS:
            raise ValueError(
                f"Audio is {duration / 3600:.2f} hours; ASR Flash accepts at most 2 hours"
            )

        request_id = str(uuid.uuid4())
        audio = {
            "format": _audio_format(audio_path),
            "data": base64.b64encode(audio_path.read_bytes()).decode("ascii"),
        }
        language = _normalize_language(lang)
        if language:
            audio["language"] = language
        payload = {
            "user": {"uid": self.app_key or "watchless"},
            "audio": audio,
            "request": {
                "model_name": "bigmodel",
                "enable_itn": True,
                "enable_punc": punctuation,
                "enable_speaker_info": show_utterances,
                "enable_channel_split": False,
                "enable_ddc": False,
                "show_utterances": show_utterances,
                "vad_segment": True,
                "sensitive_words_filter": "",
            },
        }
        headers = self._headers(request_id)
        print(f"Sending {file_size / 1024 / 1024:.1f}MB audio directly to Volcengine ASR Flash")
        print(f"Request headers: {json.dumps(_redact_mapping(headers), ensure_ascii=False)}")

        try:
            response = requests.post(
                self.recognize_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Volcengine request failed: {exc}") from exc

        status = response.headers.get("X-Api-Status-Code", "")
        message = response.headers.get("X-Api-Message", "")
        log_id = response.headers.get("X-Tt-Logid", "")
        if response.status_code != 200 or status != "20000000":
            detail = message or response.text[:500]
            raise RuntimeError(
                f"Volcengine ASR failed: HTTP {response.status_code}, code {status or 'missing'}, "
                f"message {detail}, logid {log_id or 'missing'}"
            )
        try:
            result = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Volcengine returned invalid JSON; logid {log_id or 'missing'}") from exc
        if not result.get("result"):
            raise RuntimeError(f"Volcengine returned no recognition result; logid {log_id or 'missing'}")
        print(f"Recognition completed; logid: {log_id or 'not returned'}")
        return result


class LocalWhisperTranscriber(AudioTranscriber):
    """Run OpenAI Whisper locally and return the existing transcript schema."""

    def __init__(
        self,
        model_name="small",
        language="zh-CN",
        device="auto",
        whisper_module=None,
    ):
        super().__init__(api_key="")
        self.model_name = model_name
        self.language = language
        self.device = device
        self.whisper_module = whisper_module

    def recognize_audio(self, audio_path, lang=None, punctuation=True, show_utterances=True):
        del punctuation  # Whisper handles punctuation as part of decoding.
        whisper_module = self.whisper_module or importlib.import_module("whisper")
        load_kwargs = {}
        if self.device and self.device != "auto":
            load_kwargs["device"] = self.device
        print(f"Loading local Whisper model: {self.model_name}")
        model = whisper_module.load_model(self.model_name, **load_kwargs)
        language = _normalize_whisper_language(lang or self.language)
        print(f"Running local Whisper transcription ({language or 'auto language'})")
        raw = model.transcribe(
            str(audio_path),
            language=language,
            verbose=False,
            fp16=False,
            temperature=0,
        )
        utterances = []
        if show_utterances:
            for segment in raw.get("segments", []):
                text = (segment.get("text") or "").strip()
                if not text:
                    continue
                utterances.append(
                    {
                        "start_time": round(float(segment.get("start", 0)) * 1000),
                        "end_time": round(float(segment.get("end", 0)) * 1000),
                        "text": text,
                    }
                )
        full_text = (raw.get("text") or "").strip()
        if not full_text:
            full_text = "".join(item["text"] for item in utterances)
        return {"result": {"text": full_text, "utterances": utterances}}


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe local audio/video with Tencent ASR and speaker diarization."
    )
    parser.add_argument("input_file", help="Path to a local audio or video file")
    parser.add_argument("--output", "-o", help="Transcript text output path")
    parser.add_argument("--srt-output", help="Optional SRT subtitle output path")
    parser.add_argument("--json-output", help="Optional video-use-compatible word-level JSON")
    parser.add_argument("--api-key", help="New-console Volcengine API key")
    parser.add_argument("--access-key", help="API key, or old-console access token")
    parser.add_argument("--app-key", help="Old-console App ID/App Key")
    parser.add_argument(
        "--volcengine-config",
        help=f"Existing local config.py; can also be set with {LOCAL_CONFIG_ENV}",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "tencent", "volcengine", "whisper"],
        default="tencent",
        help="Tencent is the default; other providers must be requested explicitly",
    )
    parser.add_argument(
        "--whisper-model",
        default=getattr(config, "WHISPER_MODEL", "small"),
        help="Local Whisper model name (default: config WHISPER_MODEL or small)",
    )
    parser.add_argument(
        "--whisper-device",
        default="auto",
        help="Whisper device such as auto, cpu, or cuda",
    )
    parser.add_argument(
        "--lang",
        default=getattr(config, "DEFAULT_LANGUAGE", "zh-CN"),
        help="Language code, for example zh-CN or en-US",
    )
    parser.add_argument("--no-punctuation", action="store_true")
    parser.add_argument("--no-utterances", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800, help="HTTP timeout in seconds")
    args = parser.parse_args()

    api_key, app_key, credential_source = None, None, None
    if args.provider == "volcengine":
        api_key, app_key, credential_source = resolve_volcengine_credentials(
            cli_api_key=args.api_key or args.access_key,
            cli_app_key=args.app_key,
            config_path=args.volcengine_config,
        )
    try:
        provider = select_transcription_provider(args.provider, api_key)
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    try:
        if provider == "tencent":
            from tencent_asr import TencentTranscriber
            transcriber = TencentTranscriber(timeout=args.timeout)
            print("Transcription provider: Tencent Cloud ASR (speaker diarization enabled)")
        elif provider == "volcengine":
            transcriber = AudioTranscriber(api_key=api_key, app_key=app_key, timeout=args.timeout)
            print("Transcription provider: Volcengine ASR Flash")
            print(f"Credential source: {credential_source}")
        else:
            transcriber = LocalWhisperTranscriber(
                model_name=args.whisper_model,
                language=args.lang,
                device=args.whisper_device,
            )
            print("Transcription provider: local Whisper")
        audio_path = transcriber.process_input_file(args.input_file)
        result = transcriber.recognize_audio(
            audio_path,
            lang=args.lang,
            punctuation=not args.no_punctuation,
            show_utterances=not args.no_utterances,
        )
        save_transcript(result, args.output, args.srt_output)
        if args.json_output:
            json_path = Path(args.json_output)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(
                json.dumps(normalized_word_transcript(result, provider=provider), ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
            print(f"Word-level transcript saved to: {json_path}")
    except Exception as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
