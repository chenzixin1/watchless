"""Tencent recording ASR: direct local upload, resumable jobs, no public storage."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def credentials():
    sid, key = os.getenv('TENCENTCLOUD_SECRET_ID'), os.getenv('TENCENTCLOUD_SECRET_KEY')
    if sid and key:
        return sid, key
    path = Path(os.getenv('WATCHLESS_TENCENT_CONFIG', '~/.config/watchless/tencent.json')).expanduser()
    if path.exists():
        data = json.loads(path.read_text())
        sid, key = data.get('secret_id'), data.get('secret_key')
        if sid and key:
            return sid, key
    raise RuntimeError('Tencent ASR credentials missing: configure TENCENTCLOUD_SECRET_ID/SECRET_KEY or ~/.config/watchless/tencent.json')


def normalize(details, offset_ms=0, part=None):
    utterances = []
    for sentence in details or []:
        start = sentence['StartMs'] + offset_ms
        speaker = sentence.get('SpeakerId')
        if speaker is not None and speaker >= 0 and part is not None:
            speaker = f'part{part}_{speaker}'
        elif speaker is not None and speaker < 0:
            speaker = None
        words = [{'text': w['Word'], 'start_time': start + w['OffsetStartMs'],
                  'end_time': start + w['OffsetEndMs']} for w in sentence.get('Words') or []]
        utterances.append({'text': sentence['FinalSentence'], 'start_time': start,
                           'end_time': sentence['EndMs'] + offset_ms, 'speaker': speaker, 'words': words})
    return utterances


class TencentTranscriber:
    def __init__(self, timeout=1800, engine=None, speaker_number=0):
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.asr.v20190614 import asr_client, models
        sid, key = credentials()
        profile = ClientProfile(httpProfile=HttpProfile(reqTimeout=60))
        # Do not retry CreateRecTask automatically: a lost response could duplicate billing.
        self.client = asr_client.AsrClient(credential.Credential(sid, key), '', profile)
        self.models, self.timeout = models, timeout
        self.engine = engine or os.getenv('WATCHLESS_TENCENT_ENGINE', '16k_zh_en')
        self.speaker_number = speaker_number

    def process_input_file(self, path):
        path = Path(path).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return str(path)

    def call(self, action, payload):
        from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
        request = getattr(self.models, action + 'Request')()
        request.from_json_string(json.dumps(payload))
        try:
            return json.loads(getattr(self.client, action)(request).to_json_string())
        except TencentCloudSDKException as exc:
            # Error codes suffice; do not log request bodies, signed URLs or credentials.
            raise RuntimeError(f'Tencent ASR {action} failed: {exc.get_code()}') from None

    def recognize_audio(self, audio_path, lang='zh-CN', punctuation=True, show_utterances=True):
        path = Path(audio_path)
        digest = hashlib.sha256()
        with path.open('rb') as source:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(block)
        options = {'EngineModelType': self.engine, 'ChannelNum': 1, 'ResTextFormat': 2,
                   'SpeakerDiarization': int(show_utterances), 'SpeakerNumber': self.speaker_number,
                   'FilterPunc': 0 if punctuation else 2, 'FilterModal': 0, 'ConvertNumMode': 0}
        digest.update(json.dumps(options, sort_keys=True).encode())
        cache = Path.home()/'.cache/watchless/tencent-asr'/digest.hexdigest()
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        manifest = cache/'parts.json'
        if not manifest.exists():
            # 600 s at 32 kbit/s is about 2.4 MB, safely below the 5 MB API limit.
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(path), '-vn', '-ac', '1',
                            '-ar', '16000', '-c:a', 'libmp3lame', '-b:a', '32k', '-f', 'segment',
                            '-segment_time', '600', '-reset_timestamps', '1', '-segment_list',
                            str(cache/'segments.csv'), '-segment_list_type', 'csv', str(cache/'part%04d.mp3')], check=True)
            import csv
            with (cache/'segments.csv').open() as f:
                parts = [{'file': row[0], 'offset_ms': round(float(row[1])*1000)} for row in csv.reader(f)]
            manifest.write_text(json.dumps(parts))
        parts = json.loads(manifest.read_text())
        utterances = []
        for index, part in enumerate(parts):
            state_path = cache/f'job{index}.json'
            state = json.loads(state_path.read_text()) if state_path.exists() else {}
            if not state:
                data = (cache/part['file']).read_bytes()
                if len(data) > 5*1024*1024:
                    raise ValueError('Tencent local audio exceeds 5 MB')
                reply = self.call('CreateRecTask', dict(options, SourceType=1, DataLen=len(data), Data=base64.b64encode(data).decode()))
                state = {'task_id': reply['Data']['TaskId'], 'created': time.time()}
                state_path.write_text(json.dumps(state))
            if 'result' not in state and time.time() - state['created'] > 23*3600:
                raise RuntimeError(f'Tencent task expired; remove {state_path} to explicitly resubmit')
            deadline = time.monotonic() + self.timeout
            while 'result' not in state:
                result = self.call('DescribeTaskStatus', {'TaskId': state['task_id']})['Data']
                if result['Status'] == 2:
                    state['result'] = result
                    state_path.write_text(json.dumps(state, ensure_ascii=False))
                    break
                if result['Status'] == 3:
                    raise RuntimeError(f'Tencent ASR task failed: {result.get("ErrorMsg", "unknown")}')
                if time.monotonic() >= deadline:
                    raise TimeoutError('Tencent ASR polling timed out; rerun to resume saved task')
                time.sleep(3)
            utterances.extend(normalize(state['result'].get('ResultDetail'), part['offset_ms'], index if len(parts)>1 else None))
        if not utterances:
            raise RuntimeError('Tencent ASR returned no timestamped speech')
        return {'result': {'text': ''.join(u['text'] for u in utterances), 'utterances': utterances},
                'metadata': {'provider': 'tencent', 'speaker_labels_are_not_global': len(parts)>1, 'parts': len(parts)}}
