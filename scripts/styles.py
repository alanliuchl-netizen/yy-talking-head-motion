"""The installed presets, their families and actually supported output aspects."""

STYLES = {
    'black-orange': {'name': '黑橙图解 · 右下圆窗', 'family': 'black-orange', 'aspects': ['landscape', 'portrait']},
    'black-orange-center': {'name': '黑橙图解 · 居中人物', 'family': 'black-orange', 'aspects': ['landscape', 'portrait']},
    'green-gold': {'name': '深绿金框 · 经典横窗', 'family': 'framed-knowledge', 'aspects': ['portrait']},
    'green-gold-portrait': {'name': '深绿金框 · 竖源完整取景', 'family': 'framed-knowledge', 'aspects': ['portrait']},
    'identity-blue': {'name': '蓝灰金框 · 人物介绍', 'family': 'framed-knowledge', 'aspects': ['portrait']},
    'paper-ink': {'name': '纸墨讲解 · 无人物阅读页', 'family': 'paper-editorial', 'aspects': ['landscape']},
    'ppt-bright': {'name': '横屏 PPT · 明亮配色', 'family': 'slide-deck', 'aspects': ['landscape']},
    'ppt-calm': {'name': '横屏 PPT · 沉稳配色', 'family': 'slide-deck', 'aspects': ['landscape']},
}


def resolve_style(preset, aspect=None):
    if not isinstance(preset, str) or preset not in STYLES:
        raise ValueError('Unknown style; run build.py --list-styles for installed presets')
    selected = STYLES[preset]
    if aspect is not None and aspect not in selected['aspects']:
        raise ValueError(f'{preset} supports only {", ".join(selected["aspects"])}')
    return selected
