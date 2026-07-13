# 视频内容 Pattern 与图文提取策略研究

## 结论

视频不应只按“PPT、科普、播客”三个频道式标签分类。真正影响图文提取效果的是两个正交维度：

1. **内容组织**：页面驱动、脚本化论证、多人对话、步骤化操作。
2. **视觉职责**：人物、论据、B-roll、文档、图表、界面状态。

因此采用四个主提取器，并允许叠加视觉策略：

| 主模式 | 核心切分单位 | 默认视觉策略 | 是否使用视觉算法 |
| --- | --- | --- | --- |
| `slides` | 幻灯片或构建状态 | `slide-state` | 仅此模式使用 Hybrid 关键帧 + SSIM |
| `explainer` | 完整论点、例子、视觉功能 | `evidence + dense-visual` | 不评分，Codex 直接看候选图 |
| `conversation` | 完整问答或话题单元 | `speaker` | 不评分，Codex 直接看候选图 |
| `demo` | 可执行步骤及结果 | `screen-state + evidence` | 不评分，Codex 直接看候选图 |

## 样本矩阵

| 样本 | 实际 Pattern | 推荐路由 | 关键原因 |
| --- | --- | --- | --- |
| a16z《Software in the Age of Agents》 | 三人棚内/远程对谈，画面长期稳定，少量图卡 | `conversation + speaker` | 截图不负责传递主要信息，问答和说话人身份最重要 |
| 硅谷101 Nathan Lambert 专访 | 双人深度采访，穿插外景、历史片段、资料卡，结尾 office tour | `conversation + evidence + broll` | 内容仍由对话推进，但部分 B-roll 比人物镜头更有信息 |
| 小Lin说《AI巨头们之间的资本混战》 | 单人脚本化叙事，高频图表、卡片、新闻、动画和资料镜头 | `explainer + dense-visual + evidence` | 论点和画面共同完成解释，必须增加候选密度并优先图表 |
| Best Partners《Harness 工程》 | 主讲人口播与论文、原文摘录、流程图、公式交替 | `explainer + document-evidence` | 文档和图表是主要论据，但不是稳定连续 PPT，不能用纯 slide-change 切分 |
| YC Design Review | 双人讲解与持续屏幕操作交替 | `demo + screen-state + evidence` | 关键截图是完成后的页面、设计变体和工具状态，而不是镜头切换 |
| YC Lightcone《FDE Playbook》 | 四人圆桌，长期纯人物镜头 | `conversation + speaker` | 适合大主题单元、说话人识别和少量代表人物图 |
| YC Office Hours | 多人圆桌问答 | `conversation + speaker` | 不应因摄像机切换而切段，应按创业问题和完整回答切分 |
| 课代表立正屠龙访谈 | 双人远程长访谈，极少数图卡 | `conversation + speaker` | 95 分钟内容必须按主题合并，避免按固定时间生成大量重复脸部截图 |
| MKBHD《Apple Lost the AI Race》 | 双人轻量聊天，少量产品画面 | 低权重 `conversation + speaker` | 播放量高但图文替代价值和信息密度低，不应主导模式设计 |
| Bloomberg 崔泰源专访 | 现场双人新闻采访，少量芯片图、姓名条和实时标题 | `conversation(news) + speaker + evidence` | 人物仍是主线，但短暂数据图和新闻图卡不能被均匀抽帧漏掉 |
| 硅谷坐标 × 常劲 | 有官方章节的双人长访谈，开场少量芒格资料 | `conversation(chaptered) + speaker` | 章节可提示主题，但最终边界必须保留完整问答和限定条件 |

## 各模式最佳实践

### Slides

- 先由 Codex 从全片概览确认固定 PPT 区域；没有裁剪区域时使用全画面。
- 低分辨率扫描 H.264 关键帧，使用 SSIM 找出变化候选。
- 多个候选聚集时，只在附近做固定间隔局部精修；关键帧不可用时才准确扫描全片。
- 每个状态选择切换完成后的稳定帧，并由 Codex 排除黑帧、淡入淡出、遮挡和半完成动画。
- 文字严格按幻灯片起止时间对齐，一页对应一个完整讲稿块。

### Explainer

- 先按转录稿切成完整论点、例子和视觉功能，镜头切换本身不是边界。
- 在每个语义场景内部均匀生成候选；`dense-visual` 或 `document-evidence` 增加候选密度。
- 图表、动画最终状态、原文摘录、地图、界面和实物优先于主持人脸部。
- 必须保留完整叙述顺序；截图是视觉证据，不是压缩文字内容的理由。

### Conversation

- 先用词级 ASR 和说话人识别保留问答，再按完整 Q&A 或话题单元切分。
- 通过官方简介、自我介绍、下三分之一字幕和镜头交接确认姓名；弱证据保留 `说话人N`。
- 先选子类型：`studio`、`edited`、`news`、`chaptered` 或兼容的 `general`。它只调节候选密度和边界提示，不增加主模式。
- `studio` 每个语义场景只生成 3 个分布候选；`edited` 生成 9 个；`news` 生成 8 个；其余默认 5 个。
- `edited/news` 在字幕明确提到图表、数据、报告、论文、产品、芯片或屏幕时，在对应时间附近增加局部候选，并在接触表标记 `evidence`。
- 证据触发只负责提高召回率，不进行 SSIM、哈希、直方图、人脸或美学评分，最终仍由 Codex 直接看图。
- 官方章节写入 `chapter-hints.json`，只作为粗边界；章节截断问题、回答、例子或限定条件时必须合并或拆分。
- 纯棚内对谈优先当前说话人或多人镜头；编辑型采访允许 `evidence` 和 `broll` 覆盖人物图。
- 对长篇低视觉密度视频扩大主题单元，减少重复人物截图，绝不按固定 60/90 秒切图。

## 质量闭环

- Finalize 后必须读取 `verify/quality-audit.json`，检查转录是否按顺序完整覆盖、场景/笔记/截图数量是否一致、对谈说话人是否完成、是否存在字节级重复选图。
- `candidate_reasons` 记录分布候选与字幕证据触发候选，便于追溯为什么在某个时间点截图。
- 模型运行时提供真实 Token 数量时写入 `work/token-usage.json`；运行时没有数据就保持未知，禁止估算冒充实测。
- 成本只能使用调用时显式传入的当前费率或明确的实际账单金额，不在 Skill 中硬编码会变化的价格。

### Demo

- 按“目标/前置状态 -> 操作 -> 可观察结果”切分，而不是按字幕段落或镜头切换。
- 每段候选覆盖早期、中间和后期，并默认偏向 90% 左右的完成状态。
- 保留必要的按钮、输入、菜单、配置、错误提示和最终页面，使文字可以独立复现步骤。
- UI 教程可能同时有两位讲解者，但说话人数不改变其主模式；内容组织仍是步骤驱动。

## 网上资料带来的约束

- YouTube 官方建议按 format、series、style、tone 等 bucket 分组，并结合 retention 比较，而不是用一个热门视频代表全部内容。因此本项目把 MKBHD 作为低权重反例，而不是核心模板。[YouTube：选择内容的建议](https://support.google.com/youtube/answer/13616340)
- YouTube retention 中的 top moments、spikes 和 dips 能说明哪些片段被持续观看、重看或跳过。若未来可以获得频道自己的 Analytics，可把重看高峰作为视觉证据候选，但不能把公开播放量直接当作内容密度。[YouTube：关键留存时刻](https://support.google.com/youtube/answer/9314415)
- 幻灯片切换检测本身是独立问题，研究工作也使用专门的 transition candidate 与 refinement，而不是把讲座视频当成普通镜头摘要。[SliTraNet](https://arxiv.org/abs/2202.03540)
- 教学视频的主题边界同时依赖文本、音频和视觉一致性，支持当前的“语义切分 + 决策点局部看图”，而不是全片固定时间窗口。[Multimodal Fusion and Coherence Modeling for Video Topic Segmentation](https://aclanthology.org/2025.findings-acl.904/)
- UI 教学摘要需要可执行步骤和对应关键帧，普通语义摘要无法稳定覆盖操作细节，因此 `demo` 必须独立于 `explainer`。[MS4UI](https://arxiv.org/abs/2506.12623)
- 实用的多模态视频摘要目标是同时生成关键帧与对应文本，而不是先做纯文字总结再随意配图。[Keyframe-Caption Pairs](https://arxiv.org/abs/2312.01575)

## 后续样本如何归类

新增样本只记录六项，不直接新增模式：

1. 主要内容由页面、脚本、对话还是步骤推进。
2. 有几位真实说话人，是否需要身份映射。
3. 画面主要承担人物呈现、论据、B-roll、文档、图表还是界面状态。
4. 视觉变化是否对应内容变化，还是只是剪辑和机位变化。
5. 最小可独立阅读单元是什么。
6. 一张代表图应优先呈现什么。

只有当新样本无法由四个主模式加视觉策略表达，并且需要不同的“切分单位”时，才新增主模式。
