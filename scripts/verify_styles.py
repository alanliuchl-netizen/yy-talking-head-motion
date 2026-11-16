#!/usr/bin/env python3
"""Render installed style/aspect pairs from anonymous media and retain review evidence."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import html
import json
import os
from pathlib import Path
import subprocess
import sys
from styles import STYLES

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_suite(output, selected, parallel=2, workers=2):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, HYPERFRAMES_TELEMETRY_DISABLED='1')
    for aspect in ('square', 'portrait'):
        subprocess.run([sys.executable, str(ROOT / 'scripts/make_demo.py'), '--output',
                        str(output / 'media' / aspect), '--source-aspect', aspect], check=True, env=env)
    sources = {p.relative_to(output).as_posix(): digest(p) for p in (output / 'media').rglob('*') if p.is_file()}
    (output / 'renders').mkdir()
    (output / 'logs').mkdir()
    (output / 'previews').mkdir()
    cases = [(preset, aspect) for preset in selected for aspect in STYLES[preset]['aspects']]

    def render_case(case):
        preset, aspect = case
        name = f'{preset}-{aspect}'
        source_aspect = 'portrait' if preset == 'green-gold-portrait' else 'square'
        final = output / 'renders' / f'{name}.mp4'
        log = output / 'logs' / f'{name}.log'
        command = [sys.executable, str(ROOT / 'scripts/render.py'), '--input',
                   str(output / 'media' / source_aspect / 'project.json'), '--style', preset,
                   '--aspect', aspect, '--output', str(final), '--workers', str(workers)]
        with log.open('w', encoding='utf-8') as stream:
            process = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        result = {'style': preset, 'name': STYLES[preset]['name'], 'family': STYLES[preset]['family'],
                  'aspect': aspect, 'source_aspect': source_aspect, 'exit_code': process.returncode,
                  'log': log.relative_to(output).as_posix()}
        if process.returncode:
            result['status'] = 'FAILED'
            print(name + ': FAILED (see ' + result['log'] + ')', flush=True)
            return result
        result.update(json.loads(final.with_suffix('.json').read_text(encoding='utf-8')))
        result['video'] = final.relative_to(output).as_posix()
        project = final.parent / result['project']
        check = json.loads((project / 'check.json').read_text(encoding='utf-8'))
        result['checks'] = {k: {field: check[k][field] for field in ('errorCount', 'warningCount')}
                            for k in ('lint', 'runtime', 'layout', 'contrast')}
        result['srt_sha256'] = digest(final.with_suffix('.srt'))
        frame = output / 'previews' / f'{name}.jpg'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', '1.7', '-i',
                        str(final), '-frames:v', '1', '-vf', 'scale=-2:480', '-q:v', '2', '-n', str(frame)], check=True)
        result['preview'] = frame.relative_to(output).as_posix()
        print(name + ': PASS', flush=True)
        return result

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        results = list(pool.map(render_case, cases))
    unchanged = all(digest(output / relative) == value for relative, value in sources.items())
    passed = [case for case in results if case['status'] == 'PASS']
    same_srt = bool(passed) and len({case['srt_sha256'] for case in passed}) == 1
    runtime_sources = sorted([*ROOT.glob('scripts/*.py'), *ROOT.glob('assets/template/*.css'),
                              ROOT / 'package.json', ROOT / 'package-lock.json'])
    report = {'version': json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version'],
              'ok': len(passed) == len(cases) and unchanged and same_srt,
              'cases': results, 'input_media_unchanged': unchanged, 'all_srt_identical': same_srt,
              'source_sha256': {path.relative_to(ROOT).as_posix(): digest(path) for path in runtime_sources},
              'limitations': ['Anonymous test patterns and cue tones; no human speech or face review',
                              'Local macOS rendering; Linux/Windows and fresh browser installation not verified']}
    (output / 'acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    cards = []
    for case in passed:
        cards.append(f'<article><h2>{html.escape(case["name"])} · {html.escape(case["aspect"])}</h2>'
                     f'<video controls preload="none" poster="{html.escape(case["preview"])}" '
                     f'src="{html.escape(case["video"])}"></video><p>合成测试画面与提示音 · 非真人案例</p></article>')
    gallery = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>口播动效风格预览</title><style>body{margin:32px;background:#f5f4f0;color:#222;font:16px system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px}article{padding:20px;background:white;border-radius:12px}h1{font-size:28px}h2{font-size:18px}video{width:100%;height:480px;object-fit:contain;background:#171b1d}p{color:#555}</style><h1>口播动效风格预览</h1><p>由实际验证成片生成，画面内彩条用于检验人物窗口布局。</p><main>' + ''.join(cards) + '</main></html>'
    (output / 'index.html').write_text(gallery, encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--style', action='append', choices=list(STYLES))
    parser.add_argument('--parallel', type=int, choices=(1, 2), default=2)
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=2)
    args = parser.parse_args()
    report = run_suite(args.output, args.style or list(STYLES), args.parallel, args.workers)
    raise SystemExit(0 if report['ok'] else 1)
