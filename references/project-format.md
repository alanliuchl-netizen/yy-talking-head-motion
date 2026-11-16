# project.json 格式

输入为 UTF-8 JSON，`version` 固定为 `1`，v0.3.0 保持旧配置兼容。可公开的六版式配置见 `examples/demo/project.json`；运行 `scripts/make_demo.py --output work/demo` 后，`work/demo/project.json` 与相邻媒体可直接构建。

原片内容精剪由 `edit.py` 衔接生成媒体、字幕与此结构，用户无需编写 JSON。生成初稿带 `editing_stage: needs_motion_planning`，Agent 完成实际场景编排并审校后改为 `motion_plan_reviewed`；未完成初稿不能渲染。旧的已剪齐配置没有该字段时保持兼容。本页时码均属于最终剪辑时间轴。

## 最小结构

以下是字段示意，媒体文件需自行准备并与 3 秒时间轴对齐：

```json
{
  "version": 1,
  "style": "black-orange",
  "title": "知识口播示例",
  "header": "一个清楚的结论",
  "header_note": "原声图解",
  "duration": 3,
  "fps": 30,
  "media": {
    "presenter": "assets/presenter.mp4",
    "voice": "assets/voice.wav"
  },
  "emphasis_words": ["先想清楚"],
  "captions": [
    {"start": 0, "end": 3, "text": "先想清楚，再开始行动。"}
  ],
  "scenes": [
    {
      "id": "scene-one",
      "start": 0,
      "eyebrow": "行动顺序",
      "title": "先想清楚，再行动",
      "title_emphasis": ["先想清楚"],
      "layout": "statement",
      "items": [
        {"id": "conclusion", "at": 0.5, "title": "明确下一步"}
      ]
    }
  ]
}
```

## 顶层字段

| 字段 | 含义 |
| --- | --- |
| `version` | 必填，整数 `1`。 |
| `style` | 可选，八个 preset 之一；显式 CLI `--style` 优先于 JSON，均省略时为 `black-orange`。支持画幅见 [styles.md](styles.md)。 |
| `title` | 必填，工程与输出的内容标题。 |
| `header` | 必填，画面顶部短标识。 |
| `header_note` | 可选，补充说明；黑橙竖版隐藏，知识窗用于顶部或身份区，纸墨/PPT 用于顶部。 |
| `duration` | 必填，有限正数秒；`duration × fps` 必须落在完整帧上。 |
| `fps` | 必填，整数 `24`、`30` 或 `60`。 |
| `media` | 必填，仅接受下列三个媒体键。 |
| `identity` | 可选，人物介绍的 `name`、`role`、`lines` 对象，当前由 `identity-blue` 显示。 |
| `emphasis_words` | 可选，字幕关键词字符串数组；显色依 preset。黑橙每条字幕只强调首个匹配位置。 |
| `captions` | 必填，按时间排序的校对字幕数组。 |
| `scenes` | 必填，按 `start` 严格递增的非空图解场景数组。 |

### 媒体

`presenter` 是人物窗口视频，`voice` 是工程预览及默认成片声音，二者必填。纸墨不显示人物，但当前统一格式仍要求 `presenter`；PPT 显示左下人物小窗。`audio_copy` 可选，是供成片直接复制的现有编码音轨；复制模式使用 AAC。省略时把提供的 `voice` 编码为 AAC。

三个媒体必须从零开始，与输入的 `duration` 对齐；脚本按帧容差检查。`voice` 和 `audio_copy` 必须由执行者确认属于同一剪辑。人物视频中的自带音轨不会自动使用。

视频扩展名支持 `.mp4/.mov/.m4v/.webm`；声音支持 `.wav/.m4a/.aac/.mp3/.flac/.ogg/.mp4/.webm`；复制音轨支持包含 AAC 的 `.m4a/.aac/.mp4`。扩展名之外仍会实际探测流类型、时长和音轨编码，扩展名不能替代媒体检查。

媒体路径相对输入 JSON 所在目录解析，只允许目录内文件。例如 `assets/presenter.mp4`。拒绝 `../presenter.mp4`、绝对路径、网络地址或解析后位于项目目录外的符号链接。将需要的媒体复制到新项目内，再更新路径。

### 字幕

每条字幕包含 `start`、`end`、`text`。时间满足 `0 ≤ start < end ≤ duration`，前后不重叠，可保留真实停顿。文字应为校对后的原口播，不能为空；换画幅或 preset 均不重分字幕、不改原文或时码。

### 人物介绍 identity

对象只接受 `name`、`role`、`lines`，三者均可省略；前两项为字符串，`lines` 为字符串数组。例如：

```json
{
  "style": "identity-blue",
  "identity": {
    "name": "示例讲解者",
    "role": "内容讲解",
    "lines": ["这是一条独立演示简介"]
  }
}
```

`identity-blue` 当前容量上限为 `name` 20 字、`role` 28 字、`lines` 最多三条且每条 30 字，超出会拒绝构建。建议留出实际字形与换行余量，最终检查 MP4。未提供非空 `identity` 时，人物介绍区回退到 `header` 与可选 `header_note`。示例身份不代表真实客户或讲解者。

## 场景与出现时刻

每个场景包含 `id`、`start`、`eyebrow`、`title`、`layout`、`items`。可选 `title_emphasis`、`lead`、`connector`、`footer`、`presentation`、`source_note`。

首场景从 `0` 开始。场景持续到下一场景的 `start`，末场景持续到 `duration`。子元素的 `at` 使用整条时间轴的秒数，必须落在所属场景内，不能等于场景结束时间；出现后保持到场景退出。

所有显式 `id` 全局唯一，使用字母开头及字母、数字、连字符、下划线。不要使用保留的 `root`、`presenter-frame`、`presenter`、`voice`、`divider`、`captions`、`cap-N`，也不要占用自动生成的 `<scene-id>-label`、`<scene-id>-title`、`<scene-id>-line`。

### 人物/图解切换与来源

- `presentation` 可选值为 `"host"` 或 `"graphic"`，只影响金框知识窗组的主窗显示。默认首个 `statement` 场景为 `host`，其余为 `graphic`；没有 `statement` 则默认全部图解。显式值覆盖此默认，不改变场景或字幕时码。
- `source_note` 是可选字符串，纸墨/PPT 显示为来源小字。只有用户提供真实来源时才填，没有则省略。它不执行检索或核实，不编作者、刊物、引文、数字或证据；其他组当前不显示该字段。

### 六种 layout

| `layout` | 用途 | `items` 数量 |
| --- | --- | --- |
| `diagram` | 两个线框图示的关系 | 2 |
| `compare` | 两种状态或方案对照 | 2 |
| `flow` | 两步流程或因果关系 | 2 |
| `cards` | 并列要点 | 1–4 |
| `timeline` | 前后变化 | 2 |
| `statement` | 大字结论 | 1 |

每个 item 包含 `id`、`at`、`title`；可选 `overline`、`body`、布尔值 `emphasis`。`diagram` 可选值是 `cube`、`plane`；图形只是语义占位，使用前确认适合当前内容。

### 可选节点

- `lead`：`{"id":"lead-one","at":0.4,"text":"一段引导语"}`。
- `connector`：包含 `id`、`at`，可加 `label` 与 `text`；`text` 默认为箭头。位于前两个 item 之间。
- `footer`：普通形式包含 `id`、`at`、`text`，可加关键词数组 `emphasis`。
- `footer.runs`：分段出现的页脚文本。每段包含 `id`、`at`、`text`，可加 `emphasis`；提供 runs 时按这些段落生成，不再同时显示普通 footer 文本。

页脚分段示例：

```json
{
  "footer": {
    "runs": [
      {"id": "foot-first", "at": 1.2, "text": "明确问题"},
      {"id": "foot-second", "at": 2.0, "text": "再选择方法", "emphasis": ["选择方法"]}
    ]
  }
}
```

输入配置描述内容、语义结构和时间，preset 控制布局与视觉。生成工程中的 `project.json` 另含选定 `style`、`style_name`、`style_family`、画幅、尺寸、总帧数及已复制媒体路径，供成片技术复核使用。不支持的 preset/画幅组合明确拒绝，不自动换风格。
