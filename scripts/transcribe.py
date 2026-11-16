#!/usr/bin/env python3
"""Copy a raw video into a new project and transcribe speech locally, with source-word IDs."""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import wave
from pathlib import Path


VIDEO_SUFFIXES = {'.mp4', '.mov', '.m4v', '.webm', '.mkv', '.avi', '.mts', '.m2ts'}


def finite(value, label):
    if isinstance(value, bool):
        raise ValueError(label + ' must be finite')
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(label + ' must be finite') from exc
    if not math.isfinite(number):
        raise ValueError(label + ' must be finite')
    return number


def _optional_number(value):
    if value in (None, '', 'N/A'):
        return None
    return finite(value, 'media timestamp')


def _duration(stream):
    duration = _optional_number(stream.get('duration'))
    if duration is None and stream.get('duration_ts') is not None and stream.get('time_base'):
        numerator, denominator = stream['time_base'].split('/')
        duration = finite(stream['duration_ts'], 'duration_ts') * float(numerator) / float(denominator)
    if duration is None:
        clock = (stream.get('tags') or {}).get('DURATION')
        if clock:
            hours, minutes, seconds = clock.split(':')
            duration = float(hours) * 3600 + float(minutes) * 60 + finite(seconds, 'duration')
    return duration if duration is not None and duration > 0 else None


def media_metadata(probe):
    """Use one common origin; never independently shift video and audio to zero."""
    streams = probe.get('streams') or []
    video = next((s for s in streams if s.get('codec_type') == 'video'
                  and not (s.get('disposition') or {}).get('attached_pic')), None)
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    if video is None:
        raise ValueError('Input has no usable video stream')
    if audio is None:
        raise ValueError('Input has no audio stream; a talking-head source with speech is required')
    container = probe.get('format') or {}
    format_start = _optional_number(container.get('start_time'))
    fallback_start = format_start if format_start is not None else 0.0
    starts = [_optional_number(s.get('start_time')) for s in (video, audio)]
    video_start, audio_start = [s if s is not None else fallback_start for s in starts]
    origin = min(video_start, audio_start)
    format_duration = _duration(container)
    format_end = None if format_duration is None else (format_start if format_start is not None else origin) + format_duration
    ends = []
    for stream, start in ((video, video_start), (audio, audio_start)):
        duration = _duration(stream)
        end = start + duration if duration is not None else format_end
        if end is None or end <= start:
            raise ValueError('Selected video/audio stream duration is unavailable')
        ends.append(end)
    duration = max(ends) - origin
    width, height = int(video.get('width') or 0), int(video.get('height') or 0)
    if min(width, height) <= 0 or duration <= 0:
        raise ValueError('Input video dimensions or duration are invalid')
    rotation = next((item['rotation'] for item in video.get('side_data_list') or []
                     if 'rotation' in item), (video.get('tags') or {}).get('rotate', 0))
    rotation_value = finite(rotation, 'rotation')
    if rotation_value % 90:
        raise ValueError('Only right-angle source rotation is supported')
    return {'duration': round(duration, 9), 'origin': origin, 'audio_start': audio_start,
            'video_start': video_start, 'width': width, 'height': height,
            'rotation': int(rotation_value) % 360}


def probe_media(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(path)], check=True, capture_output=True, text=True)
    return media_metadata(json.loads(result.stdout))


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def extract_audio(source, output):
    # Normalize the selected audio's first decoded sample, then add its original
    # A/V offset to recognized word times. Resampling also retains internal gaps.
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n', '-copyts',
                    '-i', str(source), '-map', '0:a:0', '-vn', '-af',
                    'asetpts=PTS-STARTPTS,aresample=16000:async=1:first_pts=0',
                    '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(output)],
                   check=True, capture_output=True)


def load_model(model, *, device, compute_type, allow_model_download):
    try:
        import onnxruntime
        onnxruntime.disable_telemetry_events()
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError('Local ASR dependency missing; install requirements-asr.txt in a virtual environment') from exc
    return WhisperModel(str(model), device=device, compute_type=compute_type,
                        cpu_threads=4, local_files_only=not allow_model_download)


def audio_samples(path):
    # FFmpeg already decoded the source. Passing PCM directly avoids decoding it
    # a second time through optional PyAV versions with different APIs.
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError('Local ASR dependency missing; install requirements-asr.txt') from exc
    with wave.open(str(path), 'rb') as handle:
        if (handle.getnchannels(), handle.getsampwidth(), handle.getframerate(), handle.getcomptype()) != (1, 2, 16000, 'NONE'):
            raise ValueError('ASR requires mono 16-bit PCM at 16000 Hz')
        pcm = handle.readframes(handle.getnframes())
    if not pcm:
        raise ValueError('Audio has no decoded samples')
    return (np.frombuffer(pcm, dtype='<i2').astype(np.float32) / np.float32(32768)).copy()


def _punctuation(text):
    return bool(text) and all(c.isspace() or unicodedata.category(c).startswith('P') for c in text)


def _probability(value, label):
    number = finite(value, label)
    if not 0 <= number <= 1:
        raise ValueError(label + ' must be between zero and one')
    return number


def transcript_fingerprint(media, language, words):
    payload = {'source_sha256': media['sha256'], 'language': language, 'words': words}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def transcript_payload(raw_segments, media, *, language):
    """Keep recognizer text, including fillers; confidence flags request later review."""
    offset = finite(media['audio_start'], 'audio_start') - finite(media['origin'], 'origin')
    duration = finite(media['duration'], 'duration')
    if offset < 0 or duration <= offset:
        raise ValueError('Invalid audio offset/duration')
    words, segments, review_ids, timing_adjustments = [], [], set(), []
    pending_prefix = ''
    for raw_segment in raw_segments:
        segment_words = []
        avg_logprob = finite(getattr(raw_segment, 'avg_logprob', 0.0), 'avg_logprob')
        if not -100 <= avg_logprob <= 0:
            raise ValueError('avg_logprob is outside the supported range')
        no_speech = _probability(getattr(raw_segment, 'no_speech_prob', 0.0), 'no_speech_prob')
        raw_words = getattr(raw_segment, 'words', None) or []
        if not raw_words and str(getattr(raw_segment, 'text', '') or '').strip():
            raise ValueError('ASR segment has text but no word timestamps')
        for raw_word in raw_words:
            text = str(getattr(raw_word, 'word', '') or '')
            if not text.strip():
                continue
            start = finite(getattr(raw_word, 'start', None), 'word start') + offset
            end = finite(getattr(raw_word, 'end', None), 'word end') + offset
            probability = _probability(getattr(raw_word, 'probability', 0.0), 'word probability')
            if end <= start:
                if end == start and _punctuation(text):
                    if words:
                        words[-1]['text'] += text
                    else:
                        pending_prefix += text
                    continue
                raise ValueError('Speech word has non-positive duration; cannot invent a word boundary')
            if start < 0 or end > duration + 0.02:
                raise ValueError('Recognized word is outside source media duration')
            if words and start < words[-1]['end'] - 1e-7:
                raise ValueError('Recognized words overlap or are out of order; inspect alignment')
            identifier = 'w%06d' % (len(words) + 1)
            if end > duration:
                timing_adjustments.append({'word_id': identifier, 'reason': 'ASR end clipped to actual media end',
                                           'recognized_end': end, 'media_end': duration})
                end = duration
                review_ids.add(identifier)
            item = {'id': identifier, 'start': round(start, 6), 'end': round(end, 6),
                    'text': pending_prefix + text, 'probability': probability}
            if item['end'] <= item['start']:
                raise ValueError('Word has no positive duration within the source media')
            pending_prefix = ''
            words.append(item)
            segment_words.append(identifier)
            if probability < 0.5 or avg_logprob < -1.0 or no_speech >= 0.6:
                review_ids.add(identifier)
        if segment_words:
            segments.append({'id': 'p%04d' % (len(segments) + 1), 'word_ids': segment_words,
                             'avg_logprob': avg_logprob, 'no_speech_prob': no_speech})
    if pending_prefix:
        raise ValueError('Punctuation has no speech interval')
    if not words:
        raise ValueError('No speech detected; no transcript was created')
    word_map = {w['id']: w for w in words}
    for item in segments:
        members = [word_map[key] for key in item['word_ids']]
        item.update(start=members[0]['start'], end=members[-1]['end'],
                    text=''.join(w['text'] for w in members).strip())
    return {'version': 1, 'language': language, 'media': dict(media), 'words': words,
            'fingerprint': transcript_fingerprint(media, language, words),
            'segments': segments,
            'metadata': {'speech_detected': True, 'recognition_review': 'unreviewed',
                         'review_word_ids': sorted(review_ids), 'timing_adjustments': timing_adjustments,
                         'notes': 'ASR confidence is a review signal, not proof of transcript accuracy.'}}


def transcript_markdown(payload):
    lines = ['# Source transcript', '',
             'ASR text is unreviewed. Word IDs and times refer to the copied source, before editing.', '',
             '| Word ID | Start (s) | End (s) | Recognized text | Review |',
             '| --- | ---: | ---: | --- | --- |']
    review = set(payload['metadata']['review_word_ids'])
    for word in payload['words']:
        text = word['text'].replace('|', '\\|').replace('\n', ' ')
        lines.append('| %s | %.3f | %.3f | %s | %s |' % (
            word['id'], word['start'], word['end'], text, 'check' if word['id'] in review else ''))
    lines += ['', '## Phrases', '']
    for phrase in payload['segments']:
        lines.append('[%.3f–%.3f] %s (%s–%s)' % (
            phrase['start'], phrase['end'], phrase['text'], phrase['word_ids'][0], phrase['word_ids'][-1]))
    return '\n'.join(lines) + '\n'


def transcribe(source, output, *, model='large-v3', language='zh', device='cpu',
               compute_type='int8', allow_model_download=False):
    raw_output = Path(output).expanduser().absolute()
    if raw_output.exists() or raw_output.is_symlink():
        raise FileExistsError('Output project exists; use a new directory')
    source = Path(source).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in VIDEO_SUFFIXES:
        raise ValueError('Input must be an ordinary video file with a supported extension')
    if not re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z0-9]+)?', language):
        raise ValueError('Language must be a language code, for example zh or en')
    media = probe_media(source)
    recognizer = load_model(model, device=device, compute_type=compute_type,
                            allow_model_download=allow_model_download)
    source_hash = file_hash(source)
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    output = raw_output.parent.resolve() / raw_output.name
    with tempfile.TemporaryDirectory(prefix='.yy-transcribe-', dir=str(output.parent)) as temporary:
        work = Path(temporary)
        source_name = 'source' + source.suffix.lower()
        copied = work / source_name
        shutil.copyfile(source, copied)
        if file_hash(copied) != source_hash:
            raise RuntimeError('Source changed during copy; retry from an unchanged input')
        wav = work / 'speech-16k.wav'
        extract_audio(copied, wav)
        raw_segments, info = recognizer.transcribe(audio_samples(wav), language=language, task='transcribe',
                                                  word_timestamps=True, beam_size=5, temperature=0.0,
                                                  condition_on_previous_text=False, vad_filter=True)
        media.update(file=source_name, sha256=source_hash)
        payload = transcript_payload(raw_segments, media, language=language)
        try:
            asr_version = importlib.metadata.version('faster-whisper')
        except importlib.metadata.PackageNotFoundError:
            asr_version = 'not installed (test double)'
        payload['metadata'].update(engine='faster-whisper', engine_version=asr_version,
                                   model=Path(str(model)).name, device=device, compute_type=compute_type,
                                   vad_filter=True, model_download_allowed=allow_model_download)
        probability = getattr(info, 'language_probability', None)
        if probability is not None:
            payload['metadata']['language_probability'] = _probability(probability, 'language_probability')
        (work / 'transcript.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (work / 'transcript.md').write_text(transcript_markdown(payload), encoding='utf-8')
        if file_hash(source) != source_hash:
            raise RuntimeError('Source changed during recognition; result was not published')
        # Reserve the destination before moving files, so a concurrent invocation
        # cannot silently replace an existing project, even an empty directory.
        output.mkdir(exist_ok=False)
        for name in (source_name, 'transcript.json', 'transcript.md'):
            os.rename(str(work / name), str(output / name))
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New project directory; never overwritten')
    parser.add_argument('--model', default='large-v3', help='Cached model name or local CTranslate2 model directory')
    parser.add_argument('--language', default='zh')
    parser.add_argument('--device', choices=('cpu', 'cuda', 'auto'), default='cpu')
    parser.add_argument('--compute-type', default='int8')
    network = parser.add_mutually_exclusive_group()
    network.add_argument('--local-files-only', action='store_true', help='Use only cached/local model files (default)')
    network.add_argument('--allow-model-download', action='store_true', help='Explicitly allow first-use model download')
    args = parser.parse_args()
    try:
        payload = transcribe(args.input, args.output, model=args.model, language=args.language,
                             device=args.device, compute_type=args.compute_type,
                             allow_model_download=args.allow_model_download)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print('Transcription stopped: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps({'status': 'TRANSCRIBED_UNREVIEWED', 'project': str(args.output),
                      'words': len(payload['words']), 'phrases': len(payload['segments']),
                      'review_words': len(payload['metadata']['review_word_ids']),
                      'source_sha256': payload['media']['sha256']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
