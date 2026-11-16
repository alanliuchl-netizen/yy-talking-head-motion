#!/usr/bin/env python3
"""Read-only dependency preflight. Does not install software or request API keys."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect():
    checks = {'python>=3.9': sys.version_info >= (3, 9)}
    for tool in ('node', 'ffmpeg', 'ffprobe'):
        checks[tool] = bool(shutil.which(tool))
    if checks['node']:
        version = subprocess.check_output(['node', '--version'], text=True).strip()
        checks['node>=22'] = int(version.lstrip('v').split('.')[0]) >= 22
    packages = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['dependencies']
    for name, version in packages.items():
        path = ROOT / 'node_modules' / name / 'package.json'
        checks[f'{name}@{version}'] = path.is_file() and json.loads(path.read_text(encoding='utf-8')).get('version') == version
    checks['hyperframes CLI'] = (ROOT / 'node_modules/hyperframes/dist/cli.js').is_file()
    gsap = ROOT / 'node_modules/gsap/dist/gsap.min.js'
    checks['GSAP license notice'] = gsap.is_file() and 'gsap.com/standard-license' in gsap.read_text(encoding='utf-8')[:1000]
    checks['Noto font and license'] = all((ROOT / 'node_modules/@fontsource/noto-sans-sc' / x).is_file() for x in ('400.css', '600.css', '800.css', 'LICENSE'))
    checks['Noto serif font and license'] = all((ROOT / 'node_modules/@fontsource/noto-serif-sc' / x).is_file() for x in ('400.css', '600.css', '800.css', 'LICENSE'))
    return {'ok': all(checks.values()), 'checks': checks,
            'browser': 'HyperFrames requires local Chrome/Chromium; check/render reports browser availability',
            'model_api': 'not required'}


if __name__ == '__main__':
    report = inspect()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report['ok'] else 1)
