#!/usr/bin/env python3
"""Build a small source-only release from an allowlist; exclude local media and dependencies."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ['SKILL.md', 'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md',
         'package.json', 'package-lock.json', 'requirements-asr.txt', '.gitignore', '.npmrc']
DIRECTORIES = ['scripts', 'references', 'assets', 'examples/demo', 'tests', 'agents']


def release(output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Release exists; choose a new filename')
    paths = [ROOT / name for name in FILES]
    for folder in DIRECTORIES:
        paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    validation = ROOT / 'docs/VALIDATION.md'
    if validation.exists():
        paths.append(validation)
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    manifest = {'version': version, 'files': []}
    for path in sorted(paths):
        if path.is_symlink() or ROOT not in path.resolve().parents:
            raise ValueError('Release source must be an ordinary file inside the Skill')
        content = path.read_bytes()
        if (b'/' + b'Users/') in content or re.search(rb'sk-(?:proj-)?[A-Za-z0-9_-]{24,}', content):
            raise ValueError('Private-path or key-like content found in ' + str(path.relative_to(ROOT)))
        manifest['files'].append({'path': path.relative_to(ROOT).as_posix(), 'bytes': len(content),
                                  'sha256': hashlib.sha256(content).hexdigest()})
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            archive.write(path, 'yy-talking-head-motion/' + path.relative_to(ROOT).as_posix())
        archive.writestr('yy-talking-head-motion/RELEASE_CONTENTS.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps({'archive': output.name, 'source_files': len(paths), 'bytes': output.stat().st_size,
                      'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    release(parser.parse_args().output)
