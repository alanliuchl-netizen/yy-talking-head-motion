---
name: yy-talking-head-motion
description: Package already edited talking-head video and checked subtitles with local explanatory motion graphics, framed knowledge windows, paper reading pages or PPT layouts while preserving the supplied voice and timing.
---

# YY 口播动效包装

把已剪齐口播与校对字幕包装为图解视频。v0.2.0 提供四组视觉方案、八个 preset；各 preset 只支持登记的画幅，见 [风格选择](references/styles.md)。保留输入声音、字幕原文、分段和时码。

本 Skill 负责内容编排、人物窗口和本地渲染。转写、粗剪、配音、数字人、模型调用、外部素材获取与发布不在范围内；运动教学、产品展示和灰模 3D 也不在本包范围内。

## 开始前

- 确认已剪齐的视频、校对字幕、原声音轨、目标画幅、视觉方案和新交付路径；已有明确说明时直接执行，只确认影响结果的缺失项。
- 用户未选风格且意图不明确时，展示四组选择，或建议一个方案并确认；不要悄悄替换风格。明确要求旧模板或默认模板时可使用 `black-orange`。
- 输入必须从零开始、剪辑一致且时长对齐。多条素材的分组与顺序按用户说明，不自行拼接或改剪。
- 新建项目目录，媒体放在该目录内。JSON 只接受目录内相对媒体路径，拒绝绝对路径、`..` 和越界符号链接。
- 所有命令从本 Skill 目录运行。首次使用按 [README.md](README.md) 安装依赖并运行 `python3 scripts/doctor.py`。渲染使用临时 `127.0.0.1` 服务，不调用模型 API、不读取密钥。

## 执行

1. 按 [项目格式](references/project-format.md) 整理 `project.json`。图解忠实于口播，摘要与字幕分别维护；不重分字幕、不改时码。
2. 按 [风格选择](references/styles.md) 选择 preset，并从图示、对照、流程、要点卡、前后变化、大字结论六种版式中组织内容。需要人物介绍时才填 `identity`；只有用户提供真实来源时才填 `source_note`。构图与容量见 [设计规则](references/design.md)。
3. 执行本地渲染，例如：

   ```sh
   python3 scripts/render.py --input work/my-video/project.json --style black-orange --aspect portrait --output outputs/my-video-portrait.mp4
   ```

   `--style` 覆盖 JSON 的 `style`；为兼容旧输入，两者都省略时 CLI 使用 `black-orange`。横版使用 `--aspect landscape`，也接受 `9:16`、`16:9`。不支持的 preset/画幅组合必须报错，不换风格。可用 `python3 scripts/build.py --list-styles` 查看清单。
4. 检查脚本的全片技术读回，再查看实际 MP4 中全部版式、最长字幕和转场。人物窗口另查头顶、嘴与下颌；完整取景、圆窗或居中窗口均需按真实源画面检查。
5. 按 [工作流](references/workflow.md) 交付 MP4、SRT、JSON 和工程位置，区分自动技术检查、实际画面检查和连续视听、逐字听审。技术通过、取帧或提示音测试不能写成真人听审通过。

所有风格共用输入保护、声音保留和验收流程。不得覆盖成片、侧车文件或工程；重做使用新名称。未获用户明确要求时，不生成配音、人脸、图片，不加音乐或音效，不再次降噪。换画幅只重排支持的版式，不裁切已合成横版冒充竖版。
