#!/usr/bin/env python3
"""Create an independent test-pattern video and cue tones, without private media."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--source-aspect', choices=['square', 'portrait', 'landscape'], default='square')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('Demo output exists; use a new directory')
    assets = output / 'assets'
    assets.mkdir(parents=True)
    shutil.copy2(ROOT / 'examples/demo/project.json', output / 'project.json')
    size = {'square': '640x640', 'portrait': '360x640', 'landscape': '640x360'}[args.source_aspect]
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                    '-i', f'testsrc2=size={size}:rate=30:duration=18',
                    '-vf', 'drawgrid=width=80:height=80:thickness=1:color=white@0.3',
                    '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-an',
                    '-movflags', '+faststart', '-n', str(assets / 'presenter.mp4')], check=True)
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                    '-i', 'sine=frequency=660:sample_rate=48000:duration=18',
                    '-af', "volume='if(lt(mod(t,3),0.14),0.12,0)':eval=frame",
                    '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-n',
                    str(assets / 'voice.m4a')], check=True)
    (output / 'provenance.json').write_text(json.dumps({
        'video': 'FFmpeg testsrc2 + grid; no person or reference photo',
        'audio': '660 Hz cue tone at each three-second boundary; no speech',
        'copy': 'Original public demonstration text',
        'duration': 18, 'fps': 30, 'source_size': size}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Demo created: ' + str(output / 'project.json'))


if __name__ == '__main__':
    main()
