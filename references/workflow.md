# 从已剪齐口播到成片

## 输入与风格

明确目标画幅、视频、校对字幕、原声音轨、preset 和新交付路径。来源或分组有歧义时只确认缺失项；已有明确说明不重复询问。保留原件，新项目使用独立目录。

输入必须已剪齐、从零开始且处于同一时间轴。先完成转写或粗剪再使用本流程，不用原片字幕套剪后视频。`presenter` 与 `voice` 始终必填，`audio_copy` 可选。

按 [styles.md](styles.md) 在四组方案中选 preset，确认支持目标画幅。用户未选风格且意图不明确时展示四组选择，或先建议一个并确认；明确要求旧模板或默认模板时用 `black-orange`。CLI 为兼容旧输入保留默认值：JSON 的 `style` 可选，CLI `--style` 显式覆盖 JSON，两者省略时为 `black-orange`。不支持的组合立即报错，不替换风格或擅自改画幅。

## 编排

1. 按口播含义分图解页并选六种版式之一，保留条件、主观判断与比喻语境。
2. 标题和卡片是图解摘要；`captions` 是已校对原口播。分别维护，保留字幕原文、分段与时码，不因换画幅或换风格重分字幕。
3. `scene.start` 与元素 `at` 使用整条剪辑的秒数。字幕不必吸附到帧；总时长必须落在完整帧上。
4. 金框知识窗需要控制人物/图解时，设置 `presentation: host|graphic`；默认首个 `statement` 为人物，其余图解。人物介绍按需要填 `identity`。纸墨/PPT 的 `source_note` 只填写用户实际提供的来源；没有来源就省略。
5. 检查正文容量及最长字幕。标题建议不超过 22 个汉字、卡片标题 10 个、正文 18 个；这是排版参考，实际 MP4 决定是否拆页。`identity-blue` 容量为姓名 20 字、身份 28 字、最多三条且每条 30 字，仍需留出实际字形余量。

字段见 [project-format.md](project-format.md)，构图见 [design.md](design.md)。新内容优先修改配置与媒体，沿用统一构建器。

## 构建与渲染

所有命令从 Skill 目录执行，首次使用运行 `npm ci`、`python3 scripts/doctor.py`。

```sh
python3 scripts/render.py --input work/my-video/project.json --style identity-blue --aspect portrait --output outputs/my-video-intro.mp4
```

脚本生成工程，执行 HyperFrames 检查、渲染、采用指定音轨并全片技术读回。默认工程为 `outputs/my-video-intro-project/`。可加 `--work-dir work/my-video-intro-project` 指定不存在的工程目录。

只构建工程：

```sh
python3 scripts/build.py --input work/my-video/project.json --style paper-ink --aspect landscape --output work/my-video-paper-project
```

渲染及 HyperFrames 检查需要允许临时 `127.0.0.1` 服务；不调用模型 API、不读取密钥。输入、成片、侧车和已有工程均不覆盖。失败后读取报错与检查结果，修正有证据的问题，用新目标重跑，不绕过校验。

## 验收

- 自动技术检查：尺寸、帧率、帧数、时长、音视频起点、全片解码；复制 AAC 音轨时再检查音频包和时间戳。可运行 `scripts/verify.py` 独立复核。
- 实际画面：检查全部版式、最长标题/正文/字幕、页面首尾、转场和出现时刻；真人另查头顶、眼睛、嘴和下颌。无人物版式也要检查文字层级与留白。
- 实际声音：连续视听检查声画同步，并逐字听审字幕。未完成时在交付说明中明确写出；技术通过、取帧或提示音测试不能替代。

音轨复制能证明编码数据保留，不能证明 `voice` 与 `audio_copy` 原本同内容、同剪辑或无偏移，使用前须确认。金框知识窗完整取景不等于人物一定清楚；仍应核查源分辨率、画面空白及人脸大小。

## 复用与交付

改画幅时保持字幕与声音、重排支持的内容，禁止裁切已合成横版冒充竖版。不同风格也遵循同样的输入、声音保留和验收规则。

交付 MP4、SRT、JSON 和工程位置，说明 preset、画幅、时长、音轨来源，以及实际完成的技术、画面、连续视听和听审范围。未确认的字幕或图解逐项列出，部分验收不写成全部通过。

需要复跑风格回归时使用 `scripts/verify_styles.py --output work/style-suite`；它生成匿名源和真实成片图库，详细命令见 [README.md](../README.md)。本机测试结果以 [docs/VALIDATION.md](../docs/VALIDATION.md) 为准。打包、本地安装和 GitHub 发布是不同阶段；本流程不默认创建仓库、推送或公开素材。
