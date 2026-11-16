"""Exercise the edit renderer's actual PCM and frame clock at source boundaries."""
import array
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from edit import fingerprint, probe, render_edit
import edit as edit_module
from transcribe import media_metadata


def run(args):
    subprocess.run(args, check=True, capture_output=True)


def source_video(root, *, delayed_audio=False, excluded_sound=False, rotated=False):
    source = root / 'source.mov'
    temporary = root / 'unrotated.mov' if rotated else source
    audio = (r'aevalsrc=if(lt(t\,1.381)\,0\,0.8):s=48000:d=2.057'
             if excluded_sound else 'sine=frequency=440:sample_rate=48000:duration=2.057')
    command = ['ffmpeg', '-v', 'error', '-n', '-f', 'lavfi', '-i',
               'testsrc2=s=64x96:r=30:d=2.057', '-f', 'lavfi', '-i', audio]
    if delayed_audio:
        command += ['-af', 'asetpts=PTS+0.026/TB']
    command += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', str(temporary)]
    run(command)
    if rotated:
        run(['ffmpeg', '-v', 'error', '-n', '-display_rotation:v:0', '90',
             '-i', str(temporary), '-c', 'copy', str(source)])
    return source


def transcript_and_plan(root, source, words, *, kept_ids, omissions):
    metadata = media_metadata(probe(source))
    metadata.update(file=source.name, sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    transcript = {'version': 1, 'language': 'zh', 'media': metadata, 'words': words}
    transcript['fingerprint'] = fingerprint(transcript)
    plan = {'version': 1, 'mode': 'content-edit', 'source_sha256': metadata['sha256'],
            'transcript_fingerprint': transcript['fingerprint'], 'title': '边界验证', 'header': '时间保持一致',
            'goal': '保留选中范围并排除相邻声音',
            'segments': [{'id': 'retained', 'word_ids': kept_ids, 'reason': '保留验证范围', 'role': 'explanation'}],
            'omissions': omissions,
            'review': {'facts_and_qualifiers': 'pass', 'continuity': 'pass', 'transcript': 'pass',
                       'notes': ['Synthetic boundary fixture, not real speech review.'], 'unresolved': []}}
    transcript_path, plan_path = root / 'transcript.json', root / 'plan.json'
    transcript_path.write_text(json.dumps(transcript), encoding='utf-8')
    plan_path.write_text(json.dumps(plan), encoding='utf-8')
    return transcript, transcript_path, plan_path


def read_mono_pcm(path):
    with wave.open(str(path), 'rb') as handle:
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == 48000
        channels, count = handle.getnchannels(), handle.getnframes()
        samples = array.array('h', handle.readframes(count))
    if sys.byteorder != 'little':
        samples.byteswap()
    return count, samples[::channels]


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'requires FFmpeg/FFprobe')
class EditMediaBoundaryTests(unittest.TestCase):
    def check_clock_and_source(self, source, transcript, output, result):
        count, pcm = read_mono_pcm(output / 'voice.wav')
        self.assertEqual(count, result['frames'] * 1600)
        self.assertEqual(len(pcm), count)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), transcript['media']['sha256'])
        self.assertEqual(result['source_sha256_after'], transcript['media']['sha256'])
        actual_video = next(s for s in probe(output / 'presenter.mp4', count=True)['streams']
                            if s['codec_type'] == 'video')
        self.assertEqual(int(actual_video['nb_read_frames']), result['frames'])
        return pcm, actual_video

    def test_ceil_frame_padding_does_not_leak_excluded_neighbor_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = source_video(root, excluded_sound=True)
            words = [{'id': 'keep', 'start': 1.11, 'end': 1.281, 'text': '保留', 'probability': 1},
                     {'id': 'drop', 'start': 1.381, 'end': 1.9, 'text': '排除', 'probability': 1}]
            transcript, tpath, ppath = transcript_and_plan(root, source, words, kept_ids=['keep'],
                omissions=[{'word_ids': ['drop'], 'reason': '排除的邻接声音'}])
            output = root / 'edited'
            result = render_edit(tpath, ppath, output, normalize=False)
            clip = result['timeline'][0]
            self.assertAlmostEqual(clip['source_start'], 1.05)
            self.assertAlmostEqual(clip['source_end'], 1.381)
            self.assertEqual(result['frames'], 10)
            self.assertGreater(result['duration'], clip['source_end'] - clip['source_start'])
            pcm, _ = self.check_clock_and_source(source, transcript, output, result)
            self.assertLessEqual(max(map(abs, pcm)), 1,
                                 'ceil-frame tail padding reintroduced deliberately excluded source audio')
            before = (output / 'edit.json').read_bytes()
            with self.assertRaises(FileExistsError):
                render_edit(tpath, ppath, output, normalize=False)
            self.assertEqual((output / 'edit.json').read_bytes(), before)

    def test_audio_offset_and_non_frame_tail_survive_common_origin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = source_video(root, delayed_audio=True)
            media = media_metadata(probe(source))
            self.assertAlmostEqual(media['audio_start'] - media['origin'], .026, places=6)
            words = [{'id': 'all', 'start': .026, 'end': media['duration'] - .1,
                      'text': '完整保留音频和视频尾部', 'probability': 1}]
            transcript, tpath, ppath = transcript_and_plan(root, source, words,
                                                           kept_ids=['all'], omissions=[])
            output = root / 'edited'
            result = render_edit(tpath, ppath, output, normalize=False)
            self.assertEqual(result['frames'], math.ceil(media['duration'] * 30 - 1e-8))
            self.assertAlmostEqual(result['timeline'][0]['source_start'], 0)
            self.assertAlmostEqual(result['timeline'][0]['source_end'], media['duration'])
            self.assertAlmostEqual(result['words'][0]['start'], .026, places=6)
            pcm, _ = self.check_clock_and_source(source, transcript, output, result)
            first_nonzero = next(index for index, value in enumerate(pcm) if abs(value) > 1)
            self.assertLessEqual(abs(first_nonzero - round(.026 * 48000)), 2,
                                 'audio was independently reset to zero or shifted by a frame')
            self.assertEqual(max(map(abs, pcm[:round(.026 * 48000)])), 0)
            self.assertGreater(max(map(abs, pcm[round(2.07 * 48000):round(2.08 * 48000)])), 1000,
                               'source audio tail after the last original video frame was lost')
            self.assertLessEqual(max(map(abs, pcm[round(2.09 * 48000):])), 1,
                                 'padding past the actual source end must remain silent')

    def test_right_angle_source_rotation_is_applied_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = source_video(root, rotated=True)
            media = media_metadata(probe(source))
            self.assertEqual((media['width'], media['height']), (64, 96))
            self.assertIn(media['rotation'], (90, 270))
            words = [{'id': 'all', 'start': .1, 'end': 1.8, 'text': '旋转验证', 'probability': 1}]
            transcript, tpath, ppath = transcript_and_plan(root, source, words,
                                                           kept_ids=['all'], omissions=[])
            output = root / 'edited'
            result = render_edit(tpath, ppath, output, normalize=False)
            _, video = self.check_clock_and_source(source, transcript, output, result)
            self.assertEqual((video['width'], video['height']), (96, 64))
            rotations = [s.get('rotation', 0) for s in video.get('side_data_list', [])]
            self.assertTrue(all(float(rotation) % 360 == 0 for rotation in rotations),
                            'rotation metadata would rotate already transformed pixels a second time')

    def test_hlg_pixels_are_tone_mapped_to_bt709_with_pcm_clock_preserved(self):
        filters = subprocess.run(['ffmpeg', '-hide_banner', '-filters'], check=True,
                                 capture_output=True, text=True).stdout
        if not re.search(r'\bzscale\s', filters) or not re.search(r'\btonemap\s', filters):
            self.skipTest('HLG regression needs an FFmpeg build with zscale and tonemap')
        encoders = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], check=True,
                                  capture_output=True, text=True).stdout
        if not re.search(r'\blibx265\s', encoders):
            self.skipTest('HLG regression fixture needs a 10-bit libx265 encoder')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'source.mov'
            # Constant bright HLG code values expose a real transfer change;
            # merely changing metadata or rounding 10-bit to 8-bit cannot pass.
            run(['ffmpeg', '-v', 'error', '-n', '-f', 'lavfi', '-i',
                 'color=c=gray:s=64x96:r=30:d=1', '-f', 'lavfi', '-i',
                 'sine=frequency=440:sample_rate=48000:duration=1',
                 '-vf', 'format=yuv420p10le,geq=lum=768:cb=512:cr=512',
                 '-c:v', 'libx265', '-preset', 'ultrafast',
                 '-x265-params', 'log-level=error:lossless=1:pools=1:frame-threads=1:colorprim=9:transfer=18:colormatrix=9',
                 '-color_primaries', 'bt2020', '-color_trc', 'arib-std-b67',
                 '-colorspace', 'bt2020nc', '-color_range', 'tv',
                 '-c:a', 'pcm_s16le', str(source)])
            source_stream = next(s for s in probe(source)['streams'] if s['codec_type'] == 'video')
            self.assertEqual(source_stream['pix_fmt'], 'yuv420p10le')
            self.assertEqual(source_stream['color_transfer'], 'arib-std-b67')
            words = [{'id': 'all', 'start': .06, 'end': .9, 'text': 'HDR验证', 'probability': 1}]
            transcript, tpath, ppath = transcript_and_plan(root, source, words,
                                                           kept_ids=['all'], omissions=[])
            real_run = edit_module._run
            def without_zscale(args):
                if '-filters' in args:
                    return subprocess.CompletedProcess(args, 0, stdout=' .S tonemap V->V tone mapping\n', stderr='')
                return real_run(args)
            rejected_output = root / 'missing-filter-output'
            with mock.patch.object(edit_module, '_run', side_effect=without_zscale):
                with self.assertRaisesRegex(ValueError, 'HDR input requires FFmpeg with zscale and tonemap'):
                    render_edit(tpath, ppath, rejected_output, normalize=False)
            self.assertFalse(rejected_output.exists(), 'missing HDR filters must fail before creating output')
            output = root / 'edited'
            result = render_edit(tpath, ppath, output, normalize=False)
            pcm, video = self.check_clock_and_source(source, transcript, output, result)
            self.assertEqual(result['frames'], 30)
            self.assertGreater(max(map(abs, pcm)), 1000)
            self.assertEqual(tuple(video[k] for k in ('color_primaries', 'color_transfer', 'color_space')),
                             ('bt709', 'bt709', 'bt709'))
            self.assertEqual((video['width'], video['height']), (64, 96))
            def luma(path):
                raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
                                               '-map', '0:v:0', '-frames:v', '1', '-pix_fmt', 'yuv420p',
                                               '-f', 'rawvideo', 'pipe:1'])
                return raw[:64 * 96]
            before, after = luma(source), luma(output / 'presenter.mp4')
            self.assertNotEqual(before, after)
            # A same-codec control accounts for normal 10-to-8-bit conversion,
            # encoder rounding and relabeling, without applying a transfer curve.
            control = root / 'relabel-only.mp4'
            run(['ffmpeg', '-v', 'error', '-n', '-i', str(source), '-an', '-frames:v', '1',
                 '-vf', 'format=yuv420p', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
                 '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', str(control)])
            relabeled = luma(control)
            mean_change = sum(abs(a - b) for a, b in zip(relabeled, after)) / len(after)
            self.assertGreater(mean_change, 1,
                               'HLG pixels match the relabel-only control; no actual transfer transform occurred')
            self.assertEqual(result['color']['assumed_peak_nits'], 1000)


if __name__ == '__main__':
    unittest.main()
