#!/usr/bin/env python3
"""Render an Agent-authored, source-word-bound content edit; never overwrite media."""
import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import unicodedata
import wave
from pathlib import Path
from compare_speech import _keep as meaningful_character, protected_tokens


def fingerprint(transcript):
    value = {'source_sha256': transcript['media']['sha256'],
             'language': transcript.get('language', 'zh'), 'words': transcript['words']}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def finite(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(label + ' must be a finite number')
    return float(value)


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip(): raise ValueError(label + ' is required')
    return value.strip()


def join_words(words):
    """Preserve ASR punctuation/spaces, adding a separator only between Latin words."""
    text = ''
    for word in words:
        part = word['text'] if isinstance(word, dict) else word
        if text and part and re.search(r'[A-Za-z0-9]$', text) and re.match(r'[A-Za-z0-9]', part):
            text += ' '
        text += part
    return text.strip()


def _captions(words, duration, max_chars=20, max_seconds=3.8):
    result, group = [], []
    def flush():
        if not group: return
        result.append({'start': round(group[0]['start'], 6), 'end': round(min(group[-1]['end'], duration), 6),
                       'text': join_words(group)})
        group.clear()
    for word in words:
        if group and (len(join_words(group + [word])) > max_chars or
                      word['end'] - group[0]['start'] > max_seconds or
                      word['start'] - group[-1]['end'] > .45 or
                      word['clip_id'] != group[-1]['clip_id']): flush()
        group.append(word)
        if re.search(r'[。！？!?；;]$', word['text'].strip()): flush()
    flush()
    return result


def planned_captions(words, groups):
    """Let the Agent choose readable groups, while source IDs determine all times."""
    if not isinstance(groups, list) or not groups: raise ValueError('caption_groups must be nonempty')
    lookup = {w['source_word_id']: w for w in words}
    covered, captions = [], []
    def visible(text):
        raw = unicodedata.normalize('NFKC', text)
        return ''.join(c for i,c in enumerate(raw) if meaningful_character(raw,i))
    for group in groups:
        ids = group.get('word_ids')
        if not isinstance(ids,list) or not ids or any(w not in lookup for w in ids):
            raise ValueError('caption_groups need actual kept word IDs')
        selected = [lookup[w] for w in ids]
        if len({w['clip_id'] for w in selected})!=1: raise ValueError('A caption cannot cross an edit cut')
        original = join_words(selected); text = group.get('text', original)
        nonempty(text, 'caption group text')
        def latin_words(value):
            normalized=unicodedata.normalize('NFKC',value).replace('’',"'")
            return re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*",normalized)
        if visible(original)!=visible(text) or latin_words(original)!=latin_words(text) or re.findall(r'\d+(?:[.,]\d+)*',original)!=re.findall(r'\d+(?:[.,]\d+)*',text):
            raise ValueError('Caption grouping may add punctuation, not rewrite speech or numbers')
        captions.append({'start':round(selected[0]['start'],6),'end':round(selected[-1]['end'],6),'text':text})
        covered.extend(ids)
    if covered != [w['source_word_id'] for w in words]:
        raise ValueError('Caption groups must cover every kept word once in output order')
    return captions


def compile_edit(transcript, plan, fps=30):
    if type(fps) is not int or fps not in (24, 30, 60): raise ValueError('fps must be 24, 30 or 60')
    if transcript.get('version') != 1 or plan.get('version') != 1 or plan.get('mode') != 'content-edit':
        raise ValueError('Expected transcript/plan version=1 and mode=content-edit')
    media = transcript.get('media', {})
    path = Path(nonempty(media.get('file'), 'media.file'))
    if path.is_absolute() or '..' in path.parts or '\\' in str(path) or ':' in str(path):
        raise ValueError('Source media must be relative to the transcript directory')
    if path.suffix.lower() not in ('.mp4', '.mov', '.m4v', '.webm', '.mkv', '.avi', '.mts', '.m2ts'):
        raise ValueError('Unsupported source video extension')
    source_hash = media.get('sha256', '')
    if not re.fullmatch('[a-f0-9]{64}', source_hash): raise ValueError('Invalid source SHA256')
    if plan.get('source_sha256') != source_hash: raise ValueError('Edit plan belongs to a different source')
    actual_fingerprint = fingerprint(transcript)
    if plan.get('transcript_fingerprint') != actual_fingerprint:
        raise ValueError('Edit plan belongs to a different transcript; re-read source words')
    if transcript.get('fingerprint', actual_fingerprint) != actual_fingerprint:
        raise ValueError('Transcript fingerprint changed')
    duration = finite(media.get('duration'), 'media.duration')
    if duration <= 0: raise ValueError('Positive media duration required')
    for key in ('origin', 'audio_start', 'video_start'): finite(media.get(key), 'media.' + key)
    words = transcript.get('words')
    if not isinstance(words, list) or not words: raise ValueError('No source speech words')
    by_id, positions, last_end = {}, {}, 0.0
    for i, word in enumerate(words):
        wid = nonempty(word.get('id'), 'word.id')
        if wid in by_id: raise ValueError('Duplicate source word ID')
        start, end = finite(word.get('start'), 'word.start'), finite(word.get('end'), 'word.end')
        if not last_end - 1e-6 <= start < end <= duration + 1e-6:
            raise ValueError('Source word times overlap or exceed source duration')
        nonempty(word.get('text'), 'word.text')
        by_id[wid], positions[wid], last_end = word, i, end
    title, header, goal = [nonempty(plan.get(k), k) for k in ('title', 'header', 'goal')]
    review = plan.get('review')
    if not isinstance(review, dict): raise ValueError('Agent semantic/transcript review is required')
    for key in ('facts_and_qualifiers', 'continuity', 'transcript'):
        if review.get(key) not in ('pass', 'needs_review'): raise ValueError('Missing review.' + key)
    for key in ('notes', 'unresolved'):
        if not isinstance(review.get(key), list) or any(not isinstance(x, str) for x in review[key]):
            raise ValueError('review.' + key + ' must be a text array')
    segments, omissions = plan.get('segments'), plan.get('omissions')
    if not isinstance(segments, list) or not segments or not isinstance(omissions, list):
        raise ValueError('Nonempty segments and explicit omissions list are required')
    seen, clip_ids = set(), set()
    for kind, groups in (('segment', segments), ('omission', omissions)):
        for group in groups:
            nonempty(group.get('reason'), kind + '.reason')
            ids = group.get('word_ids')
            if not isinstance(ids, list) or not ids: raise ValueError(kind + '.word_ids required')
            for wid in ids:
                if wid not in by_id or wid in seen: raise ValueError('Unknown or repeated word ID: ' + str(wid))
                seen.add(wid)
            if kind == 'segment':
                cid = group.get('id', '')
                if not re.fullmatch('[A-Za-z][A-Za-z0-9_-]*', cid) or cid in clip_ids:
                    raise ValueError('Unique safe segment IDs required')
                clip_ids.add(cid); nonempty(group.get('role'), 'segment.role')
                indexes = [positions[w] for w in ids]
                if indexes != list(range(indexes[0], indexes[0] + len(indexes))):
                    raise ValueError('Each segment must contain consecutive source words in source order')
    if seen != set(by_id): raise ValueError('Every source word must be kept or have an omission reason')
    corrections = {}
    for correction in plan.get('corrections', []):
        wid = correction.get('word_id')
        if wid not in by_id or wid in corrections: raise ValueError('Unknown or duplicate correction word')
        value = nonempty(correction.get('text'), 'correction.text')
        nonempty(correction.get('reason'), 'correction.reason')
        nonempty(correction.get('evidence'), 'correction.evidence: identify source audio evidence')
        corrections[wid] = value
    original_text = join_words(words)
    corrected_text = join_words([corrections.get(word['id'],word['text']) for word in words])
    if protected_tokens(original_text) != protected_tokens(corrected_text):
        raise ValueError('Correction changes a number/unit/negation/qualifier; mark unresolved instead')
    timeline, output_words, frames, risks = [], [], 0, []
    for segment in segments:
        selected = [by_id[w] for w in segment['word_ids']]
        first, last = positions[selected[0]['id']], positions[selected[-1]['id']]
        before = finite(segment.get('padding_before', .06), 'padding_before')
        after = finite(segment.get('padding_after', .10), 'padding_after')
        if not 0 <= before <= .5 or not 0 <= after <= .5: raise ValueError('Cut padding must be 0–0.5 seconds')
        start = max(0, selected[0]['start'] - before, words[first-1]['end'] if first else 0)
        end = min(duration, selected[-1]['end'] + after, words[last+1]['start'] if last+1 < len(words) else duration)
        count = max(1, math.ceil((end-start)*fps - 1e-8))
        offset, output_end = frames/fps, (frames+count)/fps
        margin_before, margin_after = selected[0]['start']-start, end-selected[-1]['end']
        if margin_before < .03 or margin_after < .03:
            risks.append({'clip_id': segment['id'], 'kind': 'tight_cut',
                          'message': 'ASR word boundaries have <30ms acoustic margin; review actual audio at this cut'})
        timeline.append({'id': segment['id'], 'source_start': start, 'source_end': end,
                         'start_frame': frames, 'end_frame': frames+count,
                         'start': offset, 'end': output_end, 'role': segment['role'],
                         'reason': segment['reason'], 'word_ids': segment['word_ids'],
                         'text': join_words([corrections.get(w['id'], w['text']) for w in selected])})
        for word in selected:
            output_words.append({'source_word_id': word['id'], 'clip_id': segment['id'],
                                 'source_start': word['start'], 'source_end': word['end'],
                                 'start': round(offset+word['start']-start, 9),
                                 'end': round(min(output_end, offset+word['end']-start), 9),
                                 'source_text': word['text'], 'text': corrections.get(word['id'], word['text'])})
        frames += count
    ready = all(review[k] == 'pass' for k in ('facts_and_qualifiers', 'continuity', 'transcript')) and not review['unresolved']
    return {'version': 1, 'mode': 'content-edit', 'title': title, 'header': header, 'goal': goal,
            'source_sha256': source_hash, 'transcript_fingerprint': actual_fingerprint,
            'source_duration': duration, 'duration': frames/fps, 'fps': fps, 'frames': frames,
            'timeline': timeline, 'words': output_words,
            'captions': planned_captions(output_words,plan['caption_groups']) if 'caption_groups' in plan else _captions(output_words, frames/fps),
            'omissions': omissions, 'corrections': plan.get('corrections', []), 'agent_review': review,
            'cut_risks': risks, 'status': 'candidate_for_final_review' if ready else 'needs_review',
            'full_av_review': 'not performed by this script'}


def _run(args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode: raise RuntimeError('External command failed: ' + result.stderr[-6000:])
    return result


def probe(path, count=False):
    return json.loads(_run(['ffprobe', '-v', 'error', *(['-count_frames'] if count else []),
                            '-show_streams', '-show_format', '-of', 'json', str(path)]).stdout)


def source_streams(info):
    streams=info.get('streams',[])
    video=next((s for s in streams if s.get('codec_type')=='video'
                and not s.get('disposition',{}).get('attached_pic')),None)
    audio=next((s for s in streams if s.get('codec_type')=='audio'),None)
    if video is None or audio is None:raise ValueError('Raw talking-head video needs usable video and speech audio')
    return video,audio


def _write_srt(captions, path):
    def stamp(value):
        ms = round(value*1000); seconds, ms = divmod(ms, 1000)
        minutes, seconds = divmod(seconds, 60); hours, minutes = divmod(minutes, 60)
        return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'
    with path.open('x', encoding='utf-8') as stream:
        for i, cue in enumerate(captions, 1):
            stream.write(f'{i}\n{stamp(cue["start"])} --> {stamp(cue["end"])}\n{cue["text"]}\n\n')


def render_edit(transcript_path, plan_path, output, fps=30, max_edge=1920, normalize=True, ffmpeg='ffmpeg'):
    transcript_path, plan_path, output = Path(transcript_path).resolve(), Path(plan_path).resolve(), Path(output)
    if output.exists() or output.is_symlink(): raise FileExistsError('Edit output exists; use a new directory')
    if max_edge < 64 or max_edge > 7680: raise ValueError('max-edge must be 64–7680')
    transcript, plan = json.loads(transcript_path.read_text()), json.loads(plan_path.read_text())
    doc = compile_edit(transcript, plan, fps)
    source = (transcript_path.parent / transcript['media']['file']).resolve()
    if transcript_path.parent not in source.parents or not source.is_file():
        raise ValueError('Source media escapes project or is missing')
    if digest(source) != doc['source_sha256']: raise ValueError('Source content changed since transcription')
    info = probe(source)
    # Use the actual source clock, not an editable JSON assertion about stream origin.
    selected = source_streams(info)
    origin = min(float(s.get('start_time', info['format'].get('start_time', 0))) for s in selected)
    if abs(origin-transcript['media']['origin']) > .002: raise ValueError('Source timeline origin changed')
    def run(args):
        return _run([ffmpeg, *args[1:]] if args[0]=='ffmpeg' else args)
    source_video = selected[0]
    transfer = source_video.get('color_transfer')
    hdr = transfer in ('arib-std-b67', 'smpte2084')
    color_filter, color_options = '', []
    color = {'source_transfer': transfer or 'unspecified', 'conversion': 'unchanged SDR'}
    if hdr:
        filters = run(['ffmpeg','-hide_banner','-filters']).stdout
        if not re.search(r'\bzscale\s', filters) or not re.search(r'\btonemap\s', filters):
            raise ValueError('HDR input requires FFmpeg with zscale and tonemap; select a suitable build with --ffmpeg')
        if source_video.get('color_primaries') != 'bt2020' or source_video.get('color_space') != 'bt2020nc':
            raise ValueError('Unsupported HDR color metadata; inspect source before conversion')
        # A documented 1000-nit base-layer assumption, not Dolby Vision RPU
        # processing. Never turn HLG/PQ into 8-bit SDR by merely relabeling it.
        color_filter = (f'zscale=pin=bt2020:tin={transfer}:min=bt2020nc:t=linear:npl=100,'
                        'format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0:peak=10,'
                        'zscale=t=bt709:m=bt709:r=limited:dither=error_diffusion,format=yuv420p,')
        color_options = ['-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-color_range','tv']
        color.update(conversion='HDR base layer -> linear -> Hable -> SDR BT.709',
                     assumed_peak_nits=1000, dynamic_hdr_metadata='not applied; inspect actual skin/highlights')
    output.mkdir(parents=True, exist_ok=False); clips = output / 'clips'; clips.mkdir()
    for index, clip in enumerate(doc['timeline']):
        start, end = clip['source_start'], clip['source_end']
        nframes = clip['end_frame']-clip['start_frame']; duration = nframes/fps
        samples = nframes*(48000//fps)
        scale = f"scale=w='min(iw,{max_edge})':h='min(ih,{max_edge})':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1"
        # Trim audio before grid padding. Extending the source end to ceil(frame)
        # can leak the first phoneme of a deliberately excluded neighboring take.
        video = (f'[0:{selected[0]["index"]}]setpts=PTS-{origin:.9f}/TB,fps={fps}:start_time=0,'
                 f'tpad=stop_mode=clone:stop_duration={duration:.9f},'
                 f'trim=start={start:.9f}:end={end:.9f},setpts=PTS-{start:.9f}/TB,'
                 f'fps={fps}:start_time=0,tpad=stop_mode=clone:stop_duration={duration:.9f},'
                 f'trim=end_frame={nframes},setpts=N/({fps}*TB),{color_filter}{scale}[v]')
        # Tiny fades sit inside the retained breathing margin and do not overlap
        # clips or change the word-to-output timeline.
        fade = min(.008, max(0, (clip['end']-clip['start'])/4))
        audio = (f'[0:{selected[1]["index"]}]asetpts=PTS-{origin:.9f}/TB,aresample=48000:first_pts=0,'
                 f'atrim=start={start:.9f}:end={end:.9f},asetpts=PTS-{start:.9f}/TB,'
                 f'aformat=sample_rates=48000:channel_layouts=stereo,apad=whole_len={samples},'
                 f'atrim=end_sample={samples},asetpts=N/SR/TB,'
                 f'afade=t=in:st=0:d={fade:.6f},afade=t=out:st={max(0,duration-fade):.9f}:d={fade:.6f}[a]')
        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n', '-copyts', '-i', str(source),
              '-filter_complex', video+';'+audio, '-map', '[v]', '-map', '[a]', '-c:v', 'libx264',
              '-preset', 'veryfast', '-crf', '18', '-g', str(fps), '-keyint_min', str(fps),
              '-sc_threshold', '0', '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le',
              '-metadata:s:v:0', 'rotate=0', *color_options, str(clips / f'clip-{index:04d}.mkv')])
    listing = output/'concat.txt'
    listing.write_text(''.join(f"file clips/clip-{i:04d}.mkv\n" for i in range(len(doc['timeline']))))
    intermediate = output/'edited-intermediate.mkv'
    run(['ffmpeg', '-v', 'error', '-n', '-f', 'concat', '-safe', '1', '-i', str(listing), '-c', 'copy', str(intermediate)])
    voice, total_samples = output/'voice.wav', doc['frames']*(48000//fps)
    loudness = {'applied': False}
    filters = []
    if normalize:
        measurement = run(['ffmpeg', '-hide_banner', '-i', str(intermediate), '-vn', '-af',
                            'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-']).stderr
        match = re.search(r'\{\s*"input_i".*?\}', measurement, re.S)
        if not match: raise ValueError('Loudness measurement unavailable')
        values = json.loads(match.group())
        if not all(math.isfinite(float(values[k])) for k in ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset')):
            raise ValueError('No measurable speech loudness; inspect source audio')
        filters.append('loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:' + ':'.join(
            k+'='+values[v] for k,v in [('measured_I','input_i'),('measured_TP','input_tp'),
                                      ('measured_LRA','input_lra'),('measured_thresh','input_thresh'),('offset','target_offset')]))
        loudness = {'applied': True, 'target_lufs': -16, 'target_true_peak_db': -1.5, 'measurements': values}
    filters.extend(['aresample=48000', f'apad=whole_len={total_samples}', f'atrim=end_sample={total_samples}', 'asetpts=N/SR/TB'])
    run(['ffmpeg', '-v', 'error', '-n', '-i', str(intermediate), '-vn', '-af', ','.join(filters),
          '-ac', '2', '-ar', '48000', '-c:a', 'pcm_s16le', str(voice)])
    with wave.open(str(voice)) as audio:
        if audio.getnframes() != total_samples: raise ValueError('Edited audio clock differs from video frames')
    presenter = output/'presenter.mp4'
    run(['ffmpeg', '-v', 'error', '-n', '-i', str(intermediate), '-map', '0:v:0', '-an',
          '-c:v', 'copy', '-movflags', '+faststart', str(presenter)])
    run(['ffmpeg', '-v', 'error', '-n', '-i', str(voice), '-c:a', 'aac', '-b:a', '192k',
          '-movflags', '+faststart', str(output/'audio-copy.m4a')])
    actual = next(s for s in probe(presenter, count=True)['streams'] if s['codec_type']=='video')
    if int(actual['nb_read_frames']) != doc['frames']: raise ValueError('Edited video frame count differs')
    run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(presenter), '-f', 'null', '-'])
    if hdr and any(actual.get(k)!='bt709' for k in ('color_space','color_transfer','color_primaries')):
        raise ValueError('HDR tone mapping did not produce the expected SDR BT.709 tags')
    _write_srt(doc['captions'], output/'captions.srt')
    doc.update(source_sha256_after=digest(source), loudness=loudness, color=color,
               technical_check='PASS: frame count, full video decode, exact PCM sample clock')
    if doc['source_sha256_after'] != doc['source_sha256']: raise ValueError('Source changed while editing')
    (output/'edit.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2)+'\n')
    shutil.copy2(transcript_path, output/'source-transcript.json'); shutil.copy2(plan_path, output/'edit-plan.json')
    project = {'version': 1, 'title': doc['title'], 'header': doc['header'], 'header_note': '',
               'editing_stage': 'needs_motion_planning', 'duration': doc['duration'], 'fps': fps,
               'media': {'presenter': 'presenter.mp4', 'voice': 'voice.wav', 'audio_copy': 'audio-copy.m4a'},
               'captions': doc['captions'], 'emphasis_words': [],
               'scenes': [{'id': 'opening', 'start': 0, 'eyebrow': '内容精剪', 'title': doc['title'],
                           'layout': 'statement', 'items': [{'id': 'opening-point', 'at': 0,
                                                           'title': doc['header']}]}]}
    (output/'project.json').write_text(json.dumps(project, ensure_ascii=False, indent=2)+'\n')
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transcript', required=True, type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--fps', type=int, choices=(24,30,60), default=30)
    parser.add_argument('--max-edge', type=int, default=1920)
    parser.add_argument('--skip-normalize', action='store_true')
    parser.add_argument('--ffmpeg', default='ffmpeg', help='FFmpeg executable; HDR needs zscale and tonemap')
    args = parser.parse_args()
    doc = render_edit(args.transcript, args.plan, args.output, args.fps, args.max_edge, not args.skip_normalize, args.ffmpeg)
    print(json.dumps({k: doc[k] for k in ('status','duration','frames','fps','technical_check','cut_risks')},
                     ensure_ascii=False, indent=2))
    print('Edit complete. Agent must finish scene planning in project.json before motion rendering.')


if __name__ == '__main__': main()
