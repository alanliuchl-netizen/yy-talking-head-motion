# 从原片到口播成片

本流程供执行 Skill 的 Agent 使用。用户提供本地原片或可访问附件，说明主题、用途和已有要求即可；转写、方案、字幕和工程 JSON 都由 Agent 整理。缺少必要资料时集中澄清，不把基础剪辑交回用户，也不逐步重复索取已给过的授权。

## 先读素材，再作内容取舍

先检查视频与音轨、旋转信息、清晰度、实际内容和可用拍摄段。默认目标是**内容精剪**：选最好的一次表达，清理准备动作、重录、重复和离题内容，建立自然的开头、发展和结尾；按语义调整段落顺序，并在词边界附近保留自然呼吸。

用户给了目标时长和必留信息就据此执行；未给时长时，先读完整转写，按有效信息量选长度并说明，不先定一个删减比例。内容已经紧凑时可以少剪。不要只机械删静音后交付，也不要为制造强开头拼出原片没有的论断。

原意约束覆盖数字、否定、概率、适用范围、前提和条件。允许删除一个完整且离题的论述，但不得只保留它的结论而丢失必要前提。段落重排后重新判断“它”“这个”“刚才”等指代是否仍成立，例子是否仍在解释同一观点，因果是否被倒置。

多条视频先确认它们是同一主题的多次拍摄，还是分别制作的内容。不同主题不自行拼成一条。当前辅助脚本一次处理一个源视频；跨源合成需另行准备统一、可追溯的源素材，不把单源精剪说成多机位或多素材剪辑。

## 1. 本地转写

从 Skill 目录运行。ASR Python 环境按 README 安装 `requirements-asr.txt`；以下 `.venv-asr/bin/python` 仅示意该独立环境的解释器。

```sh
.venv-asr/bin/python scripts/transcribe.py --input input/raw.mov --output work/source --model large-v3 --local-files-only
```

默认只使用缓存。首次没有模型时，在用户允许联网下载本地模型的范围内显式加 `--allow-model-download`，与 `--local-files-only` 互斥；也可在 `--model` 后提供已有本地模型目录。首次安装不需要 API Key，不会把原视频或声音上传给转写服务。语义精剪仍由当前 Agent 读取转写并判断；使用云端 Agent 时，这些文字按宿主的正常对话机制处理。模型下载失败或没有可用语音时明确停止，不编造字幕。

新目录保存源文件副本、`transcript.json` 与 `transcript.md`。源副本哈希与原片一致；转写词保留固定 ID、源时码和识别置信度，时间基于音视频共同原点，不能独立重置音轨而抹掉真实 A/V 偏移。保留这些原始记录，后续修字和剪辑另存方案。

完整阅读转写，对准备语、重录与重复候选作标记。低置信词、专名、数字和同音疑点对照对应原片，不能只靠上下文改成顺口的说法。当前 Agent 看不到或听不到的内容要如实列为未完成的检查。

## 2. Agent 编写内容精剪方案

使用源词 ID 决定取舍，写入源工程内新的 `edit-plan.json`。下面是结构示意，ID 必须替换为真实转写中的 ID，不能直接当成任意视频的方案：

```json
{
  "version": 1,
  "mode": "content-edit",
  "source_sha256": "从 transcript.media.sha256 原样复制",
  "transcript_fingerprint": "从 transcript.fingerprint 原样复制",
  "title": "一个清楚的主题",
  "header": "主题短标识",
  "goal": "去掉两次重录，将清楚的结论提前，保留必要例子与条件",
  "segments": [
    {
      "id": "clip-one",
      "word_ids": ["w000010", "w000011"],
      "reason": "完整且清楚的主张，作为开头",
      "role": "hook"
    },
    {
      "id": "clip-two",
      "word_ids": ["w000003", "w000004", "w000005"],
      "reason": "解释上述主张的前提，重排后指代仍明确",
      "role": "context"
    }
  ],
  "omissions": [
    {
      "word_ids": ["w000001", "w000002"],
      "reason": "准备语，不承载正文信息"
    },
    {
      "word_ids": ["w000006", "w000007", "w000008", "w000009"],
      "reason": "同一表达的未完成重录，采用后面完整版本"
    }
  ],
  "corrections": [],
  "caption_groups": [
    {"word_ids": ["w000010", "w000011"]},
    {"word_ids": ["w000003", "w000004", "w000005"]}
  ],
  "review": {
    "facts_and_qualifiers": "pass",
    "continuity": "pass",
    "transcript": "pass",
    "notes": ["已按输出顺序逐段复查前提与指代"],
    "unresolved": []
  }
}
```

方案的 `source_sha256` 与 `transcript_fingerprint` 必须分别匹配 `transcript.media.sha256` 和 `transcript.fingerprint`；转写或源片变更后必须重新审校方案，不能复用旧方案。每个片段内的 `word_ids` 必须是源转写中连续的一段。片段数组顺序决定输出顺序；同一词不能重复使用。全部源词都必须且只能归入一个保留片段或一个有理由的删除组，不允许静默遗漏。`padding_before`、`padding_after` 可选，用于可用空隙内的切点留白；实际允许范围以脚本校验为准，不能延伸到被删除的邻词。

字幕改字记录使用 `corrections`：每项含 `word_id`、`text`、`reason`、`evidence`，例如记录核对原声的源时段和判断依据。保留原词文本，修改只用于对应字幕展示；删除一句话走剪辑方案，不能以清空字幕代替剪掉声音。不得为了通顺扩写或把错读内容在字幕中改成没说过的观点。脚本拒绝通过 `corrections` 自动改变数字、否定或限定词；即使怀疑识别有误，也先记录源音频疑点并进入待复核流程，不用改字幕绕过保护。尚不确定的字词、缺失前提或无可用重录写入 `review.unresolved`，相关检查标为 `needs_review`。

可选 `caption_groups` 由 Agent 在精剪方案内按自然语意选择字幕分组，每项为 `{"word_ids": ["保留的源词 ID"], "text": "可选的原话与标点"}`。分组按最终输出顺序完整覆盖所有保留词且每词一次，不得跨剪切点；`text` 省略时使用保留词原文，提供时只能整理标点，不能改写原话或数字。字幕起止由对应源词映射推导，不能手填猜测时码。发现分组不自然时修改精剪方案并输出新版本；不要在包装阶段直接改 `project.json` 的字幕来绕过来源一致性检查。

`review` 是 Agent 的审校结论与证据记录，不是脚本能证明语义正确的凭证。第一次选完素材后，按输出顺序另读一遍，核对论证、数字、否定、条件、指代与结尾；必要时修剪辑方案，而非只删掉问题标记。

## 3. 精确剪切、声音整理与字幕对时

```sh
python3 scripts/edit.py --transcript work/source/transcript.json --plan work/source/edit-plan.json --output work/edited --fps 30 --max-edge 1920
```

脚本按方案生成 `presenter.mp4`、`voice.wav`、`audio-copy.m4a`、`captions.srt`、`edit.json` 和包装 `project.json` 初稿。原片哈希、保留和删除的源词、源时码到输出时码的映射均保留，源文件不修改；输出目录必须不存在。

原片若为 HLG/PQ HDR，`edit.py` 检查 FFmpeg 是否具有 `zscale` 和 `tonemap`，不足时在创建输出目录前停止。Agent 应先寻找本机已有的完整构建；需要指定可执行文件时使用 `--ffmpeg /path/to/ffmpeg`，例如：

```sh
python3 scripts/edit.py --transcript work/source/transcript.json --plan work/source/edit-plan.json --output work/edited-hdr --ffmpeg /path/to/ffmpeg
```

HDR 处理把 BT.2020 基础层转为线性光，采用 **1000 nit 峰值假设与 Hable 色调映射**后转换为 SDR BT.709，不是只改颜色标签；`edit.json` 记录转换与假设。不处理 Dolby Vision RPU 动态元数据，必须检查实际肤色、高光与白位。元数据不受支持时停止，不猜测颜色参数；HLG/PQ 的实际验收范围分别以验证报告为准，不把检测到某传递函数视为已验证该类实片。

音视频使用同一来源时钟和剪切范围。先准确裁掉删除区域，再将片段补到整帧；补齐只能重复末帧或补静音，不能把已删除的邻词重新带回。切点作微淡化，默认整理至约 -16 LUFS、-1.5 dBTP；`--skip-normalize` 保留剪后响度，不绕过切点和时长检查。响度整理不等于去噪，也不会重造声线。检查低音量素材放大后的底噪，存在问题时按证据处理或列出。

字幕在**新剪辑时间轴**上由保留词重新生成。检查断句、最长行、读速、首尾词和所有切点，避免切在字内、字幕跨到下一段、重排后时码未变。不得为通过版式检查均摊或虚造字幕时间。

原声保持的比较对象分两阶段：剪辑阶段保留所选原声的内容与音色，允许已说明的切点和响度处理；包装阶段以剪后 `audio-copy.m4a` 为权威，最终音轨与它比较，不将最终精剪音轨和完整原片要求为字节相同。

## 4. Agent 完成动效编排

`edit.py` 输出的 `project.json` 标记 `editing_stage: needs_motion_planning`，只是剪后媒体、字幕与时间轴的衔接稿。Agent 阅读剪后内容，按 [项目格式](project-format.md) 与 [风格参考](styles.md) 完成场景、摘要、出现时刻及身份信息；完成实际审校后改为 `motion_plan_reviewed`。渲染器拒绝未完成初稿，防止通用占位页面被当成最终包装。

按内容需要使用六种版式，不强行每种都用，也不把整片做成重复大字页。场景安排服从已剪好的原声和字幕，不重新改写字幕、改时码或再次删句。检查人物取景、标题容量、字幕安全区与图解的真实含义。

```sh
python3 scripts/render.py --input work/edited/project.json --style black-orange --aspect portrait --output outputs/final.mp4
```

渲染失败先查实际错误，新名称重做，不能跳过工程检查或覆盖已有成片。已剪齐输入直接执行该阶段，兼容旧 `project.json`。

## 5. 验收完成的成片

先对**实际最终 MP4**重新转写，再比对剪后预期语音；所有输出均使用新目录或新文件名：

```sh
.venv-asr/bin/python scripts/transcribe.py --input outputs/final.mp4 --output work/final-asr --model large-v3 --local-files-only
python3 scripts/compare_speech.py --edit work/edited/edit.json --transcript work/final-asr/transcript.json --video outputs/final.mp4 --output outputs/speech-roundtrip.json
python3 scripts/review.py --video outputs/final.mp4 --project outputs/final-project/project.json --edit work/edited/edit.json --roundtrip outputs/speech-roundtrip.json --output work/final-qa
```

`compare_speech.py` 校验回转写确实来自该最终视频，默认相似度阈值为 `0.97`，差异报告带两侧词 ID 与可用源时段。**`PASS` 仍可能包含少量非保护词差异，Agent 必须逐条阅读全部 `mismatches`。** 发现多词、漏词或切点裁切偏差时，对照实际声音检查来源；例如被删除的前词声音漏入保留片段，应调整方案、保留完整可听短语或选择安全边界，并重做精剪、包装与回转写，不能只调低阈值或修改报告状态。

数字、单位、否定或限定词发生差异时始终为 `NEEDS_REVIEW`，不能通过调低 `--threshold` 绕过。回转写只检查 ASR 一致性，不证明原声逐字正确。

`review.py` 校验完整解码、尺寸/帧数/时长、剪后音轨包一致性与字幕和精剪时间轴的一致性，测量最终响度与真峰值，并从实际视频提取各切点前后、场景和最长字幕的帧，生成帧表、联系表与 `report.json`。没有自动发现问题时状态仍为 `TECHNICAL_PASS_REVIEW_PENDING`；有语音差异、未决语义问题或相关声音测量问题时为 `NEEDS_REVIEW`。脚本不执行连续视听，也不把这些状态当作发布许可。

源副本、转写缓存与真实视频的 QA 文件留在该用户私有项目中，不打入开源 Skill 源码包。技术检查完成后，Agent 检查**实际最终 MP4**，完成下列事项并记录证据：

- 剪辑：逐个切点检查吞字、爆音、断句、黑闪与不自然跳切；重录和重复确已清理。
- 语义：按最终播放顺序确认主题、指代、条件、数字、否定、例子和结论，未制造新的因果或论断。
- 字幕：逐句对照声音，检查专名、数字、缺字、读速、首尾与切点同步；最终回转写可查丢句/重句和大范围错位，不能证明识别文字就是原声事实。
- 画面与声音：全部场景、转场、最长文案、人物嘴部和下颌、字幕遮挡、音画同步、响度和底噪。
- 文件：完整解码、帧数、时长、音视频起点、剪后音轨包一致性、输入哈希与来源映射。

自动检查与实际帧表只证明对应项目；没有逐字听审或连续视听就明确写出。未决问题、无法可靠修复的素材缺陷和缺少的审校保留为 `needs_review`，不能靠改状态消除。Agent 应先修复可处理的基础剪辑问题，再把完整成片交给用户作最终观看；不是让用户拿粗剪继续完成基础剪辑。

交付 MP4、同步 SRT、可编辑包装工程、`edit.json` 来源映射/剪辑记录和简短验收说明。区分“技术检查通过”“Agent 审校完成”“仍需复核的发布候选”；只有实际完成相应语义、画面和声音检查后，才报告对应完成度。本 Skill 不替用户登录平台发布，也不保证任意低质原片无需复核即可发布。
