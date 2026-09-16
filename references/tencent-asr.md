# Tencent Cloud ASR

Both `00_build_video_notes.py` and `01_transcribe_video.py` default to `--provider tencent`. `auto` also means Tencent, with no provider fallback. Existing transcripts remain cached and are not automatically retranscribed.

Credentials: `TENCENTCLOUD_SECRET_ID` and `TENCENTCLOUD_SECRET_KEY`, or JSON keys `secret_id` and `secret_key` in `~/.config/watchless/tencent.json` (mode 0600, outside the repository). `WATCHLESS_TENCENT_CONFIG` overrides that path. Never print credentials or put them in skill files, examples, output archives or git.

Default engine: `16k_zh_en`; override with `WATCHLESS_TENCENT_ENGINE` (e.g. `16k_zh_en_2.0` or `16k_zh_en_meeting`). Use an engine supporting word timestamps and speaker diarization. Language is determined by this engine; `--lang` does not override the Tencent engine.

The provider submits `CreateRecTask` with `ResTextFormat=2`, `SpeakerDiarization=1`, and polls `DescribeTaskStatus`. This labels speakers in text; it does not export isolated voice tracks or remove background music. Speaker numbers are anonymous, not verified identities.

Local audio is encoded as 16 kHz mono MP3 and split into 600-second parts to stay below the 5 MB direct-upload limit. It goes directly to Tencent; no public bucket is needed. Every part has its own diarization namespace (`part0_0`, `part1_0`), so do not treat matching numeric labels across parts as the same person. Review sentence continuity at chunk boundaries. Word times are converted from sentence-relative milliseconds to whole-recording seconds.

Job IDs and results are cached under `~/.cache/watchless/tencent-asr/`. Rerun the same source/options to resume. Pending jobs expire after 24 hours; expired jobs stop instead of silently resubmitting. Credentials missing, API errors or task failures stop without switching clouds.

Official documentation: https://cloud.tencent.com/document/product/1093/37823 and https://cloud.tencent.com/document/api/1093/37824
