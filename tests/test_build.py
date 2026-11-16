import copy
import importlib.util
import json
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('motion_build', ROOT / 'scripts/build.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def project():
    return {'version': 1, 'title': '示例', 'header': '测试', 'duration': 3,
            'fps': 30, 'media': {'presenter': 'assets/presenter.mp4', 'voice': 'assets/voice.m4a'},
            'captions': [{'start': 0, 'end': 3, 'text': '保留原文'}],
            'scenes': [{'id': 'scene-a', 'start': 0, 'eyebrow': '示例', 'title': '标题',
                        'layout': 'statement', 'items': [{'id': 'item-a', 'at': 0.5, 'title': '结论'}]}]}


class InputBoundaries(unittest.TestCase):
    def test_raw_edit_draft_requires_actual_scene_planning(self):
        data = project(); data['editing_stage'] = 'needs_motion_planning'
        with self.assertRaises(ValueError): builder.validate(data)
        data['editing_stage'] = 'motion_plan_reviewed'
        builder.validate(data)

    def test_unknown_style_rejected(self):
        data = project()
        data['style'] = 'not-installed'
        with self.assertRaises(ValueError):
            builder.validate(data)

    def test_unsupported_aspect_rejected_before_output_or_media_probe(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / 'project.json'
            source.write_text(json.dumps(project()), encoding='utf-8')
            output = base / 'new-project'
            with self.assertRaises(ValueError):
                builder.build(source, 'portrait', output, style='paper-ink')
            self.assertFalse(output.exists())

    def test_invalid_identity_and_presentation_rejected(self):
        for change in (lambda d: d.update(identity={'name': 123}),
                       lambda d: d['scenes'][0].update(presentation='invented'),
                       lambda d: d['scenes'][0].update(source_note={'bad': 'shape'})):
            data = project()
            change(data)
            with self.assertRaises(ValueError):
                builder.validate(data)

    def test_identity_panel_capacity_rejects_overflow(self):
        for identity in ({'name': '名' * 21}, {'role': '职' * 29},
                         {'lines': ['一', '二', '三', '四']}, {'lines': ['字' * 31]}):
            data = project()
            data.update(style='identity-blue', identity=identity)
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                builder.validate(data)

    def test_working_directory_cannot_be_a_sidecar_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            final = base / 'final.mp4'
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/render.py'),
                '--input', str(base / 'missing.json'), '--aspect', 'portrait',
                '--output', str(final), '--work-dir', str(final.with_suffix('.json'))],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(list(base.iterdir()), [])

    def test_valid_project(self):
        builder.validate(project())

    def test_reject_nonfinite_or_noninteger_timeline(self):
        for field, value in [('duration', float('inf')), ('duration', float('nan')),
                             ('duration', True), ('fps', 30.9), ('fps', True)]:
            data = project()
            data[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                builder.validate(data)

    def test_reject_unsafe_and_unknown_media(self):
        for media in [{'presenter': 'p.mp4'}, {'presenter': '/tmp/p.mp4', 'voice': 'v.m4a'},
                      {'presenter': '../p.mp4', 'voice': 'v.m4a'},
                      {'presenter': 'p.mp4', 'voice': 'v.m4a', '../../escape': 'x.txt'}]:
            data = project()
            data['media'] = media
            with self.subTest(media=media), self.assertRaises(ValueError):
                builder.validate(data)

    def test_reject_overlap_duplicate_id_and_outside_cue(self):
        mutations = [lambda d: d['captions'].append({'start': 1, 'end': 2, 'text': '重叠'}),
                     lambda d: d['scenes'][0]['items'][0].update(id='root'),
                     lambda d: d['scenes'][0]['items'][0].update(at=3)]
        for change in mutations:
            data = project()
            change(data)
            with self.assertRaises(ValueError):
                builder.validate(data)

    def test_reject_media_extensions_that_break_html_urls(self):
        for path in ['assets/clip.mp4#draft', 'assets/clip.mp4?download=1',
                     'assets/clip.mp4" onerror="alert(1)']:
            data = project()
            data['media']['presenter'] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                builder.validate(data)

    def test_existing_output_preserved_before_media_probe(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / 'project.json'
            source.write_text(json.dumps(project()), encoding='utf-8')
            target = base / 'existing'
            target.mkdir()
            marker = target / 'keep.txt'
            marker.write_text('untouched')
            with self.assertRaises(FileExistsError):
                builder.build(source, 'portrait', target)
            self.assertEqual(marker.read_text(), 'untouched')

    def test_symlink_cannot_escape_source_project(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / 'source'
            source.mkdir()
            external = base / 'external.mp4'
            external.write_bytes(b'not-media')
            (source / 'presenter.mp4').symlink_to(external)
            with self.assertRaises(ValueError):
                builder.resolve_media(source, 'presenter.mp4')

    def test_escape_user_copy(self):
        self.assertEqual(builder.marked('<script>&内容', ['内容']),
                         '&lt;script&gt;&amp;<span class="accent">内容</span>')


if __name__ == '__main__':
    unittest.main()
