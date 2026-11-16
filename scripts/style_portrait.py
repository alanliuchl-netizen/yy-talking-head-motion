"""Portrait-only shells for the local talking-head motion renderer.

Media validation, copying, audio muxing and technical verification belong to the
caller. This module only turns an already validated project into HTML.
"""
from __future__ import annotations

import html
import json
import math
import unicodedata


PRESETS = {"green-gold", "green-gold-portrait", "identity-blue"}


def _esc(value):
    return html.escape(str(value), quote=True)


def _json(value):
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _portrait_source(stream):
    """Apply ffprobe display rotation before deciding the source orientation."""
    if not isinstance(stream, dict):
        raise ValueError("A video stream from ffprobe is required for source adaptation")
    try:
        width, height = float(stream["width"]), float(stream["height"])
        rotation = stream.get("tags", {}).get("rotate", 0)
        for side in stream.get("side_data_list", []):
            if "rotation" in side:
                rotation = side["rotation"]
        rotation = float(rotation)
        if not all(math.isfinite(value) for value in (width, height, rotation)):
            raise ValueError("Non-finite source geometry")
        if width <= 0 or height <= 0:
            raise ValueError("Invalid source geometry")
        # ffprobe reports orthogonal display-matrix rotation in degrees.
        turns = rotation / 90
        if abs(turns - round(turns)) > 1e-5:
            raise ValueError("Source rotation must be an orthogonal multiple of 90 degrees")
        if round(turns) % 2:
            width, height = height, width
        return width < height
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Cannot determine the displayed video orientation") from exc


def _box(x, y, width, height):
    return f"left:{x}px;top:{y}px;width:{width}px;height:{height}px"


def _size(text, normal, minimum, capacity):
    length = max(1, len(text))
    return max(minimum, min(normal, round(normal * math.sqrt(capacity / length))))


def _header_size(text, normal, height, has_note, note_size):
    available = height - 40 - (note_size * 1.4 + 12 if has_note else 0)
    # A conservative estimate only selects a starting size; final MP4 review
    # still owns typography acceptance for real copy.
    widths = [sum(1 if unicodedata.east_asian_width(char) in "WF" else .55 for char in line)
              for line in text.splitlines() or [text]]
    for size in range(normal, 29, -1):
        line_count = sum(max(1, math.ceil(width * size / 940)) for width in widths)
        if line_count * size * 1.3 <= available:
            return size
    return 30


def _diagram(name):
    if name == "cube":
        paths = (
            '<path d="M42 45H142V126H42ZM42 45L83 17H183V98L142 126'
            'M142 45L183 17M42 126L83 98H183M83 17V98"/>'
        )
    else:
        paths = (
            '<path d="M25 112L85 38H205L145 112Z"/>'
            '<path d="M45 88H165M65 62H185M65 112L125 38M105 112L165 38"/>'
        )
    return (
        '<svg class="semantic-diagram" viewBox="0 0 230 145" '
        'width="230" height="145" aria-hidden="true">' + paths + '</svg>'
    )


def _card(item, position, count, layout):
    x, y, width, height = position
    title = item.get("title", "")
    overline = item.get("overline", "")
    body = item.get("body", "")
    diagram = item.get("diagram")
    tight = count > 2
    title_size = _size(title, 36 if tight else 42, 28, 14 if tight else 18)
    classes = "item" + (" emphasized" if item.get("emphasis") else "")
    if layout == "statement":
        title_size = _size(title, 78, 42, 12)
        content = f'<div class="statement-copy" style="font-size:{title_size}px">{_esc(title)}</div>'
        if body:
            content += f'<div class="statement-body">{_esc(body)}</div>'
    elif diagram:
        content = _diagram(diagram)
        content += f'<div class="diagram-title">{_esc(title)}</div>'
        if body:
            content += f'<div class="diagram-body">{_esc(body)}</div>'
    else:
        top = 18
        content = ""
        if overline:
            content += f'<div class="item-overline" style="top:{top}px">{_esc(overline)}</div>'
            top += 36
        title_height = 50 if tight else 96
        content += (
            f'<div class="item-title" style="top:{top}px;height:{title_height}px;'
            f'font-size:{title_size}px">{_esc(title)}</div>'
        )
        if body:
            body_top = top + (52 if tight else 102)
            body_height = max(24, height - body_top - 12)
            content += (
                f'<div class="item-body" style="top:{body_top}px;height:{body_height}px;'
                f'font-size:{25 if tight else 28}px">{_esc(body)}</div>'
            )
    return f'<div id="{_esc(item["id"])}" class="{classes}" style="{_box(x, y, width, height)}">{content}</div>'


def _scene(scene, start, end, animations):
    """Use absolute boxes so runtime layout auditing has concrete dimensions."""
    layout, items = scene["layout"], scene["items"]
    count = len(items)
    sid = scene["id"]
    title = scene["title"]
    title_size = _size(title, 48, 34, 27)
    content = (
        f'<div class="scene-eyebrow">{_esc(scene["eyebrow"])}</div>'
        f'<div class="scene-title" style="font-size:{title_size}px">{_esc(title)}</div>'
        '<div class="scene-rule" data-layout-ignore></div>'
    )
    lead = scene.get("lead")
    has_lead = bool(lead)
    if lead:
        content += f'<div id="{_esc(lead["id"])}" class="scene-lead">{_esc(lead["text"])}</div>'
        animations.append({"selector": "#" + lead["id"], "at": lead["at"], "duration": .28})
    top = 226 if has_lead else 190
    available = 246 if has_lead else 282
    connector = scene.get("connector")
    if layout == "statement":
        positions = [(52, top, 952, available)]
    elif count == 1:
        positions = [(52, top, 952, available)]
    elif count == 2:
        gap = 104 if connector else 24
        width = (952 - gap) // 2
        positions = [(52, top, width, available), (52 + width + gap, top, width, available)]
    else:
        # Three cards use the same 2 x 2 grid as four, with the last slot empty.
        height = (available - 16) // 2
        positions = [(52 + (i % 2) * 488, top + (i // 2) * (height + 16), 464, height) for i in range(count)]
    for item, position in zip(items, positions):
        content += _card(item, position, count, layout)
        animations.append({"selector": "#" + item["id"], "at": item["at"], "duration": .28})
    if connector and count == 2:
        content += (
            f'<div id="{_esc(connector["id"])}" class="connector" '
            f'style="{_box(478, top + 70, 100, 120)}">'
            f'<div class="connector-label">{_esc(connector.get("label", ""))}</div>'
            f'<div class="connector-arrow">{_esc(connector.get("text", "→"))}</div></div>'
        )
        animations.append({"selector": "#" + connector["id"], "at": connector["at"], "duration": .28})
    footer = scene.get("footer")
    if footer:
        runs = footer.get("runs") or [footer]
        # Each run occupies its own span; appearance times stay independent.
        content += '<div class="scene-footer">'
        for run in runs:
            content += f'<span id="{_esc(run["id"])}" class="footer-run">{_esc(run["text"])}</span>'
            animations.append({"selector": "#" + run["id"], "at": run["at"], "duration": .28})
        content += '</div>'
    animations.append({"selector": "#" + sid + " .scene-title", "at": start + .08, "duration": .28})
    return (
        f'<section id="{_esc(sid)}" class="graphic-scene layout-{_esc(layout)}">{content}</section>'
    )


def _identity(data):
    identity = data.get("identity") or {}
    parts = []
    if identity:
        for field, klass in (("name", "identity-name"), ("role", "identity-role")):
            if identity.get(field):
                parts.append(f'<div class="{klass}">{_esc(identity[field])}</div>')
        for line in identity.get("lines", []):
            parts.append(f'<div class="identity-line">{_esc(line)}</div>')
    else:
        parts.append(f'<div class="identity-name">{_esc(data["header"])}</div>')
        if data.get("header_note"):
            parts.append(f'<div class="identity-role">{_esc(data["header_note"])}</div>')
    return ''.join(parts)


def render_html(data, aspect, media, font_css, preset, source_info):
    """Return one complete portrait document; do not read or write any files."""
    if aspect not in ("portrait", "9:16"):
        raise ValueError("This preset only supports portrait / 9:16")
    if preset not in PRESETS:
        raise ValueError("Unknown portrait preset")
    tall = preset == "green-gold-portrait" and _portrait_source(source_info)
    blue = preset == "identity-blue"
    window = (180, 240, 720, 1280) if tall else (12, 504, 1056, 594)
    caption_y, caption_height = (1544, 144) if tall else (1122, 144)
    header_y = 48 if tall else (243 if blue else 268)
    header_height = 160 if tall else 210
    footer_y = 1736 if tall else 1310
    footer_height = 154 if tall else 360
    graphic_y = 540 if tall else 504
    note_size = 24 if tall else 28
    header_size = _header_size(data["header"], 50 if tall else 58, header_height,
                               bool(data.get("header_note")), note_size)
    duration, fps = data["duration"], data["fps"]
    scenes, animations, switches, pages = [], [], [], []
    first_statement = next((i for i, s in enumerate(data["scenes"]) if s["layout"] == "statement"), None)
    for index, scene in enumerate(data["scenes"]):
        start = scene["start"]
        end = data["scenes"][index + 1]["start"] if index + 1 < len(data["scenes"]) else duration
        mode = scene.get("presentation", "host" if index == first_statement else "graphic")
        if mode not in ("host", "graphic"):
            raise ValueError("scene.presentation must be host or graphic")
        switches.append({"at": start, "host": mode == "host"})
        if mode == "graphic":
            scenes.append(_scene(scene, start, end, animations))
            pages.append({"id": scene["id"], "start": start, "end": end})
    captions = ''.join(
        f'<div class="caption" id="cap-{i}">'
        f'<div class="caption-text">{_esc(caption["text"])}</div></div>'
        for i, caption in enumerate(data["captions"])
    )
    caption_times = [{"id": f"cap-{i}", "start": caption["start"], "end": caption["end"]}
                     for i, caption in enumerate(data["captions"])]
    footer = _identity(data) if blue else f'<div class="topic-copy">{_esc(data["title"])}</div>'
    note = f'<div class="header-note">{_esc(data["header_note"])}</div>' if data.get("header_note") else ''
    css = f"""
*{{box-sizing:border-box}}html,body{{margin:0;width:1080px;height:1920px;overflow:hidden}}
body{{font-family:'Noto Sans SC',sans-serif;color:var(--ink);background:var(--shell)}}
#root{{position:relative;width:1080px;height:1920px;overflow:hidden;
--shell:#111A1B;--panel:#1A2323;--ink:#F4F4F0;--dim:#C5D0CA;--gold:#F3BB76;--edge:#758371;
color:var(--ink);background:linear-gradient(180deg,#49514E 0%,#263632 42%,#111A1B 100%)}}
#root.identity-blue{{--shell:#101820;--panel:#354B55;--ink:#F4F4F0;--dim:#D7E1E5;--edge:#8398A0;
background:linear-gradient(180deg,#172630 0%,#101820 100%)}}
.shell-rule{{position:absolute;left:42px;top:214px;width:996px;height:3px;background:var(--gold);opacity:.45}}
.header-panel{{position:absolute;{_box(42, header_y, 996, header_height)};padding:20px 28px;text-align:center}}
.identity-blue .header-panel{{background:#172630;border:1px solid #435966;border-bottom:3px solid #8398A0;border-radius:16px}}
.header-copy{{font-size:{header_size}px;font-weight:600;line-height:1.3;white-space:pre-line;overflow-wrap:anywhere}}
.header-note{{font-size:{note_size}px;line-height:1.4;color:var(--gold);margin-top:12px;white-space:pre-line}}
#presenter-frame{{position:absolute;{_box(*window)};overflow:hidden;border:2px solid var(--gold);background:#0E1314;opacity:0;z-index:2}}
#presenter{{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;display:block}}
.identity-blue #presenter-frame{{border-color:#A7B8BE;background:#354B55;clip-path:polygon(18px 0,calc(100% - 18px) 0,100% 18px,100% calc(100% - 18px),calc(100% - 18px) 100%,18px 100%,0 calc(100% - 18px),0 18px)}}
.graphic-scene{{position:absolute;{_box(12, graphic_y, 1056, 594)};background:var(--panel);border:2px solid var(--edge);z-index:3;opacity:0}}
.scene-eyebrow{{position:absolute;{_box(52, 25, 952, 35)};font-size:25px;line-height:1.3;color:var(--gold);letter-spacing:1px}}
.scene-title{{position:absolute;{_box(52, 70, 952, 108)};font-weight:600;line-height:1.2;white-space:pre-line;overflow-wrap:anywhere}}
.scene-rule{{position:absolute;{_box(52, 175, 110, 3)};background:var(--gold)}}
.scene-lead{{position:absolute;{_box(52, 187, 952, 37)};font-size:27px;line-height:1.3;color:var(--dim)}}
.item,.scene-title,.scene-lead,.connector,.footer-run{{opacity:0}}
.item{{position:absolute;border:1px solid var(--edge);border-radius:12px;background:#142322;color:var(--ink)}}
.identity-blue .item{{background:#223741}}.item.emphasized{{border:2px solid var(--gold)}}
.item-overline{{position:absolute;left:20px;right:20px;height:32px;font-size:23px;line-height:1.3;color:var(--dim)}}
.item-title{{position:absolute;left:20px;right:20px;font-weight:600;line-height:1.25;white-space:pre-line;overflow-wrap:anywhere}}
.emphasized .item-title{{color:var(--gold)}}
.item-body{{position:absolute;left:20px;right:20px;height:90px;line-height:1.35;white-space:pre-line;overflow-wrap:anywhere;color:var(--dim)}}
.semantic-diagram{{position:absolute;left:50%;top:10px;transform:translateX(-50%);fill:none;stroke:var(--gold);stroke-width:3;stroke-linejoin:round}}
.diagram-title{{position:absolute;left:16px;right:16px;top:163px;height:45px;text-align:center;font-size:30px;line-height:1.3}}
.diagram-body{{position:absolute;left:16px;right:16px;top:212px;height:55px;text-align:center;font-size:24px;line-height:1.3;color:var(--dim)}}
.statement-copy{{position:absolute;left:24px;right:24px;top:26px;height:150px;color:var(--gold);font-weight:600;text-align:center;line-height:1.3;white-space:pre-line}}
.statement-body{{position:absolute;left:24px;right:24px;top:184px;height:70px;text-align:center;font-size:28px;line-height:1.3}}
.connector{{position:absolute;text-align:center;color:var(--gold)}}
.connector-label{{height:42px;font-size:23px;line-height:1.3}}.connector-arrow{{height:70px;font-size:57px;line-height:1}}
.scene-footer{{position:absolute;{_box(52, 490, 952, 78)};font-size:27px;line-height:1.4;color:var(--gold);text-align:center}}
.footer-run{{display:inline-block;margin:0 7px;white-space:pre-wrap}}
#captions{{position:absolute;left:40px;top:{caption_y}px;width:1000px;height:{caption_height}px;z-index:8}}
.caption{{position:absolute;inset:0;width:1000px;height:{caption_height}px;display:flex;align-items:center;justify-content:center;opacity:0}}
.caption-text{{width:1000px;max-height:{caption_height}px;font-size:{48 if tall else 42}px;line-height:1.35;font-weight:600;text-align:center;white-space:pre-line;overflow-wrap:anywhere;color:#F4F4F0}}
.footer-panel{{position:absolute;{_box(42, footer_y, 996, footer_height)};padding:28px;text-align:center}}
.identity-blue .footer-panel{{border:1px solid #435966;border-top:3px solid #8398A0;border-radius:16px;background:#1A2C38}}
.topic-copy{{font-size:{34 if tall else 42}px;line-height:1.5;color:var(--gold);white-space:pre-line;overflow-wrap:anywhere}}
.identity-name{{font-size:44px;line-height:1.4;color:var(--gold);font-weight:600;white-space:pre-line}}
.identity-role{{margin-top:12px;font-size:30px;line-height:1.5;white-space:pre-line}}
.identity-line{{margin-top:10px;font-size:28px;line-height:1.4;color:var(--dim);white-space:pre-line}}
"""
    script = f"""
window.__timelines=window.__timelines||{{}};
const tl=gsap.timeline({{paused:true}});
const switches={_json(switches)}, entrances={_json(animations)};
const pages={_json(pages)}, captions={_json(caption_times)};
tl.to({{}},{{duration:{duration},ease:'none'}},0);
switches.forEach(c=>tl.set('#presenter-frame',{{opacity:c.host?1:0}},c.at));
pages.forEach(c=>{{tl.set('#'+c.id,{{opacity:1}},c.start);tl.set('#'+c.id,{{opacity:0}},c.end);}});
captions.forEach(c=>{{tl.set('#'+c.id,{{opacity:1}},c.start);tl.set('#'+c.id,{{opacity:0}},c.end);}});
entrances.forEach(c=>tl.fromTo(c.selector,{{opacity:0,y:12}},{{opacity:1,y:0,duration:c.duration,ease:'power2.out',immediateRender:false}},c.at));
window.__timelines.main=tl;tl.pause(0);
"""
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=1080,height=1920">'
        f'<title>{_esc(data["title"])}</title><script src="assets/gsap.min.js"></script>'
        f'<style>{font_css}\n{css}</style></head><body>'
        f'<div id="root" class="{_esc(preset)}" data-composition-id="main" data-start="0" '
        f'data-duration="{duration}" data-width="1080" data-height="1920" data-fps="{fps}">'
        '<div class="shell-rule" data-layout-ignore></div>'
        f'<div class="header-panel"><div class="header-copy">{_esc(data["header"])}</div>{note}</div>'
        f'<div id="presenter-frame"><video id="presenter" class="clip" src="{_esc(media["presenter"])}" '
        f'data-start="0" data-duration="{duration}" data-track-index="1" muted playsinline></video></div>'
        + ''.join(scenes)
        + f'<audio id="voice" class="clip" src="{_esc(media["voice"])}" data-start="0" '
        f'data-duration="{duration}" data-track-index="2" data-volume="1"></audio>'
        f'<div id="captions">{captions}</div><div class="footer-panel">{footer}</div>'
        f'</div><script>{script}</script></body></html>'
    )
