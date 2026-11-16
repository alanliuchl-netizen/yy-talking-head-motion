# v0.2.0 多风格本地验证报告

日期：2026-11-16。结论：四组视觉方案、八个预设、十个已登记画幅组合全部实际渲染并通过读回；独立源码包重新安装后，两个新增渲染器的代表预设复验通过。

## 本机完整矩阵

```sh
npm ci
python3 scripts/doctor.py
npm test
python3 scripts/verify_styles.py --output work/style-suite --parallel 2 --workers 2
```

每项使用独立生成的18秒测试图形与六个短提示音，包含六种语义版式。竖源适配使用360×640源视频，其余使用640×640源。两种黑橙横版布局相同，分别验收并不表示两套不同横版风格。

| 预设 | 画幅 | 输出尺寸 | 结果 |
| --- | --- | --- | --- |
| 黑橙图解 · 右下圆窗 | landscape | 1920×1080 | PASS |
| 黑橙图解 · 右下圆窗 | portrait | 1080×1920 | PASS |
| 黑橙图解 · 居中人物 | landscape | 1920×1080 | PASS |
| 黑橙图解 · 居中人物 | portrait | 1080×1920 | PASS |
| 深绿金框 · 经典横窗 | portrait | 1080×1920 | PASS |
| 深绿金框 · 竖源完整取景 | portrait | 1080×1920 | PASS |
| 蓝灰金框 · 人物介绍 | portrait | 1080×1920 | PASS |
| 纸墨讲解 · 无人物阅读页 | landscape | 1920×1080 | PASS |
| 横屏 PPT · 明亮配色 | landscape | 1920×1080 | PASS |
| 横屏 PPT · 沉稳配色 | landscape | 1920×1080 | PASS |

所有组合均为30fps、540帧、18秒；完整音视频解码通过，流起点为0。每条845个AAC包的payload、PTS、duration均与对应原测试音轨一致。所有输出SRT字节完全相同，输入示例文件SHA256前后不变。每项HyperFrames的lint/runtime/layout/contrast均0错误、0警告。

Skill格式检查通过；13项输入/输出保护测试通过，包含越界、覆盖、特殊媒体后缀、身份字段容量、未知风格和不支持画幅的提前拒绝。

已查看所有新增预设六种版式的实际解码帧及人物/图解切换；横版长标题发现单字孤行后改为均衡换行，并完整复跑paper-ink、ppt-bright、ppt-calm三项，新的检查与音轨读回均通过。实际取帧用于源码README样张，可播放图库展示验收MP4，均不是生成效果承诺或客户案例。

## 源码包独立安装复验

在新的临时目录解压候选源码包，未读取原工作区的依赖、字体、媒体或成片。候选包SHA256：`e08d56c8a13f5c39e8984f40fc9614d8586037ae505b79744f8be730fb1dd7f2`。

```sh
npm ci --cache .npm-cache --fetch-retries=2 --fetch-retry-mintimeout=1000 --fetch-retry-maxtimeout=5000
python3 scripts/doctor.py
npm test
python3 scripts/build.py --list-styles
python3 scripts/verify_styles.py --output work/clean-sample --style green-gold-portrait --style ppt-calm --parallel 2 --workers 2
```

首次npm安装遇一次公共仓库连接重置，重试成功。doctor全部通过、13项测试通过、8预设/10画幅登记正确。两条代表预设分别为1080×1920和1920×1080，各30fps/540帧/18秒，完整解码、845个原AAC包及时间、字幕一致性、输入哈希和全部工程检查均通过；另用verify.py和FFprobe读回一致。不支持的PPT竖版、深绿横版被拒绝，未创建工程。

候选中的脚本、模板、示例和锁文件在复验后仍与ZIP逐字节一致；最终源码仅补充和校正文档、验证报告及实际取帧预览，渲染脚本和依赖锁与被测版本一致。

## 环境、资源及范围

环境：macOS arm64，Node22.23.2、npm10.9.8、Python3.9.6、FFmpeg/FFprobe8.1.2；实际渲染浏览器为已有缓存HeadlessChrome152.0.7977.30。依赖固定HyperFrames0.8.149、GSAP3.14.2、Noto Sans SC5.3.1、Noto Serif SC5.3.1。

字体从独立安装的npm依赖提取所需Unicode分片，每种字体保留OFL；GSAP保留原版权头及许可链接。源码包不包含系统苹方/宋体、客户姓名、真实人物素材、文章照片、API密钥、运行依赖或渲染工程。README中的JPEG为本项目匿名示例的实际取帧。

本次按用户确认仅整理口播相关风格；运动教学、产品拼贴、灰模3D未加入。Talkcraft上游采用PolyForm Noncommercial，未将其现成卡片、runtime或音效并入当前源码稿。

未验证Linux/Windows、从零安装浏览器、真人面部裁切、口型、真实口播逐字听审或全片连续人工视听。自动检查与取帧不替代这些项目；字体替换与通用内容版式提取也不表示对旧客户工程逐像素复刻。现有公开示例验证不保证任意长文案都能直接容纳，实际项目仍需逐页检查。

用户已于2026-11-16确认采用MIT公开授权。旧v0.1源码ZIP保留；公开发布状态以仓库为准。

## YY 命名复验

按用户要求统一更名为`yy-talking-head-motion`，界面名称为“YY 口播动效包装”，公开仓库归属为`alanliuchl-netizen`。更名后依赖检查、Skill格式校验和13项测试再次通过，并实际复跑18秒`ppt-calm`横版：1920×1080、30fps、540帧，完整解码通过，845个AAC包的内容与时间保持一致。成片SHA256为`2864bd4a51ba4be600b5a145f0d21db8b81c40f67cf353ac5b88ef81973ff736`。上述全矩阵与独立安装结果来自更名前的相同渲染实现，最终发布包以自身的`RELEASE_CONTENTS.json`校验清单为准。
