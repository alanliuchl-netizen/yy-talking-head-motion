# 四组方案与八个 preset

`style` 选择视觉 preset，`layout` 选择单页内容结构，两者独立。当前注册表有四组方案、八个 preset、十个支持的 preset/画幅组合。

| 组 | preset | 画幅 | 适用与差异 |
| --- | --- | --- | --- |
| 黑橙图解 `black-orange` | `black-orange` | 横、竖 | 图解为主；横版左下人物窗，竖版右下圆窗。 |
| 黑橙图解 `black-orange` | `black-orange-center` | 横、竖 | 横版与上一项相同；竖版为较大的居中人物窗。 |
| 金框知识窗 `framed-knowledge` | `green-gold` | 仅竖 | 深绿金框、经典横向人物窗，人物/图解共用主窗。 |
| 金框知识窗 `framed-knowledge` | `green-gold-portrait` | 仅竖 | 根据源视频纵横比例完整取景，竖源用高窗，其余用横窗。 |
| 金框知识窗 `framed-knowledge` | `identity-blue` | 仅竖 | 蓝灰金框，底部姓名、身份和简介。 |
| 纸墨讲解 `paper-editorial` | `paper-ink` | 仅横 | 无人物阅读讲解页，纸底墨字、衬线标题。 |
| 横屏 PPT `slide-deck` | `ppt-bright` | 仅横 | 幻灯片结构，明亮配色。 |
| 横屏 PPT `slide-deck` | `ppt-calm` | 仅横 | 同组幻灯片结构，沉稳配色。 |

横版为 `landscape` / `16:9` / 1920×1080；竖版为 `portrait` / `9:16` / 1080×1920。相同黑橙横版仍在注册表中分别验证，因此共十个组合，不代表十套视觉风格。

## 选择方式

用户未选风格且意图不明确时，先展示四组选择或建议一个并确认。用户明确要求旧模板或默认模板时可使用 `black-orange`。CLI 为兼容旧配置仍保留默认：JSON 可选 `"style": "green-gold-portrait"`；显式 CLI `--style` 覆盖 JSON；两者省略时使用 `black-orange`。

```sh
python3 scripts/build.py --list-styles
python3 scripts/render.py --input work/my-video/project.json --style green-gold-portrait --aspect portrait --output outputs/my-video-portrait.mp4
```

不支持的 preset/画幅组合报错，不更换 preset。需要某组尚未支持的画幅时先说明限制；不要把现有合成画面裁切后冒充支持。

## 可选内容字段

- 金框知识窗使用 `scene.presentation: "host"|"graphic"` 控制当前主窗。默认首个 `statement` 显示人物，其余场景显示图解；若没有 `statement`，默认全部图解。该开关不改变时码。
- `identity-blue` 可用 `identity.name`、`identity.role`、`identity.lines`；每个字段均可省略。未提供非空 identity 时使用 `header/header_note`。容量与示例见 [项目格式](project-format.md)。
- 纸墨/PPT 可显示 `scene.source_note`，只填写用户实际提供的来源。没有来源则不显示，不编作者、刊物、引文、数字或证据。

纸墨不显示人物，PPT 保留左下人物小窗；统一输入均要求已剪齐的 `presenter`、`voice`，`audio_copy` 可选。所有 preset 共用六种 `layout`、原字幕分段与时码、原声音轨保留、相对路径保护、禁止覆盖和全片技术读回。

## 对照验证

运行 `python3 scripts/verify_styles.py --output work/style-suite --parallel 2 --workers 2`，生成匿名方形及竖形源素材并渲染全部十个组合。可重复传入 `--style` 限定 preset；脚本保留 `acceptance.json`、逐项日志、实际 MP4、取帧与 `index.html` 可播放图库。必须使用不存在的输出目录。

图形和提示音只用于检查布局及技术链路；真实人物取景、口型与字幕仍需成片复核和连续视听。发布包实际验收情况见 [验证报告](../docs/VALIDATION.md)，不把脚本提供的能力写成已完成的结果。
