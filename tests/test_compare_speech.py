import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compare_speech import compare_speech, compare_files


def documents(expected, actual, video):
    def words(parts, source):
        return [dict({'source_word_id' if source else 'id': 'w%06d' % (i + 1)},
                     start=i * .7, end=i * .7 + .5, text=text,
                     **({'clip_id': 'clip-one'} if source else {}))
                for i, text in enumerate(parts)]
    edit = {'version': 1, 'mode': 'content-edit', 'duration': max(1, len(expected)),
            'words': words(expected, True), 'source_sha256': 'a' * 64}
    transcript = {'version': 1, 'language': 'zh', 'words': words(actual, False),
                  'media': {'sha256': hashlib.sha256(video.read_bytes()).hexdigest(),
                            'duration': max(1, len(actual))}}
    return edit, transcript


class CompareSpeechTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root / 'final.mp4'
        self.video.write_bytes(b'final media bytes for identity checking')

    def compare(self, expected, actual, **kwargs):
        return compare_speech(*documents(expected, actual, self.video), self.video, **kwargs)

    def test_case_punctuation_whitespace_and_nfkc_normalize(self):
        result = self.compare(['ＡＩ：', '２０２６年。', 'Ready!'], ['ai', '2026年', ' ready '])
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['similarity'], 1)
        self.assertEqual(result['mismatches'], [])
        self.assertIn('not proof', result['limits'])

    def test_missing_negation_forces_review_even_above_global_threshold(self):
        context = '先明确主题再解释方法并用例子帮助理解' * 15
        result = self.compare([context, '不是所有任务都适用。'], [context, '是所有任务都适用。'])
        self.assertGreater(result['similarity'], .97)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertTrue(result['mismatches'][0]['protected_changes'])

    def test_qualifier_partial_change_and_unit_change_are_protected(self):
        prefix = '这是一段充分长的背景说明。' * 30
        for left, right in [('至少三次', '至多三次'), ('长度5公里', '长度5米'),
                            ('概率可能增加', '概率一定增加'), ('not every case', 'every case'),
                            ("you can't skip review", 'you can skip review'),
                            ('it may happen', 'it must happen')]:
            with self.subTest(left=left):
                result = self.compare([prefix, left], [prefix, right])
                self.assertGreater(result['similarity'], .97)
                self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_decimal_percent_and_numeric_range_are_not_erased(self):
        for left, right in [('增长1.5%', '增长15%'), ('增长15%', '增长15'),
                            ('需要10-15秒', '需要1015秒')]:
            with self.subTest(left=left):
                result = self.compare([left], [right])
                self.assertNotEqual(result['similarity'], 1)
                self.assertEqual(result['status'], 'NEEDS_REVIEW')

    def test_repeated_and_omitted_sentences_are_reported(self):
        original = ['先明确问题。', '再选择能验证结果的方法。', '最后检查实际成片。']
        for actual in (original[:1] + original[2:], original + [original[1]]):
            with self.subTest(actual=actual):
                result = self.compare(original, actual)
                self.assertEqual(result['status'], 'NEEDS_REVIEW')
                self.assertTrue(result['mismatches'])
                self.assertGreater(result['counts']['deletions'] + result['counts']['insertions'], 0)

    def test_substitution_spans_have_actual_ids_and_output_times(self):
        result = self.compare(['先看实际画面。'], ['先看实际页面。'], threshold=1)
        self.assertEqual(result['counts']['substitutions'], 1)
        mismatch = result['mismatches'][0]
        self.assertEqual(mismatch['expected']['word_ids'], ['w000001'])
        self.assertEqual(mismatch['actual']['word_ids'], ['w000001'])
        self.assertEqual(mismatch['actual']['start'], 0)
        self.assertEqual(mismatch['actual']['end'], .5)

    def test_traditional_script_variants_are_differences(self):
        result = self.compare(['这个实际画面'], ['這個實際畫面'], threshold=1)
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertNotEqual(result['similarity'], 1)

    def test_stale_video_hash_does_not_create_report(self):
        edit, transcript = documents(['实际成片'], ['实际成片'], self.video)
        transcript['media']['sha256'] = '0' * 64
        a, b, out = self.root / 'edit.json', self.root / 'transcript.json', self.root / 'report.json'
        a.write_text(json.dumps(edit)); b.write_text(json.dumps(transcript))
        with self.assertRaisesRegex(ValueError, 'different|changed|SHA256'):
            compare_files(a, b, self.video, out)
        self.assertFalse(out.exists())

    def test_existing_outputs_and_input_files_are_preserved(self):
        edit, transcript = documents(['实际成片'], ['实际成片'], self.video)
        a, b, out = self.root / 'edit.json', self.root / 'transcript.json', self.root / 'report.json'
        a.write_text(json.dumps(edit)); b.write_text(json.dumps(transcript))
        before = {p: p.read_bytes() for p in (a, b, self.video)}
        compare_files(a, b, self.video, out)
        report_before = out.read_bytes()
        for output in (out, a, b, self.video):
            with self.subTest(output=output), self.assertRaises(FileExistsError):
                compare_files(a, b, self.video, output)
        self.assertEqual(out.read_bytes(), report_before)
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_invalid_times_empty_text_and_threshold_rejected(self):
        edit, transcript = documents(['成片'], ['成片'], self.video)
        for bad in (float('nan'), -1, 1.1, True):
            with self.subTest(threshold=bad), self.assertRaises(ValueError):
                compare_speech(edit, transcript, self.video, threshold=bad)
        for value in (float('nan'), -.1):
            t = copy.deepcopy(transcript); t['words'][0]['start'] = value
            with self.subTest(start=value), self.assertRaises(ValueError):
                compare_speech(edit, t, self.video)
        t = copy.deepcopy(transcript); t['words'][0]['text'] = '。'
        with self.assertRaises(ValueError): compare_speech(edit, t, self.video)


if __name__ == '__main__': unittest.main()
