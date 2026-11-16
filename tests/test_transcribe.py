import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SPEC = importlib.util.spec_from_file_location('speech_ingest', Path(__file__).parents[1] / 'scripts/transcribe.py')
ingest = importlib.util.module_from_spec(SPEC)
if SPEC.loader:
    SPEC.loader.exec_module(ingest)


def word(text, start, end, probability=0.9):
    return SimpleNamespace(word=text, start=start, end=end, probability=probability)


def segment(words, avg_logprob=-0.2, no_speech_prob=0.01):
    return SimpleNamespace(words=words, avg_logprob=avg_logprob, no_speech_prob=no_speech_prob)


class IngestTests(unittest.TestCase):
    def media(self):
        return {'file': 'source.mov', 'sha256': 'a' * 64, 'duration': 3.0,
                'origin': 5.0, 'video_start': 5.0, 'audio_start': 5.026,
                'width': 640, 'height': 360, 'rotation': 90}

    def test_probe_preserves_common_origin_and_audio_offset(self):
        probe = {'streams': [
            {'codec_type': 'video', 'start_time': '5.0', 'duration': '2.0',
             'width': 640, 'height': 360, 'side_data_list': [{'rotation': 90}]},
            {'codec_type': 'audio', 'start_time': '5.026', 'duration': '2.5'}],
            'format': {'start_time': '5.0', 'duration': '2.526'}}
        media = ingest.media_metadata(probe)
        self.assertAlmostEqual(media['origin'], 5.0)
        self.assertAlmostEqual(media['duration'], 2.526)
        self.assertAlmostEqual(media['audio_start'], 5.026)
        self.assertEqual(media['rotation'], 90)

    def test_probe_without_audio_rejected(self):
        with self.assertRaisesRegex(ValueError, 'audio'):
            ingest.media_metadata({'streams': [{'codec_type': 'video', 'width': 640, 'height': 360}],
                                   'format': {'duration': '2'}})

    def test_container_duration_fallback_uses_selected_stream_origin(self):
        media = ingest.media_metadata({'streams': [
            {'codec_type': 'video', 'start_time': '5', 'width': 640, 'height': 360},
            {'codec_type': 'audio', 'start_time': '5.1'}],
            'format': {'duration': '2.5'}})
        self.assertAlmostEqual(media['origin'], 5)
        self.assertAlmostEqual(media['duration'], 2.5)

    def test_offset_punctuation_and_source_text_are_retained(self):
        payload = ingest.transcript_payload([segment([
            word('嗯', 0.1, 0.2), word('这是', 0.3, 0.5), word('。', 0.5, 0.5)])],
            self.media(), language='zh')
        self.assertEqual([w['text'] for w in payload['words']], ['嗯', '这是。'])
        self.assertAlmostEqual(payload['words'][0]['start'], 0.126)
        self.assertAlmostEqual(payload['words'][1]['end'], 0.526)
        self.assertEqual(payload['segments'][0]['word_ids'], ['w000001', 'w000002'])
        self.assertEqual(payload['segments'][0]['text'], '嗯这是。')

    def test_nonfinite_overlap_and_zero_duration_speech_rejected(self):
        invalid = [
            [word('错', float('nan'), 1)],
            [word('前', 0.1, 0.7), word('后', 0.5, 0.8)],
            [word('实词', 0.1, 0.1)],
            [word('越界', 2.9, 3.5)],
        ]
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                ingest.transcript_payload([segment(raw)], self.media(), language='zh')

    def test_no_speech_is_not_a_fabricated_transcript(self):
        with self.assertRaisesRegex(ValueError, 'No speech'):
            ingest.transcript_payload([], self.media(), language='zh')

    def test_low_confidence_words_are_flagged_not_deleted(self):
        payload = ingest.transcript_payload([segment([word('专名', 0.1, 0.3, 0.2)])],
                                            self.media(), language='zh')
        self.assertEqual(payload['words'][0]['text'], '专名')
        self.assertEqual(payload['metadata']['review_word_ids'], ['w000001'])

    def test_fingerprint_binds_source_language_and_word_timing(self):
        payload = ingest.transcript_payload([segment([word('测试', 0.1, 0.3)])], self.media(), language='zh')
        canonical = json.dumps({'source_sha256': payload['media']['sha256'], 'language': 'zh',
                                'words': payload['words']}, ensure_ascii=False, sort_keys=True,
                               separators=(',', ':'), allow_nan=False).encode()
        self.assertEqual(payload['fingerprint'], hashlib.sha256(canonical).hexdigest())
        changed_words = [dict(payload['words'][0], start=0.2)]
        self.assertNotEqual(payload['fingerprint'], ingest.transcript_fingerprint(self.media(), 'zh', changed_words))

    def test_existing_output_rejected_before_probe_or_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'raw.MOV'; source.write_bytes(b'original')
            output = root / 'project'; output.mkdir()
            sentinel = output / 'keep'; sentinel.write_bytes(b'keep')
            with mock.patch.object(ingest, 'probe_media') as probe:
                with self.assertRaises(FileExistsError):
                    ingest.transcribe(source, output, model='unused')
                probe.assert_not_called()
            self.assertEqual(source.read_bytes(), b'original')
            self.assertEqual(sentinel.read_bytes(), b'keep')

    def test_failed_recognition_does_not_create_success_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'raw.mov'; source.write_bytes(b'original')
            output = root / 'new-project'
            media = self.media(); media.update(origin=0, audio_start=0, video_start=0)
            fake_model = SimpleNamespace(transcribe=lambda *a, **kw: (iter([]), SimpleNamespace(language='zh')))
            with mock.patch.object(ingest, 'probe_media', return_value=media), \
                 mock.patch.object(ingest, 'load_model', return_value=fake_model), \
                 mock.patch.object(ingest, 'extract_audio'), \
                 mock.patch.object(ingest, 'audio_samples', return_value=[]):
                with self.assertRaisesRegex(ValueError, 'No speech'):
                    ingest.transcribe(source, output, model='unused')
            self.assertFalse(output.exists())
            self.assertEqual(source.read_bytes(), b'original')

    def test_success_copies_media_and_writes_relative_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'raw.MOV'; source.write_bytes(b'original')
            output = root / 'new-project'; media = self.media()
            fake_model = SimpleNamespace(transcribe=lambda *a, **kw: (
                iter([segment([word('测试', 0.1, 0.5)])]), SimpleNamespace(language='zh', language_probability=1.0)))
            with mock.patch.object(ingest, 'probe_media', return_value=media), \
                 mock.patch.object(ingest, 'load_model', return_value=fake_model), \
                 mock.patch.object(ingest, 'extract_audio'), \
                 mock.patch.object(ingest, 'audio_samples', return_value=[]):
                result = ingest.transcribe(source, output, model='unused')
            self.assertEqual((output / 'source.mov').read_bytes(), source.read_bytes())
            saved = json.loads((output / 'transcript.json').read_text())
            self.assertEqual(saved['media']['file'], 'source.mov')
            self.assertEqual(result['words'][0]['id'], 'w000001')
            self.assertIn('w000001', (output / 'transcript.md').read_text())
            self.assertNotIn(str(root), json.dumps(saved))


if __name__ == '__main__':
    unittest.main()
