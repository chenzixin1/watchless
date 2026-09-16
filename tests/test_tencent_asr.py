import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from tencent_asr import normalize, TencentTranscriber
from unittest.mock import Mock

class TencentTests(unittest.TestCase):
    def test_sentence_relative_words_and_chunk_speakers(self):
        details = [{'StartMs': 2000, 'EndMs': 3000, 'SpeakerId': 0, 'FinalSentence': '你好',
                    'Words': [{'Word': '你好', 'OffsetStartMs': 100, 'OffsetEndMs': 900}]}]
        result = normalize(details, 600000, 1)[0]
        self.assertEqual(result['words'][0]['start_time'], 602100)
        self.assertEqual(result['words'][0]['end_time'], 602900)
        self.assertEqual(result['speaker'], 'part1_0')
        self.assertEqual(normalize(details)[0]['speaker'], 0)

    def test_sdk_errors_do_not_disclose_message(self):
        from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
        from tencentcloud.asr.v20190614 import models
        transcriber = TencentTranscriber.__new__(TencentTranscriber)
        transcriber.models = models
        transcriber.client = Mock()
        transcriber.client.CreateRecTask.side_effect = TencentCloudSDKException('AuthFailure', 'secret-canary')
        with self.assertRaisesRegex(RuntimeError, '^Tencent ASR CreateRecTask failed: AuthFailure$'):
            transcriber.call('CreateRecTask', {})
