# YY Talking Head Motion · v0.3.0

一个本地 Agent Skill：用户提供拍摄原片，由 Agent 完成**内容精剪、字幕校对与对时、声音整理、动效包装和成片验收**，交付完成基础剪辑的视频。也兼容 v0.2 的已剪视频仅包装模式。

用户不需要自己先剪辑、准备 SRT 或手写 JSON。默认按有效内容选择最佳表达、清理重录/重复与离题段、调整结构和节奏；未给时长时依据内容确定合适长度。语义取舍由运行 Skill 的 Agent 完成，本地辅助脚本不额外调用付费模型 API、不读取 API Key。精剪规则与辅助脚本见 [原片到成片流程](references/editing.md)。

包装仍提供四组视觉方案、八个 preset，支持画幅合计十个组合；六种内容版式共用剪后时间轴。

| 组 | preset | 输出画幅 | 区别 |
| --- | --- | --- | --- |
| 黑橙图解 | `black-orange`、`black-orange-center` | 16:9、9:16 | 两者横版相同；竖版分别为右下圆窗和居中人物窗。 |
| 金框知识窗 | `green-gold`、`green-gold-portrait`、`identity-blue` | 仅 9:16 | 经典横窗、按源比例完整取景、蓝灰金框人物介绍。 |
| 纸墨讲解 | `paper-ink` | 仅 16:9 | 无人物的阅读讲解页。 |
| 横屏 PPT | `ppt-bright`、`ppt-calm` | 仅 16:9 | 左下人物小窗，明亮、沉稳两套配色。 |

选择与边界见 [风格参考](references/styles.md)。不支持的画幅会明确拒绝，不自动换风格。实际测试范围、结果和未验收项以[验证报告](docs/VALIDATION.md)为准；本包不宣称 Linux、Windows 或从零安装浏览器已验收。匿名测试画面与提示音不能代表真实人脸裁切或逐字听审。

四组实际成片取帧，使用独立测试图形与提示音：

| 黑橙图解 | 蓝灰金框人物介绍 |
| --- | --- |
| ![黑橙圆窗测试帧](assets/previews/black-orange-portrait.jpg) | ![人物介绍测试帧](assets/previews/identity-blue-portrait.jpg) |

| 纸墨讲解 | 横屏 PPT · 沉稳配色 |
| --- | --- |
| ![纸墨讲解测试帧](assets/previews/paper-ink-landscape.jpg) | ![沉稳PPT测试帧](assets/previews/ppt-calm-landscape.jpg) |

完整八预设、十组合的可播放图库由下方 `verify_styles.py` 命令生成，入口为其输出目录内的 `index.html`。

## 用户怎样使用

安装后，在支持 Agent Skills 的工具中提供原片路径或可访问附件，并说明已有制作要求，例如：

> 使用 $yy-talking-head-motion，把这条原始口播内容精剪成适合发布的 9:16 视频。清理重录和重复，按内容调整结构和节奏，用深绿金框包装；保留事实与原意，完成字幕、声音和整片检查，给我成片、字幕及可编辑工程。

Agent 负责检查环境、本地转写、制定剪辑方案、重新对时字幕、编排动效并渲染；只询问确实影响结果的缺失项。目标是完成基础剪辑的成片，而非一条等待用户继续剪的粗剪。字幕歧义或素材缺陷确实无法解决时，会随成片集中标出，保留为待复核的发布候选。

“达到发布水平”以实际成片的剪辑、字幕、声音和画面检查为依据。技术读回、截图或回转写均不能单独证明逐字正确或全片视听通过；本版本的实际验证范围见 [验证报告](docs/VALIDATION.md)，旧版包装测试不自动证明新增精剪链路已通过。

## 安装与包装示例

准备 Python 3.9+、Node.js 22+、npm，以及 PATH 中可运行的 `ffmpeg`、`ffprobe`。项目内 `.npmrc` 指向 npm 官方仓库，不修改全局配置。首次安装依赖和渲染浏览器可能需要联网；依赖及浏览器就绪后，本地渲染不调用模型 API、不需要或读取 API Key。

将源码包解压为 `yy-talking-head-motion/`。已有该目录时从 `cd` 开始：

```sh
unzip yy-talking-head-motion-v0.3.0.zip
cd yy-talking-head-motion
npm ci
python3 scripts/doctor.py
python3 scripts/build.py --list-styles
python3 scripts/make_demo.py --output work/demo --source-aspect square
python3 scripts/render.py --input work/demo/project.json --style black-orange --aspect portrait --output outputs/demo-portrait.mp4
python3 scripts/render.py --input work/demo/project.json --style paper-ink --aspect landscape --output outputs/demo-paper.mp4
```

`make_demo.py` 生成独立的 18 秒测试素材：六种版式、FFmpeg 测试图形与六个短提示音，不含真人、语音、客户素材或 AI 生图。`--source-aspect` 接受 `square`（默认）、`portrait`、`landscape`，只控制源视频比例；输出比例由渲染命令选择。可公开的内容配置在 `examples/demo/project.json`。

若提示缺少浏览器，运行 `npm run hyperframes -- browser ensure` 查找或安装 Chrome，再用新的输出/工程名称重试。HyperFrames 检查会启动临时本机服务；执行环境必须允许监听 `127.0.0.1`。`doctor.py` 检查系统工具与依赖版本，浏览器可用性由实际检查与渲染确认，不能跳过检查直接出片。

每次渲染产生同名 `.mp4`、`.srt`、`.json`，默认工程目录位于输出旁，例如 `outputs/demo-portrait-project/`。工程保留 HTML、配置、本地媒体、所需字体字符分片与许可、GSAP 版权及许可链接。已有成片、侧车文件或工程时脚本停止；重做使用新名称。

独立复核和只构建工程：

```sh
python3 scripts/verify.py --video outputs/demo-portrait.mp4 --project outputs/demo-portrait-project/project.json
python3 scripts/build.py --input work/demo/project.json --style ppt-calm --aspect landscape --output work/demo-ppt-project
npm test
```

需要比对原编码音轨时，在 `verify.py` 命令后加 `--audio-reference` 和对应原音轨路径。渲染可用 `--work-dir work/new-project` 指定不存在的工程目录，`--workers 1` 至 `--workers 8` 调整并发。画幅接受 `portrait`、`landscape`、`9:16`、`16:9`。

## 从拍摄原片开始

仅包装已剪视频时无需 ASR 依赖。原片模式另建 Python 环境并安装固定的本地转写依赖：

```sh
python3 -m venv .venv-asr
.venv-asr/bin/python -m pip install -r requirements-asr.txt
```

Agent 先检查已有模型。默认使用本地缓存的 `large-v3`；首次缺少模型时显式允许下载，下载的是本地识别模型，不上传媒体：

```sh
.venv-asr/bin/python scripts/transcribe.py --input input/raw.mov --output work/source --model large-v3 --allow-model-download
```

已有模型时用 `--local-files-only`，或通过 `--model` 指定本地模型目录；两个下载策略参数互斥。CPU 上大模型可能较慢，模型和依赖不随源码包分发，不承诺从零下载的耗时或所有电脑都具备相同速度。

随后由 Agent 阅读转写、对照原声，自动编写有源词出处和删除理由的精剪方案，调用 `edit.py` 完成剪切、响度和新字幕，再完成 `project.json` 场景编排后调用 `render.py`。这些 JSON 是内部工程文件，用户不用手动制作。完整方案结构、命令与成片审校见 [内容精剪流程](references/editing.md)。

Agent 可在精剪方案的 `caption_groups` 中选择自然字幕分组，词顺序、完整覆盖、剪切点和源时码均受校验；不会在包装阶段重新手改字幕。HLG/PQ 原片需要具备 `zscale`、`tonemap` 的 FFmpeg，缺失会在创建输出目录前停止；Agent 可选择本机已有完整构建并通过 `edit.py --ffmpeg /path/to/ffmpeg` 指定。转换采用 1000 nit 基础层假设，经线性光与 Hable 映射到 SDR BT.709，不处理 Dolby Vision 动态元数据；实际高光/肤色仍需检查，实片验证范围见报告。

`edit.py` 的包装初稿带 `editing_stage: needs_motion_planning`；Agent 完成实际内容编排后才标记为 `motion_plan_reviewed`，未完成初稿会拒绝渲染。已剪齐输入的旧格式保持兼容。

成片后，Agent 对实际 MP4 回转写，使用 `compare_speech.py` 比对剪后语音，再运行 `review.py` 校验音轨、字幕与剪辑时间轴，测量响度并提取实际切点/场景/最长字幕帧表。即使回转写为 `PASS`，Agent 也必须阅读全部 `mismatches`；有漏词、多词或切点偏差时修方案和边界后重做，不能只调阈值。数字、否定或限定词的差异必须待复核；技术通过仍标记为 `TECHNICAL_PASS_REVIEW_PENDING`，不代替完整视听。可直接执行的 QA 命令见 [成片验收](references/editing.md#5-验收完成的成片)。

## 复跑全部风格

```sh
python3 scripts/verify_styles.py --output work/style-suite --parallel 2 --workers 2
```

该命令生成匿名方形、竖形源素材，实际渲染注册表中的十个 preset/画幅组合，保留逐项日志、MP4、取帧、`acceptance.json` 和可播放真实 MP4 的 `index.html` 图库。输出目录必须不存在。重复传入 `--style` 可缩小范围，例如 `--style green-gold --style green-gold-portrait`。结果以本次报告为准；生成图库不等于所有项目已通过。

## 安装为本地 Skill

别人可以下载完整源码包，或直接克隆到自己的 Skill 目录；需要在支持 Agent Skills 的工具中调用。Skill 会使用对方电脑上的本地渲染环境，不连接本项目作者的电脑。

Codex 的 macOS 安装命令：

```sh
mkdir -p ~/.agents/skills
git clone https://github.com/alanliuchl-netizen/yy-talking-head-motion.git ~/.agents/skills/yy-talking-head-motion
cd ~/.agents/skills/yy-talking-head-motion
npm ci
python3 scripts/doctor.py
```

Git 已存在的非空目标目录会拒绝克隆；保留旧版后选择新的安装位置。也可以把下面这段话交给自己的 Agent 执行：

> 请从 https://github.com/alanliuchl-netizen/yy-talking-head-motion 安装 yy-talking-head-motion Skill。先检查 Python、Node、FFmpeg 和现有同名 Skill，保留旧版，按 README 安装依赖并运行 doctor，告诉我是否需要开启新会话。

把整个目录复制到 `~/.agents/skills/yy-talking-head-motion`，包含脚本、模板、参考文档、示例和依赖锁。目标已存在时保留旧版、使用新安装位置，不合并覆盖。首次安装可从当前目录的上一级运行：

```sh
mkdir -p ~/.agents/skills
test ! -e ~/.agents/skills/yy-talking-head-motion && cp -R yy-talking-head-motion ~/.agents/skills/yy-talking-head-motion
cd ~/.agents/skills/yy-talking-head-motion
npm ci
python3 scripts/doctor.py
```

按所用 Agent 的发现方式刷新或开启新会话。调用示例：

> 使用 $yy-talking-head-motion，从提供的拍摄原片完成内容精剪、字幕和动效包装，使用 9:16 identity-blue，检查剪辑与成片质量，输出到新的文件名。若我提供的是已剪齐视频和校对字幕，则只做包装。

安装位置只用于发现 Skill。正式项目和成片可放在独立工作目录，通过命令参数指定；媒体必须放在输入 JSON 所在项目目录内。

## 已剪视频的仅包装模式

以下工程文件由 Agent 整理；若直接使用底层 CLI，在新目录准备 `project.json`、已剪齐的视频与同时间轴声音。`media.presenter`、`media.voice` 必填；`media.audio_copy` 可选，用于复制 AAC 编码音轨。纸墨不显示人物，但统一输入格式仍要求 `presenter`；PPT 保留左下人物小窗。视频自带声音不会自动替代 `voice`。

JSON 可选 `style`，显式 CLI `--style` 优先；为兼容旧输入，省略两者的 CLI 默认值为 `black-orange`。Agent 面对未选风格的请求，会结合素材建议一种并说明；意图确实不明确时集中确认。明确要求旧模板或默认模板时按黑橙执行。

可选 `identity` 保存姓名、身份和简介；知识窗可用 `scene.presentation` 切换人物与图解；纸墨/PPT 可用 `scene.source_note` 展示用户提供的真实来源，禁止生成证据。详见 [项目格式](references/project-format.md)、[工作流](references/workflow.md)及[设计规则](references/design.md)。

仅包装输入的字幕须已校对，保留原文、分段和时码。原片模式的字幕由精剪链路生成并由 Agent 审校。媒体从零开始且与 `duration` 对齐；帧率只接受整数 24、30、60，总时长须落在完整帧上。媒体路径只接受输入 JSON 目录内相对路径，禁止绝对路径、`..` 或越界符号链接。

## 验收与范围

所有风格共用声音保留、禁止覆盖及全片技术读回：输入与输出保护、HyperFrames 工程检查、成片尺寸、帧率、帧数、时长、音视频起点与完整解码；复制音轨时可比对音频包和时间戳。技术检查后仍需查看实际 MP4，连续视听并逐字核对字幕。

技术检查不能判断观点真伪、字幕逐字准确、口型同步或人脸取景是否合适。Agent 需检查实际成片的切点、字幕、语义、最长文案、人物取景和全部转场，修复可处理的基础问题，保留未决项；内容超量先拆页，不能删字幕来让页面好看。

原片模式允许有理由的内容取舍与重排、切点微淡化及响度整理，并保留原片与剪辑来源映射。包装阶段以**剪后音轨与时间轴**为准，保持字幕及声音，不拿最终精剪音轨和完整原片要求为字节相同。已剪视频的仅包装模式继续保留所提供的声音和字幕时码。

本包不生成配音、数字人、图片、音乐或音效，不抓取外部素材，不登录账号发布，也不包含运动教学、产品展示或灰模 3D。Talkcraft 不纳入本包，详见第三方说明。

## 依赖、许可与发布状态

本地转写依赖由 `requirements-asr.txt` 固定，模型按需另行安装；模型许可与实际来源见 [第三方说明](THIRD_PARTY_NOTICES.md)。语义精剪使用宿主 Agent 的现有能力，不需要为本 Skill 另外配置模型 API；宿主本身仍需可用，费用与隐私按其使用方式决定。云端 Agent 会按正常对话机制处理它读取的转写文字，不能把整个 Agent 流程称为完全离线。

渲染依赖锁定 HyperFrames `0.8.149`、GSAP `3.14.2`、`@fontsource/noto-sans-sc` `5.3.1`、`@fontsource/noto-serif-sc` `5.3.1`。字体从 npm 包按所需 Unicode 分片复制，保留对应许可；不依赖或分发系统苹方、宋体。

本项目原创代码、文档和示例采用 MIT，允许使用、修改、商用与再分发，需保留许可证与版权声明。第三方组件适用各自条款，尤其 GSAP 不是 MIT；见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。源码包排除运行依赖、客户姓名、真实人物素材、文章照片、私有路径与密钥；公开示例使用独立测试内容。

v0.3.0 源码包名为 `yy-talking-head-motion-v0.3.0.zip`，旧版 ZIP 保留。可用 `python3 scripts/make_release.py --output releases/yy-talking-head-motion-v0.3.0.zip` 生成新的源码包；目录或包的生成不代表已对外发布。
