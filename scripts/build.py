#!/usr/bin/env python3
"""Generate either aspect of the same HyperFrames talking-head template.

All copy and cue times come from the input project; layout comes from style.css.
No transcription, rough cutting, voice generation or image generation occurs.
"""
from pathlib import Path
import argparse
import html
import json
import math
import re
import shutil
import subprocess
from styles import STYLES, resolve_style

ROOT = Path(__file__).resolve().parents[1]
ASPECTS = {'landscape': (1920, 1080), 'portrait': (1080, 1920)}
LAYOUTS = {'diagram', 'compare', 'flow', 'cards', 'timeline', 'statement'}


def marked(text, words, tag='span', cls='accent', once=False):
    """Escape first; match source text once without nesting or replacing markup."""
    words = sorted(set(w for w in words if w), key=len, reverse=True)
    if not words:
        return html.escape(text)
    pattern = re.compile('|'.join(re.escape(w) for w in words))
    parts, cursor = [], 0
    for m in pattern.finditer(text):
        parts.append(html.escape(text[cursor:m.start()]))
        attrs = f' class="{cls}"' if cls else ''
        parts.append(f'<{tag}{attrs}>{html.escape(m.group())}</{tag}>')
        cursor = m.end()
        if once:
            break
    parts.append(html.escape(text[cursor:]))
    return ''.join(parts)


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Project must be a JSON object')
    if data.get('editing_stage') not in (None, 'motion_plan_reviewed'):
        raise ValueError('Agent must finish actual scene planning and review before rendering the edited project')
    resolve_style(data.get('style', 'black-orange'))
    def number(value, label):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f'{label} must be a finite number')
        return value
    def text(value, label):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{label} must be non-empty text')
    for key in ('title', 'header'):
        text(data.get(key), key)
    if not isinstance(data.get('header_note', ''), str):
        raise ValueError('header_note must be text')
    for word in data.get('emphasis_words', []):
        text(word, 'emphasis_words')
    if 'identity' in data:
        identity = data['identity']
        if not isinstance(identity, dict) or identity.keys() - {'name', 'role', 'lines'}:
            raise ValueError('identity accepts name, role and lines')
        for key in ('name', 'role'):
            if key in identity and not isinstance(identity[key], str):
                raise ValueError(f'identity.{key} must be text')
        if not isinstance(identity.get('lines', []), list) or any(not isinstance(x, str) for x in identity.get('lines', [])):
            raise ValueError('identity.lines must be a text array')
        if data.get('style') == 'identity-blue' and (len(identity.get('name', '')) > 20 or len(identity.get('role', '')) > 28 or len(identity.get('lines', [])) > 3 or any(len(line) > 30 for line in identity.get('lines', []))):
            raise ValueError('Identity panel capacity: name <=20, role <=28, up to three lines <=30 characters each')
    media = data.get('media')
    if not isinstance(media, dict) or not {'presenter', 'voice'} <= media.keys() or media.keys() - {'presenter', 'voice', 'audio_copy'}:
        raise ValueError('media requires presenter/voice; only audio_copy is optional')
    extensions = {
        'presenter': {'.mp4', '.mov', '.m4v', '.webm'},
        'voice': {'.wav', '.m4a', '.aac', '.mp3', '.flac', '.ogg', '.mp4', '.webm'},
        'audio_copy': {'.m4a', '.aac', '.mp4'},
    }
    for key, value in media.items():
        text(value, 'media path')
        path = Path(value)
        if path.is_absolute() or '..' in path.parts or '\\' in value or ':' in value:
            raise ValueError('Media must use a relative path inside the input project')
        if path.suffix.lower() not in extensions[key]:
            raise ValueError(f'Unsupported {key} extension: use {", ".join(sorted(extensions[key]))}')
    if data.get('version') != 1:
        raise ValueError('Unsupported project version; expected version=1')
    duration = number(data.get('duration'), 'duration')
    fps = data.get('fps')
    if duration <= 0 or type(fps) is not int or fps not in (24, 30, 60):
        raise ValueError('Positive duration and fps=24/30/60 are required')
    if abs(round(duration*fps)/fps-duration) > 1e-6:
        raise ValueError('duration must end on a whole video frame at the selected fps')
    scenes = data.get('scenes')
    if not isinstance(scenes, list) or not scenes or scenes[0].get('start') != 0:
        raise ValueError('First scene must start at zero')
    if not isinstance(data.get('captions'), list):
        raise ValueError('captions must be a list')
    ids = {'root','presenter-frame','presenter','voice','divider','captions'}

    def unique(value):
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', value) or value in ids:
            raise ValueError(f'Duplicate or unsafe id: {value}')
        ids.add(value)

    for i in range(len(data['captions'])):
        unique(f'cap-{i}')
    for index, scene in enumerate(scenes):
        if scene.get('presentation', 'graphic') not in ('host', 'graphic'):
            raise ValueError('scene.presentation must be host or graphic')
        if not isinstance(scene.get('source_note', ''), str):
            raise ValueError('scene.source_note must be text')
        unique(scene['id'])
        for suffix in ('label','title','line'):
            unique(scene['id']+'-'+suffix)
        start = number(scene['start'], 'scene start')
        end = number(scenes[index+1]['start'], 'scene end') if index+1 < len(scenes) else duration
        for field in ('title', 'eyebrow'):
            text(scene.get(field), 'scene ' + field)
        if not 0 <= start < end <= duration:
            raise ValueError(f'Invalid scene time: {scene["id"]}')
        if scene['layout'] not in LAYOUTS or not 1 <= len(scene['items']) <= 4:
            raise ValueError(f'Unknown layout or invalid card count: {scene["id"]}')
        if scene['layout'] in ('diagram', 'compare', 'flow', 'timeline') and len(scene['items']) != 2:
            raise ValueError(f'{scene["layout"]} requires two items')
        if scene['layout'] == 'statement' and len(scene['items']) != 1:
            raise ValueError('statement requires one item')
        nodes = list(scene['items'])
        for key in ('lead', 'connector'):
            if scene.get(key):
                nodes.append(scene[key])
        footer = scene.get('footer')
        if footer:
            nodes.extend(footer.get('runs') or [footer])
        for node in nodes:
            unique(node['id'])
            number(node['at'], 'cue at')
            if not start <= node['at'] < end:
                raise ValueError(f'Cue outside its scene: {node["id"]}')
        for item in scene['items']:
            text(item.get('title'), 'item title')
            for field in ('body', 'overline'):
                if field in item and not isinstance(item[field], str):
                    raise ValueError(f'item {field} must be text')
            if item.get('diagram') not in (None, 'cube', 'plane'):
                raise ValueError('Only cube/plane semantic diagrams are currently supported')
    previous_end = 0
    for caption in data['captions']:
        number(caption['start'], 'caption start')
        number(caption['end'], 'caption end')
        if not previous_end - 1e-6 <= caption['start'] < caption['end'] <= duration:
            raise ValueError('Caption times overlap or extend outside duration')
        text(caption.get('text'), 'caption text')
        previous_end = caption['end']


def title_markup(text, words):
    # Keep short comma-delimited clauses together when a portrait title wraps.
    # The same markup still fits naturally on a single landscape line.
    phrases = re.findall(r'[^，：；]+[，：；]?', text)
    if len(phrases) > 1 and all(len(x) <= 12 for x in phrases):
        return ''.join(f'<span class="title-phrase">{marked(x,words)}</span>' for x in phrases)
    return marked(text,words)


def diagram(name):
    path = ('<path class="wire" d="M106 73H262V204H106ZM106 73L174 28H330V159L262 204M262 73L330 28M106 204L174 159H330M174 28V159"/>'
            '<path class="wire accent-wire" d="M106 73H262V204H106Z"/>') if name == 'cube' else (
            '<path class="plane-fill" d="M66 154L166 78H354L254 154Z"/>'
            '<path class="wire accent-wire" d="M106 124H294M126 108H314M146 92H334M116 154L216 78M166 154L266 78M216 154L316 78"/>')
    return f'<svg viewBox="0 0 420 228" aria-label="{html.escape(name)}">{path}</svg>'


def resolve_media(base, relative):
    base = Path(base).resolve()
    path = (base / relative).resolve()
    if base not in path.parents:
        raise ValueError('Media resolves outside the input project')
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def check_media(path, stream_type, duration, fps, audio_copy=False):
    info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
    streams = [s for s in info['streams'] if s['codec_type'] == stream_type]
    if not streams:
        raise ValueError(f'Missing {stream_type} stream: {path}')
    stream = streams[0]
    if audio_copy and stream.get('codec_name') != 'aac':
        raise ValueError('audio_copy must contain AAC audio for lossless MP4 muxing; otherwise omit audio_copy')
    start = float(stream.get('start_time', 0))
    length = float(stream.get('duration', info['format'].get('duration', 0)))
    if abs(start) > 1 / fps or abs(length - duration) > 1 / fps:
        raise ValueError(f'Media must start at zero and match the edited timeline (±1 frame): {path}; start={start}, duration={length}')
    return stream


def copy_dependencies(assets, data, include_serif=False):
    gsap = ROOT / 'node_modules/gsap'
    fonts = ROOT / 'node_modules/@fontsource/noto-sans-sc'
    if not (gsap / 'dist/gsap.min.js').is_file() or not (fonts / '400.css').is_file():
        raise ValueError('Dependencies missing. Run npm ci in the Skill directory first.')
    shutil.copy2(gsap / 'dist/gsap.min.js', assets / 'gsap.min.js')
    font_output = assets / 'fonts'
    (font_output / 'files').mkdir(parents=True)
    font_css = []
    used = {ord(char) for char in json.dumps(data, ensure_ascii=False) + '→'}
    for weight in (400, 600, 800):
        css = (fonts / f'{weight}.css').read_text(encoding='utf-8')
        # Fontsource splits Chinese by Unicode range. Include every range used by
        # this project's copy; rebuild automatically selects ranges for new copy.
        for block in re.findall(r'@font-face\s*\{[^}]*\}', css):
            ranges = re.search(r'unicode-range:\s*([^;]+)', block)
            include = not ranges
            if ranges:
                for part in ranges.group(1).split(','):
                    low, _, high = part.strip().removeprefix('U+').partition('-')
                    lower = int(low.replace('?', '0'), 16)
                    upper = int((high or low).replace('?', 'F'), 16)
                    if any(lower <= code <= upper for code in used):
                        include = True
                        break
            if not include:
                continue
            relative = re.search(r'url\(([^)]+\.woff2)\)', block).group(1).strip('\"\'').removeprefix('./')
            shutil.copy2(fonts / relative, font_output / relative)
            block = re.sub(r'src:[^;]+;', f'src: url(assets/fonts/{relative}) format(\'woff2\');', block)
            font_css.append(block.replace('font-display: swap', 'font-display: block'))
    (assets / 'GSAP-NOTICE.txt').write_text(
        'GSAP 3.14.2\nCopyright 2025 GreenSock. All rights reserved.\n'
        'License: https://gsap.com/community/standard-license/\n'
        'Original copyright/license header is retained in gsap.min.js.\n'
        'Not covered by this project\'s MIT license.\n', encoding='utf-8')
    for source, target in ((fonts / 'LICENSE', font_output / 'OFL.txt'),):
        if not source.is_file():
            raise ValueError(f'Third-party license missing: {source.name}')
        shutil.copy2(source, target)
    if include_serif:
        serif_package = ROOT / 'node_modules/@fontsource/noto-serif-sc'
        serif_output = font_output / 'serif'
        (serif_output / 'files').mkdir(parents=True)
        for weight in (400, 600, 800):
            css = (serif_package / f'{weight}.css').read_text(encoding='utf-8')
            for block in re.findall(r'@font-face\s*\{[^}]*\}', css):
                ranges = re.search(r'unicode-range:\s*([^;]+)', block)
                include = not ranges
                if ranges:
                    for part in ranges.group(1).split(','):
                        low, _, high = part.strip().removeprefix('U+').partition('-')
                        lower = int(low.replace('?', '0'), 16)
                        upper = int((high or low).replace('?', 'F'), 16)
                        if any(lower <= code <= upper for code in used):
                            include = True
                            break
                if not include:
                    continue
                relative = re.search(r'url\(([^)]+\.woff2)\)', block).group(1).strip('\"\'').removeprefix('./')
                shutil.copy2(serif_package / relative, serif_output / relative)
                font_css.append(re.sub(r'src:[^;]+;', f'src: url(assets/fonts/serif/{relative}) format(\'woff2\');', block).replace('font-display: swap', 'font-display: block'))
        shutil.copy2(serif_package / 'LICENSE', serif_output / 'OFL.txt')
    return '\n'.join(font_css)


def subtitles(captions):
    def stamp(t):
        ms=round(t*1000)
        return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
    return '\n\n'.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}' for i,c in enumerate(captions))+'\n'


def build(input_path, aspect, output, style=None):
    input_path, output = Path(input_path).resolve(), Path(output).resolve()
    data = json.loads(input_path.read_text(encoding='utf-8'))
    preset = style or data.get('style', 'black-orange')
    selected = resolve_style(preset, aspect)
    data['style'] = preset
    validate(data)
    if output.exists():
        raise FileExistsError('Build output already exists; choose a new directory')
    if aspect not in ASPECTS:
        raise ValueError('Unknown aspect; choose landscape or portrait')
    sources = {name: resolve_media(input_path.parent, relative) for name, relative in data['media'].items()}
    source_info = {}
    for name in ('presenter','voice','audio_copy'):
        if name in data['media']:
            stream = check_media(sources[name], 'video' if name == 'presenter' else 'audio', data['duration'], data['fps'], name == 'audio_copy')
            if name == 'presenter':
                source_info = stream
    width, height = ASPECTS[aspect]
    output.mkdir(parents=True, exist_ok=False)
    assets = output / 'assets'
    assets.mkdir(exist_ok=True)
    media = {}
    for name, relative in data['media'].items():
        source = sources[name]
        if not source.is_file():
            raise FileNotFoundError(source)
        target = assets / (name + source.suffix.lower())
        if source != target and (not target.exists() or source.stat().st_mtime_ns != target.stat().st_mtime_ns or source.stat().st_size != target.stat().st_size):
            shutil.copy2(source, target)
        media[name] = f'assets/{target.name}'
    fonts_css = copy_dependencies(assets, data, preset in ('paper-ink', 'ppt-bright', 'ppt-calm'))
    css = (ROOT / 'assets/template/style.css').read_text(encoding='utf-8')
    css = fonts_css + f'\n:root{{--canvas-w:{width}px;--canvas-h:{height}px}}\n' + css
    if preset == 'black-orange-center':
        css += '\n' + (ROOT / 'assets/template/center.css').read_text(encoding='utf-8')
    scenes_html, reveal = [], []
    for index, scene in enumerate(data['scenes']):
        sid, start = scene['id'], float(scene['start'])
        items_html = []
        for j, item in enumerate(scene['items']):
            contents = ''
            if item.get('diagram'):
                contents += diagram(item['diagram'])
            for key, klass in [('overline', 'item-overline'), ('title', 'item-title'), ('body', 'item-body')]:
                if item.get(key):
                    contents += f'<div class="{klass}">{html.escape(item[key])}</div>'
            if scene['layout'] == 'statement':
                contents += '<div class="statement-mark" data-layout-ignore></div>'
            em = ' emphasis' if item.get('emphasis') else ''
            items_html.append(f'<div id="{item["id"]}" class="item{em}">{contents}</div>')
            reveal.append([item['id'], item['at'], 'card'])
            if j == 0 and scene.get('connector'):
                c = scene['connector']
                items_html.append(f'<div id="{c["id"]}" class="connector"><div class="label">{html.escape(c.get("label", ""))}</div><div class="arrow" data-layout-ignore>{html.escape(c.get("text", "→"))}</div></div>')
                reveal.append([c['id'], c['at'], 'connector'])
        lead = scene.get('lead')
        lead_html = f'<div id="{lead["id"]}" class="lead">{html.escape(lead["text"])}</div>' if lead else ''
        if lead:
            reveal.append([lead['id'], lead['at'], 'copy'])
        footer = scene.get('footer')
        footer_html = ''
        if footer:
            if footer.get('runs'):
                parts = []
                for run in footer['runs']:
                    parts.append(f'<span id="{run["id"]}">{marked(run["text"], run.get("emphasis", []), "strong", "")}</span>')
                    reveal.append([run['id'], run['at'], 'copy'])
                footer_html = '<div class="footer">' + ''.join(parts) + '</div>'
            else:
                footer_html = f'<div class="footer" id="{footer["id"]}">{marked(footer["text"], footer.get("emphasis", []), "strong", "")}</div>'
                reveal.append([footer['id'], footer['at'], 'copy'])
        title = title_markup(scene['title'], scene.get('title_emphasis', []))
        scenes_html.append(f'''<section id="{sid}" class="scene layout-{scene['layout']} count-{len(scene['items'])}" style="z-index:1">
<div class="scene-content"><div class="eyebrow" id="{sid}-label">{html.escape(scene['eyebrow'])}</div><h1 id="{sid}-title">{title}</h1><div class="underline" id="{sid}-line" data-layout-ignore></div>{lead_html}<div class="items">{''.join(items_html)}</div>{footer_html}</div></section>''')
        reveal.extend([[sid+'-label', start+.08, 'label'], [sid+'-title', start+.14, 'title'], [sid+'-line', start+.34, 'line']])
    captions = ''.join(f'<div class="caption" id="cap-{i}">{marked(c["text"], data.get("emphasis_words", []), "strong", "", once=True)}</div>' for i,c in enumerate(data['captions']))
    cues = [{'id':s['id'], 'start':s['start'], 'layout':s['layout']} for s in data['scenes']]
    js = f'''window.__timelines=window.__timelines||{{}};
const PAGES={json.dumps(cues,ensure_ascii=False)};
const CUES={json.dumps(data['captions'],ensure_ascii=False)};
const REVEALS={json.dumps(reveal,ensure_ascii=False)};
const tl=gsap.timeline({{paused:true}});
PAGES.slice(1).forEach((p,i)=>{{tl.to('#'+PAGES[i].id,{{opacity:0,duration:.3,ease:'power2.inOut'}},p.start);tl.fromTo('#'+p.id,{{opacity:0}},{{opacity:1,duration:.3,ease:'power2.inOut'}},p.start);}});
REVEALS.forEach(([id,at,kind])=>{{if(kind==='line'){{tl.from('#'+id,{{scaleX:0,duration:.4,ease:'expo.out'}},at);}}else{{tl.from('#'+id,{{y:kind==='label'?12:18,opacity:0,duration:.34,ease:kind==='title'?'power3.out':kind==='connector'?'sine.out':'power2.out'}},at);}}}});
CUES.forEach((c,i)=>{{tl.fromTo('#cap-'+i,{{opacity:0}},{{opacity:1,duration:.06,ease:'none'}},c.start);tl.set('#cap-'+i,{{opacity:0}},c.end);}});
window.__timelines.main=tl;tl.pause(0);'''
    # JSON is embedded as JS data; escape HTML script delimiters from input copy.
    js = js.replace('</', '<\\/')
    duration, fps = data['duration'], data['fps']
    document = f'''<!doctype html><html lang="zh-CN" class="{aspect}" data-resolution="{aspect}"><head><meta charset="utf-8"><meta name="viewport" content="width={width},height={height}"><title>{html.escape(data['title'])}</title><script src="assets/gsap.min.js"></script><style>{css}</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{duration}" data-width="{width}" data-height="{height}" data-fps="{fps}">
{''.join(scenes_html)}<div class="topbar"><b>{html.escape(data['header'])}</b><span>{html.escape(data.get('header_note',''))}</span></div><div class="top-rule" data-layout-ignore></div>
<div id="presenter-frame"><video id="presenter" class="clip" src="{html.escape(media['presenter'], quote=True)}" data-start="0" data-duration="{duration}" data-track-index="1" muted playsinline></video></div>
<audio id="voice" class="clip" src="{html.escape(media['voice'], quote=True)}" data-start="0" data-duration="{duration}" data-track-index="2" data-volume="1"></audio><div id="divider" data-layout-ignore></div><div id="captions">{captions}</div></div><script>{js}</script></body></html>'''
    if preset in ('green-gold', 'green-gold-portrait', 'identity-blue'):
        from style_portrait import render_html
        document = render_html(data, aspect, media, fonts_css, preset, source_info)
    elif preset in ('paper-ink', 'ppt-bright', 'ppt-calm'):
        from style_editorial import render_html
        document = render_html(data, aspect, media, fonts_css, preset, source_info)
    (output / 'index.html').write_text(document, encoding='utf-8')
    (output / 'captions.srt').write_text(subtitles(data['captions']), encoding='utf-8')
    manifest = dict(data, aspect=aspect, width=width, height=height, media=media, frames=round(duration*fps), style_name=selected['name'], style_family=selected['family'])
    (output / 'project.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2), encoding='utf-8')
    (output / 'meta.json').write_text(json.dumps({'id':'talking-head-'+aspect, 'name':data['title']+' · '+aspect},ensure_ascii=False,indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--aspect', choices=[*ASPECTS,'16:9','9:16'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--style', choices=list(STYLES))
    parser.add_argument('--list-styles', action='store_true')
    args = parser.parse_args()
    if args.list_styles:
        print(json.dumps(STYLES, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    if not all((args.input, args.aspect, args.output)):
        parser.error('--input, --aspect and --output are required unless --list-styles is used')
    ratio = {'16:9':'landscape','9:16':'portrait'}.get(args.aspect,args.aspect)
    result = build(args.input,ratio,args.output,args.style)
    print(json.dumps({'project':str(args.output.resolve()),'aspect':ratio,'size':[result['width'],result['height']],'duration':result['duration'],'scenes':len(result['scenes']),'captions':len(result['captions'])},ensure_ascii=False))
