import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from edit import compile_edit, render_edit, fingerprint, source_streams


def transcript():
    return {'version': 1, 'language': 'zh',
            'media': {'file': 'source.mov', 'sha256': 'a' * 64, 'duration': 3,
                      'origin': 0, 'audio_start': 0, 'video_start': 0,
                      'width': 64, 'height': 96, 'rotation': 0},
            'words': [{'id': 'w1', 'start': .2, 'end': .6, 'text': '先说明。', 'probability': .99},
                      {'id': 'w2', 'start': .8, 'end': 1.2, 'text': '这段重录。', 'probability': .99},
                      {'id': 'w3', 'start': 1.5, 'end': 2.0, 'text': '不是所有任务。', 'probability': .99},
                      {'id': 'w4', 'start': 2.2, 'end': 2.6, 'text': '只需3次。', 'probability': .99}]}


def plan():
    return {'version': 1, 'mode': 'content-edit', 'source_sha256': transcript()['media']['sha256'],
            'transcript_fingerprint': fingerprint(transcript()), 'title': '适用范围', 'header': '先看条件',
            'goal': '用完整的限定和结论解释适用范围',
            'segments': [{'id': 'conclusion', 'word_ids': ['w3', 'w4'], 'reason': '先给完整结论', 'role': 'hook'},
                         {'id': 'context', 'word_ids': ['w1'], 'reason': '补充背景', 'role': 'context'}],
            'omissions': [{'word_ids': ['w2'], 'reason': '明确失败重录'}],
            'review': {'facts_and_qualifiers': 'pass', 'continuity': 'pass', 'transcript': 'pass',
                       'notes': ['已核对重排后的指代'], 'unresolved': []}}


class EditPlanTests(unittest.TestCase):
    def test_cover_art_is_not_selected_as_the_recorded_video(self):
        streams=[{'index':0,'codec_type':'video','disposition':{'attached_pic':1}},
                 {'index':1,'codec_type':'audio'}, {'index':2,'codec_type':'video'}]
        video,audio=source_streams({'streams':streams})
        self.assertEqual((video['index'],audio['index']),(2,1))
        with self.assertRaises(ValueError):source_streams({'streams':streams[:2]})

    def test_reorder_remaps_words_and_captions_without_changing_text(self):
        result = compile_edit(transcript(), plan())
        self.assertEqual([w['source_word_id'] for w in result['words']], ['w3', 'w4', 'w1'])
        self.assertEqual(''.join(c['text'] for c in result['captions']), '不是所有任务。只需3次。先说明。')
        self.assertGreaterEqual(result['captions'][0]['start'], 0)
        self.assertLessEqual(result['captions'][-1]['end'], result['duration'])
        self.assertAlmostEqual(result['duration'] * 30, result['frames'])

    def test_unaccounted_duplicate_and_invented_words_rejected(self):
        for mutate in ('missing', 'duplicate', 'invented'):
            p = plan()
            if mutate == 'missing': p['omissions'] = []
            if mutate == 'duplicate': p['segments'][1]['word_ids'] = ['w3']
            if mutate == 'invented': p['segments'][1]['word_ids'] = ['unknown']
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                compile_edit(transcript(), p)

    def test_noncontiguous_segment_rejected(self):
        p = plan(); p['segments'][0]['word_ids'] = ['w1', 'w3']
        with self.assertRaises(ValueError): compile_edit(transcript(), p)

    def test_plan_cannot_be_reused_for_changed_transcript_of_same_source(self):
        t = transcript(); t['words'][0]['text'] = '另一遍识别结果。'
        with self.assertRaisesRegex(ValueError, 'different transcript'): compile_edit(t, plan())

    def test_padding_never_includes_omitted_neighbor(self):
        t = transcript(); t['words'][1]['end'] = 1.49
        p = plan(); p['transcript_fingerprint'] = fingerprint(t)
        doc = compile_edit(t, p)
        self.assertGreaterEqual(doc['timeline'][0]['source_start'], 1.49)
        self.assertLessEqual(doc['timeline'][1]['source_end'], .8)

    def test_doubt_is_not_reported_as_ready(self):
        p = plan(); p['review']['unresolved'] = ['专名尚未听清']
        self.assertEqual(compile_edit(transcript(), p)['status'], 'needs_review')

    def test_agent_caption_groups_use_source_word_times_and_preserve_content(self):
        p = plan(); p['caption_groups'] = [{'word_ids':['w3'], 'text':'不是所有任务。'},
                                          {'word_ids':['w4']}, {'word_ids':['w1']}]
        doc = compile_edit(transcript(),p)
        self.assertEqual(len(doc['captions']),3)
        self.assertEqual(doc['captions'][1]['start'],round(doc['words'][1]['start'],6))
        for invalid in ([{'word_ids':['w3','w4'],'text':'所有任务只需30次。'},{'word_ids':['w1']}],
                        [{'word_ids':['w3','w4','w1']}], [{'word_ids':['w3','w4']}]):
            p['caption_groups']=invalid
            with self.assertRaises(ValueError):compile_edit(transcript(),p)

    def test_caption_groups_do_not_merge_latin_words_or_remove_lexical_marks(self):
        for before,after in [('not able','notable'),('re-sign','resign'),("can't",'cant')]:
            t=transcript();t['words'][0]['text']=before
            p=plan();p['transcript_fingerprint']=fingerprint(t)
            p['caption_groups']=[{'word_ids':['w3','w4']},{'word_ids':['w1'],'text':after}]
            with self.subTest(before=before,after=after),self.assertRaises(ValueError):compile_edit(t,p)

    def test_correction_must_not_silently_change_numbers_or_negation(self):
        for word_id, text in [('w3', '所有任务。'), ('w4', '只需30次。')]:
            p = plan(); p['corrections'] = [{'word_id': word_id, 'text': text, 'reason': '自动猜测', 'evidence': ''}]
            with self.subTest(text=text), self.assertRaises(ValueError): compile_edit(transcript(), p)

    def test_corrections_protect_chinese_numbers_units_percent_and_qualifiers(self):
        for before, after in [('十分钟','一小时'),('大约3次','必须3次'),('收益1.5%','收益1.5'),
                              ('只能100元','只能100美元')]:
            t=transcript();t['words'][3]['text']=before
            p=plan();p['transcript_fingerprint']=fingerprint(t)
            p['corrections']=[{'word_id':'w4','text':after,'reason':'对音修订','evidence':'test source range'}]
            with self.subTest(before=before,after=after),self.assertRaises(ValueError):compile_edit(t,p)
        # The amount and currency may be separate ASR words; check the full
        # utterance, not just whether an isolated word happens to contain digits.
        t=transcript();t['words'][2]['text']='只需100';t['words'][3]['text']='元'
        p=plan();p['transcript_fingerprint']=fingerprint(t)
        p['corrections']=[{'word_id':'w4','text':'美元','reason':'猜测','evidence':'test source'}]
        with self.assertRaises(ValueError):compile_edit(t,p)

    def test_invalid_source_times_and_paths_rejected(self):
        for kind in ('nan', 'overlap', 'escape'):
            t = transcript()
            if kind == 'nan': t['words'][0]['start'] = float('nan')
            if kind == 'overlap': t['words'][1]['start'] = .4
            if kind == 'escape': t['media']['file'] = '../source.mov'
            p = plan()
            if kind == 'overlap': p['transcript_fingerprint'] = fingerprint(t)
            with self.subTest(kind=kind), self.assertRaises(ValueError): compile_edit(t, p)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'requires FFmpeg')
class EditMediaTests(unittest.TestCase):
    def test_real_cut_remap_pcm_clock_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / 'source.mov'
            subprocess.run(['ffmpeg', '-v', 'error', '-n', '-f', 'lavfi', '-i', 'testsrc2=s=64x96:r=30:d=3',
                            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=3',
                            '-c:v', 'libx264', '-c:a', 'pcm_s16le', str(source)], check=True)
            t = transcript(); t['media']['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            p = plan(); p.update(source_sha256=t['media']['sha256'], transcript_fingerprint=fingerprint(t))
            (root / 'transcript.json').write_text(json.dumps(t)); (root / 'plan.json').write_text(json.dumps(p))
            out = root / 'edited'
            result = render_edit(root / 'transcript.json', root / 'plan.json', out, normalize=False)
            with wave.open(str(out / 'voice.wav')) as audio:
                self.assertEqual(audio.getnframes(), result['frames'] * 1600)
            self.assertEqual(result['source_sha256_after'], t['media']['sha256'])
            project = json.loads((out / 'project.json').read_text())
            self.assertEqual(project['captions'], result['captions'])
            self.assertEqual(project['editing_stage'], 'needs_motion_planning')
            self.assertTrue((out / 'audio-copy.m4a').is_file())
            before = (out / 'edit.json').read_bytes()
            with self.assertRaises(FileExistsError): render_edit(root / 'transcript.json', root / 'plan.json', out)
            self.assertEqual((out / 'edit.json').read_bytes(), before)

