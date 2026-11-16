# 第三方组件说明

本项目原创代码、文档与示例采用 MIT。项目代码许可不替代第三方条款，也不涵盖使用者提供的视频、声音、照片或其他素材。

依赖通过 `npm ci` 按锁文件安装。源码包不直接附带下列 JavaScript 或字体二进制。许可标识来自对应固定版本 npm 包；具体使用和再分发以完整条款为准。

| 组件 | 固定版本 | 许可与用途 |
| --- | --- | --- |
| HyperFrames | `0.8.149` | 本地 HTML 视频检查与渲染；npm 标注 `Apache-2.0`，该 npm 包未附独立 LICENSE 文件。 |
| GSAP | `3.14.2` | 时间轴动画，适用 GSAP Standard License，不是 MIT。 |
| Noto Sans SC（`@fontsource/noto-sans-sc`） | `5.3.1` | 中文无衬线字体，SIL Open Font License 1.1。 |
| Noto Serif SC（`@fontsource/noto-serif-sc`） | `5.3.1` | 纸墨与 PPT 标题使用的中文衬线字体，SIL Open Font License 1.1。 |

生成工程保留 `gsap.min.js` 头部原版权注释，并写入 `GSAP-NOTICE.txt`，记录版本、版权及[官方 Standard License](https://gsap.com/community/standard-license/)链接；该说明不等同于随附完整条款，不应将 GSAP 与项目一起统称为 MIT。

Noto 字体适用 [SIL Open Font License 1.1](https://openfontlicense.org/open-font-license-official-text/)。构建器只复制当前文案所需 Unicode 字符分片，保留各字体包随附许可：无衬线字体在工程 `assets/fonts/OFL.txt`，使用衬线字体时另有 `assets/fonts/serif/OFL.txt`。项目不分发系统苹方、宋体。

FFmpeg、FFprobe、Node.js、npm 与渲染浏览器由使用者的本地环境或依赖安装提供，不包含在本源码包中，各自适用原项目及实际构建版本的许可。

Talkcraft 上游本地核实为 PolyForm Noncommercial，本包不纳入其 runtime、卡片、音效或其他上游素材。它不属于上述八个 preset，也不是本包运行依赖。

独立 demo 使用 FFmpeg 生成的测试图形与六个短提示音。源码及公开示例不含真实客户姓名、真人素材、客户转写或文章照片；使用自己的素材时，其授权与公开范围由素材本身决定。
