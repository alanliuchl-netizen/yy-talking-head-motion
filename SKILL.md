---
name: yy-talking-head-motion
description: Edit raw talking-head recordings into a concise, subtitled motion-graphics video, or package an already edited talking-head video with supplied checked captions. Use when a user wants content editing, retake selection, subtitles and one of the local talking-head styles.
---

# YY 口播动效包装

从拍摄原片完成内容精剪、字幕与动效包装，交付完成基础剪辑的成片；也兼容已剪视频的仅包装模式。v0.3.0 保留四组视觉方案、八个 preset、十个支持的画幅组合，见 [风格选择](references/styles.md)。语义判断由运行本 Skill 的 Agent 完成，本地脚本负责转写、精确剪切、对时、渲染与技术检查，不要求额外模型 API 或密钥。

## 识别输入

- **拍摄原片：默认内容精剪。** 按 [内容精剪流程](references/editing.md) 完成原片检查、转写、取舍与重排、字幕校对、切点处理、包装和成片验收。用户只需提供原片及制作意图，不把 SRT、剪辑方案或 JSON 编写交回用户。
- **已剪齐的视频与校对字幕：仅包装。** 保留其声音、字幕原文、分段与时码，直接按下方包装流程执行。用户明确只要保真粗剪时，保留内容和表达顺序，仅清理明确无效部分。
- 已有授权和明确要求时连续执行，只确认影响结果的缺失项。未给目标时长时，依据有效信息量选定合适长度并说明；不为凑时长丢失事实、数字、否定、条件或必要例子。多条素材是否属于同一成片、来源顺序不清时先澄清。
- 确认目标画幅、视觉方案与新交付路径。风格未定时结合素材建议一种，并说明选择；用户有明确风格时不得替换。不支持的 preset/画幅组合报错。
- 首次使用按 [README.md](README.md) 安装依赖，运行 `python3 scripts/doctor.py`。本地转写需要可用的 ASR Python 环境和模型；模型首次下载须显式允许，已缓存时离线使用。脚本不读取 API Key。

## 内容精剪的结果

Agent 选择最有效的表达，删除重录、重复和离题段，改善开头、结构、衔接与节奏。每个保留或删除的源词均有出处与理由；只能剪选原声，不能用改字幕伪造没有说过的话。改字需对照原声，保留原转写与修改证据；疑点集中列出。

重排后重新检查指代、因果、前提、数字、否定与限定条件。未决问题使用 `needs_review`，不把不确定内容悄悄删掉，也不将粗剪或检查通过直接称为可发布成片。声音可做切点微淡化和响度整理；不自动生成配音、人物、图片、音乐或音效，不自动降噪。

## 包装与成片验收

1. 按 [项目格式](references/project-format.md) 整理最终剪辑时间轴的 `project.json`。原片模式由脚本生成初稿后，Agent 实际编排场景：将 `editing_stage: needs_motion_planning` 完成到 `motion_plan_reviewed`；未完成的初稿不可渲染。包装阶段不重分已校对字幕、不改字幕时码。
2. 按 [风格选择](references/styles.md)，从图示、对照、流程、要点卡、前后变化、大字结论六种版式中选择适合内容的组合。图解摘要忠实于口播；人物介绍才填 `identity`，有用户提供的真实来源才填 `source_note`。容量与构图见 [设计规则](references/design.md)。
3. 从本 Skill 目录执行，例如：

   ```sh
   python3 scripts/render.py --input work/my-video/project.json --style black-orange --aspect portrait --output outputs/my-video-portrait.mp4
   ```

   `--style` 覆盖 JSON 的 `style`；旧输入均省略时 CLI 默认 `black-orange`。横版用 `--aspect landscape`，亦接受 `9:16`、`16:9`。`python3 scripts/build.py --list-styles` 查看支持清单。
4. 检查全片技术读回与原声回转写一致性，并查看实际成片全部切点、最长字幕、场景和转场。人物窗口另查头顶、嘴、下颌；检查响度、爆音、吞字、音画同步与重复/断句。自动检查、取帧与回转写各有边界，不能写成连续视听或逐字听审已通过。
5. Agent 修复基础剪辑、字幕和包装问题后，按 [内容精剪流程](references/editing.md) 与 [交付工作流](references/workflow.md) 交付 MP4、SRT、可编辑工程、剪辑来源映射与验收说明。报告实际完成的审校及未决项；未完成全片视听时标为发布候选，不冒称已完成听审。

新建输出，拒绝覆盖成片、侧车文件或工程；媒体只接受项目内相对路径，拒绝 `..`、绝对路径和越界符号链接。原片不修改。换画幅重排支持的版式，不裁切已合成横版冒充竖版。本包不执行账号发布，不包含运动教学、产品展示或灰模 3D。
