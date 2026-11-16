"""Independent landscape editorial layouts for the local talking-head Skill.

The caller validates copy/timing, copies media and fonts, and owns provenance.
This module only produces HTML; it does not fetch assets or alter the edit.
"""
import html
import json
import re


PRESETS = {'paper-ink', 'ppt-bright', 'ppt-calm'}


def _e(value):
    return html.escape(str(value), quote=True)


def _j(value):
    return (json.dumps(value, ensure_ascii=False).replace('</', '<\\/')
            .replace('\u2028', '\\u2028').replace('\u2029', '\\u2029'))


def _n(value):
    return format(float(value), '.9g')


def _marked(text, words):
    words = sorted({w for w in words if w}, key=len, reverse=True)
    if not words:
        return _e(text)
    match = re.search('|'.join(re.escape(w) for w in words), text)
    if not match:
        return _e(text)
    return (_e(text[:match.start()]) + '<strong>' + _e(match.group())
            + '</strong>' + _e(text[match.end():]))


def _diagram(name):
    """Small geometric diagrams, without external images or embedded copy."""
    if name == 'cube':
        shape = ('<path d="M80 75 178 25 290 75 192 128Z M80 75V175L192 226'
                 ' 290 175V75 M192 128V226"/><path class="diagram-accent" '
                 'd="M80 75 192 128 290 75 M192 128V226"/>')
    else:
        shape = ('<path d="M48 180 148 70H324L224 180Z M81 143H257 '
                 'M115 107H291 M106 180 206 70 M165 180 265 70"/>')
    return '<svg class="diagram" viewBox="0 0 370 250" aria-hidden="true">' + shape + '</svg>'


CSS = r'''
*{box-sizing:border-box}html,body{margin:0;width:1920px;height:1080px;overflow:hidden}
body{font-family:"Noto Sans SC",sans-serif;color:var(--ink);background:var(--paper)}
#root{position:relative;width:1920px;height:1080px;overflow:hidden;background:var(--paper);color:var(--ink);font-family:"Noto Sans SC",sans-serif}
.page{position:absolute;inset:0;visibility:hidden;opacity:0;background:var(--paper);overflow:hidden}
.topbar{position:absolute;left:96px;right:96px;top:52px;height:52px;display:flex;justify-content:space-between;gap:48px;align-items:center;font-size:27px;z-index:6}
.topbar b{font-weight:600}.topbar span{color:var(--muted);font-size:24px;text-align:right}
.top-rule{position:absolute;left:96px;right:96px;top:116px;height:1px;background:var(--rule);z-index:6}
.eyebrow{position:absolute;left:96px;top:141px;font-size:26px;line-height:1.4;color:var(--accent);letter-spacing:2px}
.page-number{position:absolute;right:98px;top:142px;font-size:24px;color:var(--muted);font-variant-numeric:tabular-nums}
h1,h2,p{margin:0}.headline{position:absolute;white-space:pre-line;overflow-wrap:anywhere;text-wrap:balance;font-weight:600}
.reveal{opacity:0}.items{position:absolute}.item{position:absolute;white-space:pre-line;overflow-wrap:anywhere}
.item-overline{font-size:27px;line-height:1.35;margin-bottom:16px;color:var(--muted)}
.item-title{font-weight:600;line-height:1.32}.item-body{line-height:1.55;margin-top:23px}
.item-index{font-variant-numeric:tabular-nums}.lead,.footer,.source-note{position:absolute;white-space:pre-line;overflow-wrap:anywhere}
.source-note{font-size:24px;line-height:1.35;color:var(--muted)}
.connector{position:absolute;text-align:center;font-size:52px;line-height:1.2;color:var(--accent)}
.connector-label{font-size:24px;margin-bottom:8px;color:var(--muted)}
.diagram{display:block;width:100%;height:210px;margin:0 auto 26px;fill:none;stroke:currentColor;stroke-width:2.5;stroke-linejoin:round}
.diagram-accent{stroke:var(--accent);stroke-width:4}
#voice{display:none}#captions{position:absolute;z-index:10}
.caption{position:absolute;inset:0;opacity:0;display:flex;align-items:center;justify-content:center;text-align:center;white-space:pre-line;overflow-wrap:anywhere;font-size:42px;line-height:1.36;font-weight:600}
.caption strong{color:var(--accent);font-weight:800}

/* Paper pages use an article column, marginal copy and rules, without a host. */
.paper-ink{--paper:#f6f4f0;--ink:#1c1c1c;--muted:#625e57;--accent:#b4523c;--rule:#cfc9c0}
.paper-ink .headline,.paper-ink .item-title{font-family:"Noto Serif SC","Noto Sans SC",serif;font-weight:600}
.paper-ink .headline{left:116px;top:230px;width:640px;font-size:80px;line-height:1.35;letter-spacing:-1px}
.paper-ink .eyebrow{left:116px;top:175px}.paper-ink .page-number{top:175px;right:116px}
.paper-ink .items{left:865px;top:255px;width:935px;height:490px;border-left:1px solid var(--rule);padding-left:48px}
.paper-ink .item{left:48px;right:0;padding:14px 0 20px 56px;border-bottom:1px solid var(--rule)}
.paper-ink .item-index{position:absolute;left:0;top:19px;font-size:24px;color:var(--accent)}
.paper-ink .item-title{font-size:43px}.paper-ink .item-body{font-size:30px;margin-top:13px;color:var(--muted)}
.paper-ink .item-overline{font-size:23px;margin-bottom:9px}
.paper-ink .count-4 .item{padding:6px 0 8px 56px}
.paper-ink .count-4 .item-title{font-size:34px;line-height:1.25;padding-right:225px}
.paper-ink .count-4 .item-body{font-size:25px;line-height:1.3;margin-top:6px}
.paper-ink .count-4 .item-overline{position:absolute;right:0;top:10px;max-width:210px;font-size:20px;line-height:1.25;text-align:right;margin:0}
.paper-ink .lead{left:120px;top:620px;width:610px;font-size:31px;line-height:1.6;color:var(--muted)}
.paper-ink .footer{left:865px;top:770px;width:935px;font-size:29px;line-height:1.45;color:var(--accent)}
.paper-ink .source-note{left:116px;top:837px;width:1688px;max-height:64px}
.paper-ink #divider{position:absolute;left:116px;right:116px;top:914px;height:1px;background:var(--rule);z-index:7}
.paper-ink #captions{left:116px;top:928px;width:1688px;height:102px}
.paper-ink .reading-rule{position:absolute;left:116px;bottom:28px;width:1688px;height:3px;background:var(--rule);z-index:8}
.paper-ink .reading-progress{width:100%;height:100%;background:var(--accent);transform:scaleX(0);transform-origin:left center}
.paper-ink .layout-compare .items,.paper-ink .layout-diagram .items{border-left:0;padding:0}
.paper-ink .layout-compare .item,.paper-ink .layout-diagram .item{left:auto;width:440px;height:490px;padding:76px 20px 20px 0;border-top:3px solid var(--accent);border-bottom:0}
.paper-ink .layout-compare .item-index,.paper-ink .layout-diagram .item-index{top:24px}
.paper-ink .layout-compare .item-title,.paper-ink .layout-diagram .item-title{font-size:48px}
.paper-ink .layout-diagram .item{padding-top:65px}.paper-ink .layout-diagram .item-title{font-size:43px}
.paper-ink .layout-flow .items,.paper-ink .layout-timeline .items{border-left:2px solid var(--accent)}
.paper-ink .layout-flow .item,.paper-ink .layout-timeline .item{padding-left:50px;border-bottom:0}
.paper-ink .layout-flow .item-title,.paper-ink .layout-timeline .item-title{font-size:52px}
.paper-ink .connector{left:815px;top:453px;width:85px;font-size:37px;background:var(--paper)}
.paper-ink .connector-label{font-size:20px}
.paper-ink .layout-statement .headline{left:116px;top:204px;width:1580px;font-size:48px;line-height:1.4;color:var(--muted)}
.paper-ink .layout-statement .items{left:170px;top:340px;width:1580px;height:390px;padding-left:44px;border-left:6px solid var(--accent)}
.paper-ink .layout-statement .item{left:44px;top:0!important;width:1490px;padding:0;border:0}
.paper-ink .layout-statement .item-title{font-size:104px;line-height:1.36;color:var(--ink)}
.paper-ink .layout-statement .item-body{font-size:37px;margin-top:34px}
.paper-ink .layout-statement .item-index{display:none}
.paper-ink .layout-statement .lead{top:740px;width:1550px}

/* PPT has a host rail and three page structures, shared by both palettes. */
.ppt-bright{--paper:#F0EEDC;--ink:#252820;--muted:#484C42;--accent:#5a4230;--rule:#9b9d8b;--card-a:#CF95B8;--card-b:#D3E65B;--card-c:#E1BFAE;--card-d:#AEC3A1;--card-ink:#252820;--end-paper:#CF95B8;--end-ink:#252820}
.ppt-calm{--paper:#ECE8DF;--ink:#24313A;--muted:#58616a;--accent:#675537;--rule:#a8ada7;--card-a:#243D4B;--card-b:#A8B09B;--card-c:#C1A77F;--card-d:#D1CEC5;--card-ink:#24313A;--end-paper:#243D4B;--end-ink:#F4F1E8}
.ppt .headline{left:96px;top:190px;width:1650px;font-family:"Noto Serif SC","Noto Sans SC",serif;font-size:84px;line-height:1.3;font-weight:600}
.ppt .eyebrow{top:142px}.ppt .items{left:500px;top:352px;width:1240px;height:480px}
.ppt .item{top:0;height:480px;border-radius:22px;padding:30px 34px;background:var(--card-a);color:var(--card-ink)}
.ppt .item:nth-of-type(2){background:var(--card-b)}.ppt .item:nth-of-type(3){background:var(--card-c)}.ppt .item:nth-of-type(4){background:var(--card-d)}
.ppt-calm .item:first-child{color:#F4F1E8}.ppt-calm .item:first-child .item-overline{color:#DFE1DD}
.ppt-calm .item:first-child .diagram-accent{stroke:#F4F1E8}
.ppt .item-index{font-size:66px;line-height:1.15;margin-bottom:38px;font-family:"Noto Serif SC","Noto Sans SC",serif}
.ppt .item-title{font-size:51px;line-height:1.35}.ppt .item-body{font-size:33px;line-height:1.55}
.ppt .item-overline{font-size:25px;color:inherit;opacity:.85}
.ppt .lead{left:96px;top:356px;width:330px;max-height:225px;font-size:32px;line-height:1.5}
.ppt .footer{left:500px;top:850px;width:1240px;font-size:29px;line-height:1.35}
.ppt .source-note{left:500px;top:890px;width:1240px;max-height:58px;font-size:22px;line-height:1.3}
.ppt #presenter-frame{position:absolute;left:74px;top:634px;width:288px;height:360px;overflow:hidden;border-radius:10px;z-index:7;background:var(--card-a)}
.ppt #presenter{width:100%;height:100%;object-fit:cover;object-position:center 40%;display:block}
.ppt #divider{position:absolute;left:430px;right:96px;top:952px;height:1px;background:var(--rule);z-index:8}
.ppt #captions{left:430px;top:965px;width:1394px;height:94px}
.ppt .count-4 .item{height:224px;padding:22px 27px}
.ppt .count-4 .item-index{display:none}.ppt .count-4 .item-title{font-size:42px}.ppt .count-4 .item-body{font-size:29px;margin-top:12px;line-height:1.4}
.ppt .count-4 .item-overline{font-size:23px;margin-bottom:8px}
.ppt .layout-diagram .item-index{display:none}.ppt .layout-diagram .diagram{height:240px;margin-bottom:25px}
.ppt .layout-diagram .item-title{font-size:50px}.ppt .layout-diagram .item-body{font-size:31px;margin-top:14px}
.ppt .page-compare .headline{left:96px;top:190px;width:485px;max-height:390px;font-size:76px;line-height:1.3}
.ppt .page-compare .items{left:680px;top:270px;width:1060px;height:570px}
.ppt .page-compare .item{height:570px;width:515px;padding:34px 40px}
.ppt .page-compare .item-index{font-size:118px;margin-bottom:55px}
.ppt .page-compare .item-title{font-size:53px}.ppt .page-compare .item-body{font-size:35px;line-height:1.6;margin-top:30px}
.ppt .page-compare .lead{left:96px;top:535px;width:470px;font-size:29px;max-height:80px}
.ppt .page-thesis{background:var(--end-paper);color:var(--end-ink)}
.ppt .page-thesis .eyebrow,.ppt .page-thesis .page-number{color:inherit}
.ppt .page-thesis .headline{left:500px;top:190px;width:1240px;font-size:82px;line-height:1.35}
.ppt .page-thesis .items{left:500px;top:465px;width:1240px;height:350px}
.ppt .page-thesis .item{top:0;width:570px;height:280px;padding:32px;background:var(--paper);color:var(--ink);border-radius:18px}
.ppt .page-thesis .item-index{font-size:30px;margin-bottom:24px;color:var(--muted)}
.ppt .page-thesis .item-title{font-size:54px}.ppt .page-thesis .item-body{font-size:32px;margin-top:21px}
.ppt .page-thesis .connector{left:1078px;top:545px;width:84px;font-size:52px;color:var(--end-ink)}
.ppt .page-thesis .connector-label{color:var(--end-ink)}
.ppt .layout-statement .items{top:410px;height:380px}
.ppt .layout-statement .item{width:1240px;height:380px;padding:35px 0;background:transparent;color:var(--end-ink)}
.ppt .layout-statement .item-title{font-family:"Noto Serif SC","Noto Sans SC",serif;font-size:112px;line-height:1.35}
.ppt .layout-statement .item-body{font-size:39px;line-height:1.45;margin-top:30px}
.ppt .layout-statement .item-index{display:none}.ppt .page-thesis .lead{top:365px;left:500px;width:1240px;font-size:30px}
.ppt .page-thesis .footer,.ppt .page-thesis .source-note{color:var(--end-ink)}
'''


def render_html(data, aspect, media, font_css, preset, source_info):
    """Return a full 1920x1080 document for validated project data.

    ``source_info`` belongs to the caller's manifest; only an explicitly supplied
    scene ``source_note`` is printed. PPT titles also use Noto Serif SC, so the
    caller should include its 600-weight faces with the supplied font CSS.
    """
    if aspect not in ('landscape', '16:9'):
        raise ValueError(f'{preset} supports landscape / 16:9 only')
    if preset not in PRESETS:
        raise ValueError('Unknown editorial preset: ' + str(preset))
    paper = preset == 'paper-ink'
    scenes = data['scenes']
    all_ids = set()
    for scene in scenes:
        all_ids.add(scene['id'])
        for item in scene['items']:
            all_ids.add(item['id'])
        for key in ('lead', 'connector', 'footer'):
            node = scene.get(key)
            if node:
                all_ids.update(run['id'] for run in node.get('runs', [node]))
    prefix = 'editorial-'
    while any(value.startswith(prefix) for value in all_ids):
        prefix = 'e-' + prefix
    reveal, pages, fragments = [], [], []
    for index, scene in enumerate(scenes):
        sid = scene['id']
        start = float(scene['start'])
        end = float(scenes[index + 1]['start']) if index + 1 < len(scenes) else float(data['duration'])
        layout, count = scene['layout'], len(scene['items'])
        page_kind = 'compare' if layout in ('compare', 'timeline') else ('thesis' if layout in ('flow', 'statement') else 'context')
        classes = f'page layout-{layout} count-{count} page-{page_kind}'
        title_size = ''
        if not paper and page_kind == 'context':
            title_size = f' style="font-size:{max(58, min(88, int(1650 / max(1, len(scene["title"])))))}px"'
        elif not paper and page_kind == 'compare' and len(scene['title']) > 15:
            title_size = ' style="font-size:64px"'
        contents = []
        for item_index, item in enumerate(scene['items']):
            if paper:
                if layout in ('compare', 'diagram'):
                    style = f'left:{item_index * 490}px;top:0'
                else:
                    style = f'top:{item_index * (490 / count):.3f}px;min-height:{490 / count:.3f}px'
            elif page_kind == 'compare':
                style = f'left:{item_index * 545}px'
            elif page_kind == 'thesis':
                style = f'left:{item_index * 670}px'
            elif count == 4:
                style = f'left:{(item_index % 2) * 632}px;top:{(item_index // 2) * 248}px;width:608px'
            else:
                gap = 24
                width = (1240 - gap * (count - 1)) / count
                style = f'left:{item_index * (width + gap):.3f}px;width:{width:.3f}px'
            inner = f'<div class="item-index" aria-hidden="true">{item_index + 1:02d}</div>'
            if item.get('overline'):
                inner += '<div class="item-overline">' + _e(item['overline']) + '</div>'
            if layout == 'diagram' and item.get('diagram'):
                inner += _diagram(item['diagram'])
            inner += '<h2 class="item-title">' + _e(item['title']) + '</h2>'
            if item.get('body'):
                inner += '<p class="item-body">' + _e(item['body']) + '</p>'
            contents.append(f'<article id="{_e(item["id"])}" class="item reveal" style="{style}">{inner}</article>')
            reveal.append([item['id'], float(item['at']), min(.38, max(.04, end - float(item['at'])))])
        extras = []
        for key in ('lead', 'footer'):
            node = scene.get(key)
            if not node:
                continue
            if node.get('runs'):
                parts = []
                for run in node['runs']:
                    parts.append(f'<span id="{_e(run["id"])}" class="reveal">{_e(run["text"])}</span>')
                    reveal.append([run['id'], float(run['at']), .3])
                extras.append(f'<div class="{key}">' + ''.join(parts) + '</div>')
            else:
                extras.append(f'<div class="{key} reveal" id="{_e(node["id"])}">{_e(node["text"])}</div>')
                reveal.append([node['id'], float(node['at']), .3])
        connector = scene.get('connector')
        if connector:
            label = '<div class="connector-label">' + _e(connector['label']) + '</div>' if connector.get('label') else ''
            extras.append(f'<div id="{_e(connector["id"])}" class="connector reveal">{label}{_e(connector.get("text", "→"))}</div>')
            reveal.append([connector['id'], float(connector['at']), .3])
        if scene.get('source_note'):
            extras.append('<div class="source-note">' + _e(scene['source_note']) + '</div>')
        fragments.append(f'''<section id="{_e(sid)}" class="{classes}">
<div class="eyebrow">{_e(scene['eyebrow'])}</div><div class="page-number">{index + 1:02d} / {len(scenes):02d}</div>
<h1 class="headline"{title_size}>{_e(scene['title'])}</h1><div class="items">{''.join(contents)}</div>{''.join(extras)}</section>''')
        pages.append([sid, start, end, not paper and page_kind == 'thesis'])
    captions = ''.join(f'<div class="caption" id="cap-{i}">{_marked(c["text"], data.get("emphasis_words", []))}</div>' for i, c in enumerate(data['captions']))
    duration, fps = _n(data['duration']), int(data['fps'])
    presenter = '' if paper else f'''<div id="presenter-frame"><video id="presenter" class="clip" src="{_e(media['presenter'])}" data-start="0" data-duration="{duration}" data-track-index="1" muted playsinline></video></div>'''
    progress_id = prefix + 'progress'
    progress = f'<div class="reading-rule" data-layout-ignore><div id="{progress_id}" class="reading-progress"></div></div>' if paper else ''
    script = f'''window.__timelines=window.__timelines||{{}};
const PAGES={_j(pages)},REVEALS={_j(reveal)},CAPTIONS={_j(data['captions'])};
const tl=gsap.timeline({{paused:true}});
PAGES.forEach(([id,start,end,thesis])=>{{const el=document.getElementById(id);tl.set(el,{{autoAlpha:1}},start);tl.set(el,{{autoAlpha:0}},end);}});
REVEALS.forEach(([id,at,duration])=>{{tl.fromTo(document.getElementById(id),{{opacity:0,y:12}},{{opacity:1,y:0,duration,ease:'power2.out',immediateRender:false}},at);}});
CAPTIONS.forEach((c,i)=>{{const el=document.getElementById('cap-'+i);tl.set(el,{{opacity:1}},c.start);tl.set(el,{{opacity:0}},c.end);}});
'''
    if preset == 'ppt-calm':
        script += '''PAGES.forEach(([id,start,end,thesis])=>{
const ink=thesis?'#F4F1E8':'#24313A',muted=thesis?'#DADBD3':'#58616a',line=thesis?'#aeb8b8':'#a8ada7';
tl.set(document.querySelector('.topbar'),{color:ink},start);
tl.set(document.querySelector('.topbar span'),{color:muted},start);
tl.set(document.querySelectorAll('.caption'),{color:ink},start);
tl.set(document.querySelectorAll('.caption strong'),{color:thesis?'#E9CDA3':'#675537'},start);
tl.set(document.querySelectorAll('.top-rule,#divider'),{backgroundColor:line},start);
});
'''
    if paper:
        script += f"tl.fromTo(document.getElementById({_j(progress_id)}),{{scaleX:0}},{{scaleX:1,duration:{duration},ease:'none',immediateRender:false}},0);\n"
    script += 'window.__timelines.main=tl;tl.pause(0);'
    body_class = preset if paper else preset + ' ppt'
    return f'''<!doctype html><html lang="zh-CN" class="landscape"><head><meta charset="utf-8"><meta name="viewport" content="width=1920,height=1080"><title>{_e(data['title'])}</title><script src="assets/gsap.min.js"></script><style>{font_css}\n{CSS}</style></head><body class="{body_class}">
<div id="root" data-composition-id="main" data-start="0" data-duration="{duration}" data-fps="{fps}" data-width="1920" data-height="1080">
{''.join(fragments)}<div class="topbar"><b>{_e(data['header'])}</b><span>{_e(data.get('header_note', ''))}</span></div><div class="top-rule" data-layout-ignore></div>
{presenter}<audio id="voice" class="clip" src="{_e(media['voice'])}" data-start="0" data-duration="{duration}" data-track-index="2" data-volume="1"></audio><div id="divider" data-layout-ignore></div><div id="captions">{captions}</div>{progress}
</div><script>{script}</script></body></html>'''
