#!/usr/bin/env python3
"""Read back an MP4: size, frame count, timing, decode and optional AAC packet identity."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
        '-show_streams', '-show_format', '-of', 'json', str(path)], text=True))


def packets(path):
    result = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'a:0',
        '-show_packets', '-show_entries', 'packet=pts_time,duration_time,data_hash',
        '-show_data_hash', 'sha256', '-of', 'json', str(path)], text=True))
    return result.get('packets', [])


def verify(video, project, audio_reference=None):
    doc = json.loads(Path(project).read_text(encoding='utf-8'))
    info = probe(video)
    streams = info['streams']
    visual = next((x for x in streams if x['codec_type'] == 'video'), None)
    audio = next((x for x in streams if x['codec_type'] == 'audio'), None)
    if not visual or not audio:
        raise ValueError('Final MP4 must have both video and audio streams')
    if (visual['width'], visual['height']) != (doc['width'], doc['height']):
        raise ValueError('Final dimensions differ from the selected aspect')
    frames = int(visual.get('nb_read_frames', 0))
    if frames != doc['frames']:
        raise ValueError(f'Frame count differs: {frames} vs {doc["frames"]}')
    fps = doc['fps']
    for stream in (visual, audio):
        if abs(float(stream.get('start_time', 0))) > 1 / fps:
            raise ValueError('Final stream does not start at zero')
        duration = float(stream.get('duration', info['format']['duration']))
        if abs(duration - doc['duration']) > 1 / fps:
            raise ValueError('Final stream duration differs by more than one frame')
    rate_n, rate_d = visual['avg_frame_rate'].split('/')
    if abs(int(rate_n) / int(rate_d) - fps) > 1e-6:
        raise ValueError('Final frame rate differs from input')
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-xerror', '-i',
                    str(video), '-f', 'null', '-'], check=True, capture_output=True)
    audio_check = 'stream presence and timing checked; audio packets not compared to a reference'
    if audio_reference:
        actual, expected = packets(video), packets(audio_reference)
        if not expected or len(actual) != len(expected):
            raise ValueError('Copied audio packet count differs')
        for left, right in zip(actual, expected):
            if left.get('data_hash') != right.get('data_hash') or not left.get('data_hash'):
                raise ValueError('Copied audio packet payload differs')
            for key in ('pts_time', 'duration_time'):
                if abs(float(left.get(key, 0)) - float(right.get(key, 0))) > 1 / int(audio['sample_rate']) + 1e-6:
                    raise ValueError('Copied audio packet timing differs')
        audio_check = f'{len(actual)} AAC packets: payload and timing identical'
    return {'status': 'PASS', 'size': [visual['width'], visual['height']], 'fps': fps,
            'frames': frames, 'duration': doc['duration'], 'full_decode': 'PASS',
            'audio': audio_check, 'sha256': hashlib.sha256(Path(video).read_bytes()).hexdigest(),
            'human_speech_review': 'not performed by this technical check'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', required=True, type=Path)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--audio-reference', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.video, args.project, args.audio_reference), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
