---
name: watchless
description: 将 YouTube 链接或本地的 PPT、科普、访谈、播客、产品演示视频转换成完整的截图型笔记、忠实轻度润色文本、HTML、PDF 或分享 ZIP。
---

# Watchless 中文审阅版

> 本文件是正式入口 `SKILL.md` 的完整中文审阅稿。

把一段视频转换成完整的图文文章。转录稿是事实来源，截图负责保存视觉证据。读者不应再需要观看原视频。

## 硬性要求

- 全程本地运行，不调用 PodSum、网站、MCP、Cloudflare、APIFY、D1 或 R2。
- 原视频不可变，重复运行必须复用已经下载的视频和转录稿。
- 默认使用火山引擎词级 ASR，不得静默替换成 YouTube 自动字幕或本地 Whisper。
- 内容必须按原顺序完整保留。Light-plus 不是摘要：保留推理、例子、数字、限定条件、分歧、问答和重复强调。
- 运行过程中展示全片路由概览、边界证据、候选帧、最终帧和 PDF 页面概览。
- 本 Skill 任何路径都不使用 OpenCV。
- 视觉算法只能按路径使用：`slides` 使用 ffmpeg 关键帧召回和局部 SSIM 精修；`explainer`、`conversation`、`demo` 不使用 SSIM、感知哈希、直方图、人物评分或其他视觉排序算法，由 Codex 直接读取候选图。
- 所有 `conversation` 视频在写笔记前必须识别说话人；证据不足时保留 `说话人N`。
- 运行时能够提供真实 Token 数量时，必须记录到 `work/token-usage.json`。不得猜测缺失用量，也不得静默套用过期价格。
- HTML 图片引用、PDF 页面和 ZIP 内容全部通过验证后，才能宣布完成。

## 私人使用合规闸门

获取远程来源前，必须确认用户拥有该内容、已经得到处理授权，或已经独立确认存在其他合法依据。授权不明确时应停止下载，请用户提供已获授权的本地文件。

- 本仓库及其输出默认保持私人。未经单独完成版权、隐私、保密和署名复核，不得公开发布或分发生成结果。
- Chrome Cookie 只能从用户本机浏览器配置中读取；不得导出、打印、复制、上传、写入日志或提交到 Git。能够读取 Cookie 不代表拥有下载或再利用权。
- 不得使用本 Skill 绕过 DRM、付费墙、会员限制、私人视频权限、地区限制、验证码、账号处罚或其他访问控制。
- 把未公开或敏感音频发送给火山引擎前，必须确认用户有权进行该第三方传输。无法确认时，改用用户显式要求的本地 Whisper，或停止处理。
- 说话人姓名只能依据明确的公开元数据、自我介绍、姓名条或同等可靠证据；不得进行人脸或声纹生物识别。无法确认时保留 `说话人N`，对外使用前必须人工复核。
- 经批准对外使用时，只保留实现说明目的所必要的截图和引文。未经单独法律审查，不得发布足以替代原内容的完整转录或完整图文复刻。

处理第三方、保密、商业或敏感内容前必须阅读 `LEGAL.md`。这些控制只能降低风险，不构成法律意见。

## 路由模型

Codex 必须先直接查看 `verify/mode-overview.jpg` 和转录稿，再选择一个内容主路径并附加视觉策略。不得只根据标题或频道判断。

| 主路径 | 可观察特征 | 切分单位 | 截图方法 |
| --- | --- | --- | --- |
| `slides` | 稳定 PPT、幻灯片、文档页面或固定演示区域 | 每个有意义的页面或构建状态 | H.264 Hybrid 关键帧召回、局部 SSIM 精修、准确扫描回退 |
| `explainer` | 脚本化视觉论证：主持人、图表、动画、地图、文档、B-roll | 完整论点、例子或视觉功能 | 在语义场景内密集分布候选，由 Codex 选图 |
| `conversation` | 访谈、圆桌、播客或问答 | 完整问答或话题单元，不按每次换人切分 | 主讲人/双人/多人镜头；有证据画面时优先证据 |
| `demo` | UI walkthrough、产品演示、教程或实体操作 | 可执行步骤及可观察结果 | 候选偏向操作前后和完成状态，由 Codex 选图 |

视觉策略可以组合：

- `slide-state`：稳定、完整的幻灯片或构建状态。
- `speaker`：当前主讲人或有用的多人镜头。
- `evidence`：承载论点的图表、引文、界面、物体或资料。
- `broll`：编辑型采访或纪录片中的相关外景和资料画面。
- `dense-visual`：为小 Lin 式高密度成片增加候选帧。
- `document-evidence`：优先论文、文章摘录、表格和示意图。
- `screen-state`：优先清晰的界面结果，而不是鼠标移动或转场。

`conversation` 还必须选择一个提取子类型，但不增加新的主路径：

| 子类型 | 适用场景 | 候选帧策略 |
| --- | --- | --- |
| `studio` | 视觉证据很少的棚内或远程播客 | 每个语义场景取 3 个代表性人物/多人候选，减少重复脸部截图 |
| `edited` | 穿插外景、文档、历史资料或 B-roll 的编辑型采访 | 9 个分布候选，再叠加字幕证据触发的局部候选 |
| `news` | 有姓名条、Ticker、数据图和产品图的新闻采访 | 8 个分布候选，再叠加字幕证据触发的局部候选 |
| `chaptered` | 官方章节可作为主题线索的长访谈 | 5 个候选；章节只提示粗边界，不得截断回答 |
| `general` | 证据不足，暂时无法判断更具体子类型 | 保留兼容的 5 候选行为 |

典型样本：

- 小 Lin 式财经科技科普：`explainer + dense-visual + evidence`。
- Best Partners 论文/文章解读：`explainer + document-evidence`。
- a16z、YC Lightcone 棚内播客：`conversation + speaker`。
- 硅谷101编辑型深度采访：`conversation + evidence + broll`。
- YC Design Review 屏幕演示：`demo + screen-state + evidence`。
- 低信息密度娱乐聊天：`conversation + speaker`，按更大的主题单元合并并减少截图。

## 工作流程

把 `SKILL_DIR` 设为本 Skill 目录，并从希望生成 `outputs/video-notes/` 的工作区执行。

### 1. 下载、转录和全片检查

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" "$SOURCE" --stage prepare
```

从输出读取 `PROJECT_DIR`。展示 `verify/mode-overview.jpg`，结合转录稿和来源信息，根据视频真实结构选择路径。

### 2. 确认路径和视觉策略

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage route --project-dir "$PROJECT_DIR" \
  --mode explainer \
  --visual-strategy dense-visual \
  --visual-strategy evidence \
  --mode-reason "脚本化主持人口播与图表、B-roll 交替"
```

后续阶段可以使用 `--mode auto`，它会读取已确认的 `work/route-decision.json`。显式 `--mode` 可以随时覆盖。兼容别名：`presentation -> slides`，`editorial -> explainer`。

Bloomberg 式新闻采访示例：

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage route --project-dir "$PROJECT_DIR" \
  --mode conversation --conversation-profile news \
  --visual-strategy speaker --visual-strategy evidence \
  --mode-reason "新闻采访包含姓名条和少量关键数据图"
```

### 3A. Slides 路径

Slides 不走语义时间线。如果 PPT 只占画面的一部分，直接查看概览图并传入相对裁剪区域：

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage scenes --project-dir "$PROJECT_DIR" --mode auto \
  --slide-rect "0.04,0.08,0.72,0.92"
```

默认 `hybrid-keyframe`：低分辨率扫描 H.264 关键帧，用 SSIM 比较固定 PPT 区域，仅在成簇变化附近按 2 秒网格精修；关键帧召回不可用时回退到 `accurate` 全片扫描。只有默认漏页或过度切分时，才调整 `--slide-backend accurate`、`--slide-interval` 或 `--slide-threshold`。

展示 `verify/selected-keyframes.jpg`，确认截图是完整页面，而不是黑帧、淡入淡出或半完成转场。

### 3B. Explainer、Conversation 和 Demo 路径

先准备音频优先的语义边界材料：

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage timeline --project-dir "$PROJECT_DIR" --mode auto
```

阅读 `work/video-use/takes_packed.md` 和 `work/timeline/boundary-review.md`。只在完整语句和语义转折处提出边界。对每个真实决策点 `T`，使用 `video-use/helpers/timeline_view.py` 查看约 `T-4s` 到 `T+4s`；禁止固定间隔扫描整段视频。

来源存在官方章节时，时间线阶段会生成 `work/timeline/chapter-hints.json`。章节只作为粗略主题建议；必须根据完整问题、回答、例子和限定条件进行合并或拆分。

写入 `work/timeline/scene-boundaries.json`：

```json
{"mode":"explainer","scenes":[{"end_sec":42.35,"reason":"开场和第一个论点完整结束"},{"end_sec":113.8,"reason":"图表解释结束"}]}
```

最后一个边界必须覆盖最后一句转录。然后生成场景：

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage scenes --project-dir "$PROJECT_DIR" --mode auto \
  --boundaries "$PROJECT_DIR/work/timeline/scene-boundaries.json"
```

展示候选接触表和 `verify/selected-keyframes.jpg`。科普优先承载论点的证据画面；对谈默认主讲人，但资料/B-roll 有新增信息时优先资料；演示优先完成后的 UI 或实体结果。

对于 `edited` 和 `news` 对谈，程序还会查找字幕中对图表、数据、报告、论文、产品、芯片和屏幕的明确引用，在附近增加标为 `evidence` 的候选图。这只是提高召回率，不是视觉评分；最终仍由 Codex 直接看图选择。

### 4. 确认最终截图

默认候选合适时：

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage select --project-dir "$PROJECT_DIR"
```

需要调整时写入 `{"1":2,"7":5}` 这样的选择文件并传入 `--selections`。只有 `keyframe_review.status=complete` 后才能继续。

### 5. 对谈说话人识别

`conversation` 必须先完成 `work/speaker-map.json`。证据顺序：

1. YouTube 标题、简介、嘉宾名单、章节和官方链接。
2. 自我介绍和可靠字幕。
3. 下三分之一字幕、画面姓名、镜头交接与说话轮次一致性。
4. 官方节目页面。
5. 同频道历史节目中的固定主持人，只作为佐证。

记录显示名、角色、置信度和证据。`high` 需要明确点名加轮次一致；`medium` 是有官方依据的推断；`low` 必须继续显示 `说话人N`。ASR 合并多人或同一人标签变化时，用带时间范围的 `turn_overrides`。检查全片交接后才能设置 `status=complete`。

### 6. 生成完整场景稿

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage batches --project-dir "$PROJECT_DIR"
```

逐张查看图片和转录稿，严格生成要求的 `work/codex-notes/scene_NNN.md`。保持原始顺序和说话方式，不把对话改写成第三人称文章。画面描述只写有用且可见的事实。

运行时能够报告真实模型用量时，在每个高 Token 阶段后追加记录。只有提供当前明确费率时才计算成本：

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage usage --project-dir "$PROJECT_DIR" \
  --usage-stage notes --model-name "$MODEL" \
  --input-tokens "$INPUT_TOKENS" --output-tokens "$OUTPUT_TOKENS" \
  --cached-input-tokens "$CACHED_INPUT_TOKENS" \
  --input-rate-per-million "$INPUT_RATE" \
  --cached-input-rate-per-million "$CACHED_RATE" \
  --output-rate-per-million "$OUTPUT_RATE"
```

### 7. 构建并验证产物

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/00_build_video_notes.py" \
  --stage finalize --project-dir "$PROJECT_DIR"
```

Finalize 会自动生成 `verify/quality-audit.json` 和 `verify/quality-audit.md`。展示 `verify/pdf-pages-contact-sheet.jpg`，读取审计结果，处理转录覆盖、笔记/截图数量、说话人、字节级重复帧和用量记录警告。最后报告 Markdown、HTML、PDF、ZIP、场景数、图片数、页数、已记录 Token 和已知成本；未知用量必须保持未知。

## 回退策略

通过合规闸门后，YouTube 先匿名运行 `yt-dlp`，再使用本机 Chrome 浏览器 Cookie，但不导出 Cookie，也不得借此规避访问控制。火山凭据可以从环境变量、`scripts/config.py` 或 `WATCHLESS_VOLCENGINE_CONFIG` 发现；不得打印或复制凭据。只有显式 `--use-source-subtitles` 才使用来源/人工字幕；只有显式 `--provider whisper` 才使用本地 Whisper。仍无法下载时，说明错误分类并请求已获授权的本地视频。

所有阶段都可重复执行和断点续跑。`--target-seconds` 只是非 slides 模式的旧兼容回退，绝不是正常切分方法。
