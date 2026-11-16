#!/usr/bin/env python3
"""Compare an edit's expected speech with a fresh ASR transcript of its actual final video."""
import argparse
import bisect
import difflib
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path


LIMITS = ('ASR round-trip consistency only; not proof of verbatim speech accuracy, '
          'edit semantics, lip sync, full listening review or publishing readiness.')
CN_QUALIFIERS = ('不超过', '不少于', '不低于', '不高于', '并非', '至少', '至多', '最多',
                 '最少', '超过', '低于', '高于', '大约', '大概', '如果', '除非', '只有',
                 '仅当', '上限', '下限', '可能', '也许', '或许', '一定', '必须', '全部', '所有', '部分',
                 '通常', '一般', '总是', '从不', '有时', '偶尔', '不', '没', '未', '无',
                 '非', '只', '仅', '约')
UNITS = (r'(?:百分之|人民币|万美元|美元|万元|亿元|个月|小时|分钟|毫秒|千米|公里|厘米|毫米|'
         r'千克|公斤|毫克|毫升|元|万|亿|千|百|天|年|月|日|时|分|秒|次|倍|米|克|吨|升|'
         r'%|‰|‱|°[cf]?|km|cm|mm|kg|mg|ml|ms|gb|mb|kb|hz|kw|w|m|g|l|s)(?:/[a-z]+)?')
NUMBER = re.compile(r'[¥$€£]?[+−-]?\d+(?:[.,:/-]\d+)*(?:' + UNITS + r')?')
CN_NUMBER = re.compile(r'[零〇一二三四五六七八九十百千万亿两]+(?:点[零〇一二三四五六七八九]+)?(?:' + UNITS + r')?')
CN_QUALIFIER = re.compile('|'.join(re.escape(x) for x in CN_QUALIFIERS))
EN_QUALIFIER = re.compile(
    r"\b(?:at\s+least|at\s+most|more\s+than|less\s+than|up\s+to|"
    r"(?:ca|do|does|did|is|are|was|were|wo|should|could|would|must|has|have|had|need)n['’]t|"
    r"cannot|no|not|never|none|without|unless|only|if|can|could|would|should|may|might|must|always|sometimes|"
    r"generally|approximately|about)\b")


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): value.update(block)
    return value.hexdigest()


def finite(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(label + ' must be finite')
    return float(value)


def _neighbor(raw, index, step):
    index += step
    while 0 <= index < len(raw):
        if not raw[index].isspace(): return raw[index]
        index += step
    return ''


def _keep(raw, index):
    char = raw[index]
    if char.isspace(): return False
    if not unicodedata.category(char).startswith('P'): return True
    # Decimal points, ranges, negative signs, percentages and unit slashes carry
    # meaning. Treating 1.5% as 15 or 10-15 as 1015 would hide a speech error.
    before, after = _neighbor(raw, index, -1), _neighbor(raw, index, 1)
    if char in '%‰‱': return True
    if char in '.,:/' and before.isdecimal() and after.isdecimal(): return True
    if char == '-' and after.isdecimal(): return True
    if char == '/' and before.isascii() and before.isalpha() and after.isascii() and after.isalpha(): return True
    if char == '!' and after == '=': return True
    return False


def _stream(words, duration, expected):
    if not isinstance(words, list) or not words: raise ValueError('Speech words are required')
    raw_parts, raw_refs, seen, previous_end = [], [], set(), 0.0
    for word in words:
        if not isinstance(word, dict): raise ValueError('Speech words must be objects')
        identifier = word.get('source_word_id' if expected else 'id')
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError('Speech word IDs must be unique nonempty strings')
        start, end = finite(word.get('start'), 'word.start'), finite(word.get('end'), 'word.end')
        if not previous_end - 1e-6 <= start < end <= duration + 1e-6:
            raise ValueError('Speech word times overlap or exceed media duration')
        text = word.get('text')
        if not isinstance(text, str) or not text.strip(): raise ValueError('Speech word text is required')
        ref = {'id': identifier, 'start': start, 'end': end, 'text': text}
        if expected and word.get('clip_id') is not None: ref['clip_id'] = word['clip_id']
        normalized = unicodedata.normalize('NFKC', text).casefold()
        if raw_parts:
            raw_parts.append(' '); raw_refs.append(None)
        raw_parts.append(normalized); raw_refs.extend([ref] * len(normalized))
        seen.add(identifier); previous_end = end
    raw = ''.join(raw_parts)
    indexes = [i for i in range(len(raw)) if _keep(raw, i)]
    text = ''.join(raw[i] for i in indexes)
    if not text: raise ValueError('No speech characters remain after normalization')
    return {'text': text, 'refs': [raw_refs[i] for i in indexes],
            'raw': raw, 'raw_indexes': indexes}


def _protected(stream):
    spans = []
    for kind, pattern in (('number_or_unit', NUMBER), ('number_or_unit', CN_NUMBER),
                          ('negation_or_qualifier', CN_QUALIFIER)):
        for match in pattern.finditer(stream['text']):
            spans.append({'kind': kind, 'start': match.start(), 'end': match.end(), 'text': match.group()})
    for match in EN_QUALIFIER.finditer(stream['raw']):
        start = bisect.bisect_left(stream['raw_indexes'], match.start())
        end = bisect.bisect_left(stream['raw_indexes'], match.end())
        if start < end:
            spans.append({'kind': 'negation_or_qualifier', 'start': start, 'end': end, 'text': match.group()})
    return spans


def protected_tokens(text):
    """Shared guard for subtitle corrections, including tokens crossing ASR words."""
    raw = unicodedata.normalize('NFKC', text).casefold()
    indexes = [i for i in range(len(raw)) if _keep(raw, i)]
    stream = {'raw':raw, 'raw_indexes':indexes, 'text':''.join(raw[i] for i in indexes)}
    return [(span['kind'],span['text']) for span in _protected(stream)]


def _changed_protected(spans, start, end, side):
    return [{'side': side, 'kind': span['kind'], 'text': span['text'],
             'normalized_start': span['start'], 'normalized_end': span['end']} for span in spans
            if (start < span['end'] and end > span['start']) or
               (start == end and span['start'] < start < span['end'])]


def _location(stream, start, end):
    result = {'normalized_start': start, 'normalized_end': end,
              'text': stream['text'][start:end], 'word_ids': []}
    refs, seen = [], set()
    for ref in stream['refs'][start:end]:
        if ref['id'] not in seen:
            refs.append(dict(ref)); seen.add(ref['id'])
    if refs:
        result.update(word_ids=[r['id'] for r in refs], start=refs[0]['start'], end=refs[-1]['end'], words=refs)
    else:
        # Missing speech has no actual spoken interval. Give neighboring ASR
        # words as anchors rather than fabricate a word-level timestamp.
        result['anchor'] = {
            'after': dict(stream['refs'][start - 1]) if start > 0 else None,
            'before': dict(stream['refs'][start]) if start < len(stream['refs']) else None}
    return result


def compare_speech(edit, transcript, video, threshold=.97):
    threshold = finite(threshold, 'threshold')
    if not 0 <= threshold <= 1: raise ValueError('threshold must be between zero and one')
    if edit.get('version') != 1 or edit.get('mode') != 'content-edit' or transcript.get('version') != 1:
        raise ValueError('Expected version=1 edit and transcript, with mode=content-edit')
    video = Path(video).expanduser().resolve(strict=True)
    if not video.is_file(): raise ValueError('Actual final video must be a file')
    actual_hash = digest(video)
    media = transcript.get('media')
    if not isinstance(media, dict) or media.get('sha256') != actual_hash:
        raise ValueError('Transcript SHA256 belongs to a different or changed final video')
    expected_duration = finite(edit.get('duration'), 'edit.duration')
    actual_duration = finite(media.get('duration'), 'transcript.media.duration')
    if min(expected_duration, actual_duration) <= 0: raise ValueError('Positive speech duration required')
    expected = _stream(edit.get('words'), expected_duration, True)
    actual = _stream(transcript.get('words'), actual_duration, False)
    if transcript.get('fingerprint'):
        payload = {'source_sha256': actual_hash, 'language': transcript.get('language', 'zh'), 'words': transcript['words']}
        fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                               separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        if transcript['fingerprint'] != fingerprint: raise ValueError('ASR transcript fingerprint changed')
    matcher = difflib.SequenceMatcher(None, expected['text'], actual['text'], autojunk=False)
    protected_expected, protected_actual = _protected(expected), _protected(actual)
    counts = {'matches': 0, 'substitutions': 0, 'deletions': 0, 'insertions': 0}
    mismatches = []
    for operation, a, b, c, d in matcher.get_opcodes():
        left, right = b - a, d - c
        if operation == 'equal':
            counts['matches'] += left; continue
        substitution = min(left, right) if operation == 'replace' else 0
        counts['substitutions'] += substitution
        counts['deletions'] += left - substitution
        counts['insertions'] += right - substitution
        protected = (_changed_protected(protected_expected, a, b, 'expected') +
                     _changed_protected(protected_actual, c, d, 'actual'))
        mismatches.append({'id': 'm%04d' % (len(mismatches) + 1), 'operation': operation,
                           'expected': _location(expected, a, b), 'actual': _location(actual, c, d),
                           'protected_changes': protected})
    similarity = matcher.ratio()
    protected_changes = sum(bool(m['protected_changes']) for m in mismatches)
    reasons = []
    if similarity < threshold: reasons.append('Normalized speech similarity is below the selected threshold')
    if protected_changes: reasons.append('A mismatch changes a number, unit, negation or qualifier')
    return {'version': 1, 'status': 'NEEDS_REVIEW' if reasons else 'PASS',
            'check': 'ASR round-trip speech consistency', 'threshold': threshold,
            'similarity': similarity, 'counts': counts,
            'character_error_rate': (counts['substitutions'] + counts['deletions'] + counts['insertions']) / len(expected['text']),
            'expected_characters': len(expected['text']), 'actual_characters': len(actual['text']),
            'protected_mismatch_count': protected_changes, 'reasons': reasons,
            'normalization': 'Unicode NFKC, casefold, whitespace and nonnumeric punctuation; meaningful numeric punctuation retained; no Chinese-script conversion',
            'video_sha256': actual_hash, 'edit_source_sha256': edit.get('source_sha256'),
            'mismatches': mismatches, 'limits': LIMITS}


def compare_files(edit_path, transcript_path, video, output, threshold=.97):
    output = Path(output).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError('Speech comparison output exists; use a new filename')
    edit = json.loads(Path(edit_path).read_text(encoding='utf-8'))
    transcript = json.loads(Path(transcript_path).read_text(encoding='utf-8'))
    report = compare_speech(edit, transcript, video, threshold)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--edit', required=True, type=Path)
    parser.add_argument('--transcript', required=True, type=Path)
    parser.add_argument('--video', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--threshold', type=float, default=.97)
    args = parser.parse_args()
    report = compare_files(args.edit, args.transcript, args.video, args.output, args.threshold)
    print(json.dumps({k: report[k] for k in ('status', 'similarity', 'threshold', 'counts',
                                           'protected_mismatch_count', 'reasons', 'limits')},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
