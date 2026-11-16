#!/usr/bin/env python3
"""Build, check, render and verify a new local MP4 without overwriting prior work."""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from build import build, ROOT
from doctor import inspect
from verify import verify
from styles import STYLES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--aspect', choices=['landscape', 'portrait', '16:9', '9:16'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=3)
    parser.add_argument('--style', choices=list(STYLES))
    args = parser.parse_args()
    aspect = {'16:9': 'landscape', '9:16': 'portrait'}.get(args.aspect, args.aspect)
    final = args.output.resolve()
    project = args.work_dir.resolve() if args.work_dir else final.parent / (final.stem + '-project')
    if final.suffix.lower() != '.mp4':
        parser.error('Output must be an MP4 filename')
    targets = (final, final.with_suffix('.srt'), final.with_suffix('.json'), project)
    if len(set(targets)) != len(targets):
        parser.error('Video, sidecars and working directory must have distinct paths')
    for target in targets:
        if target.exists():
            parser.error('Output or working directory exists; choose a new name: ' + str(target))
    if project == final or project in final.parents:
        parser.error('Final output must be outside the new project directory')
    preflight = inspect()
    if not preflight['ok']:
        raise SystemExit(json.dumps(preflight, ensure_ascii=False, indent=2))
    doc = build(args.input, aspect, project, args.style)
    cli = ['node', str(ROOT / 'node_modules/hyperframes/dist/cli.js')]
    env = dict(os.environ, HYPERFRAMES_TELEMETRY_DISABLED='1')
    result = subprocess.run([*cli, 'check', '.', '--samples', '18', '--json'],
                            cwd=project, env=env, capture_output=True, text=True)
    (project / 'check.stdout.txt').write_text(result.stdout, encoding='utf-8')
    (project / 'check.stderr.txt').write_text(result.stderr, encoding='utf-8')
    try:
        check = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit('Check did not return JSON; inspect check.stdout/stderr.txt') from exc
    (project / 'check.json').write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding='utf-8')
    if result.returncode:
        raise SystemExit('HyperFrames check failed; inspect the new project/check.json')
    for category in ('lint', 'runtime', 'layout', 'contrast'):
        section = check.get(category)
        if not isinstance(section, dict) or 'errorCount' not in section or 'warningCount' not in section:
            raise SystemExit(f'Incomplete {category} check; inspect check.json')
        if section['errorCount'] or section['warningCount']:
            raise SystemExit(f'Review {category} findings in project/check.json before rendering')
    visual = project / 'rendered-visual.mp4'
    subprocess.run([*cli, 'render', '.', '--output', str(visual), '--fps', str(doc['fps']),
                    '--quality', 'high', '--workers', str(args.workers), '--sdr'],
                    cwd=project, env=env, check=True)
    media = doc['media']
    audio = project / media.get('audio_copy', media['voice'])
    codec = ['-c:a', 'copy'] if 'audio_copy' in media else ['-c:a', 'aac', '-b:a', '192k']
    final.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(visual),
                    '-i', str(audio), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
                    *codec, '-movflags', '+faststart', '-metadata', 'title=' + doc['title'], '-n', str(final)], check=True)
    report = verify(final, project / 'project.json', audio if 'audio_copy' in media else None)
    shutil.copy2(project / 'captions.srt', final.with_suffix('.srt'))
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    report.update(video=final.name, aspect=aspect, style=doc['style'], style_family=doc['style_family'], project=os.path.relpath(project, final.parent), version=version)
    final.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
