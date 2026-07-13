#!/usr/bin/env python3
"""
Unified Configuration for Meetup Transcript Processing Tools

This module provides configuration for all transcript processing tools:
- DocxOptimizer
- Markdown Processor
- Video Transcription

It can be used directly with global variables or as a Config class instance.
"""


# Default configuration values
# [api]
API_KEY = "YOUR_OPENROUTER_API_KEY"  # OpenRoute API key
BASE_URL = "https://openrouter.ai/api/v1"  # API base URL
MODEL = "google/gemini-2.5-flash"  # Model to use
SITE_URL = ""  # Your site URL (optional, for OpenRouter rankings)
SITE_NAME = ""  # Your site name (optional, for OpenRouter rankings)

# [logging]
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"
LOG_FILE = "logs/04_polish_slide_transcript.log"

# [inputs]
INPUT_PROJECTS_DIR = "data/inputs"

# [output]
DEFAULT_TRANSCRIPT_DIR = "data/inputs/samples"
DEFAULT_AUDIO_FORMAT = "mp3"

# [file patterns]
TEMP_AUDIO_SUFFIX = "_temp"
TRANSCRIPT_SUFFIX = "_transcript.txt"

# [whisper]
# Explicit fallback only: pass --provider whisper.
WHISPER_MODEL = "small"
WHISPER_LANGUAGE = "zh"

# [prompt - DocxOptimizer]
# Prompt for optimizing meetup transcript text
OPTIMIZATION_PROMPT = """请作为 SRE 专家，对以下 meetup 录音稿进行整理。请务必：
1. 将口语化录音稿表达整理成逻辑清晰、可读性强的文章
2. 修正所有语法和拼写错误
3. 保留原意与技术准确性
4. 保持原有的结构和组织形式
5. 保留所有技术术语与专有名词
6. 广泛使用bullet points呈现信息
7. 删除所有发言者标记
8. 语言比较客观平实，不要使用夸张的修辞手法，因为这都是对外分享，要客观公正。


全文使用中文

待优化内容：
{text}

Please provide only the optimized version without any explanations or comments.
"""

# [prompt - Markdown Processor]
# Prompt for describing a slide
DESCRIBE_SLIDE_PROMPT = """请扮演 SRE 专家，请详细描述这张幻灯片的内容。
请包括：
1. 幻灯片的标题和主题
2. 幻灯片中的关键点和要点
3. 任何图表、图形或表格的内容
4. 幻灯片的整体结构和布局
5. 不要描述的字体，字号等信息

请提供详细且准确的描述，不要添加幻灯片中没有的信息。
"""

# Prompt for integrating slide description with transcript
TRANSCRIPT_INTEGRATION_PROMPT = """请扮演 SRE 专家，整合 *优化幻灯片* 描述，对以下 *演讲文本* 进行整理，作为这页幻灯片的解说。要求：
* 保持技术准确性和专业性
* 将口语化录音稿表达整理成逻辑清晰、可读性强的文章, 要求语言精炼，但在适当的地方使用接地气、富有情感等等语气
* 使用长句表达复杂概念，提高可读性，如果原文没有使用到成语，不要增加成语
* 保留所有重要的技术细节和专业术语
* 保持原文的核心信息和结构
* 广泛使用bullet points呈现信息， 但不要所有地方都用 bullet points
* 删除所有发言者标记
* 不要生成这种文本：好的，以下是根据您的要求，对幻灯片描述和演讲文本进行整理后生成的解说文本
* 不要过度扩展，输出的文本长度不要超过 **演讲文本** 长度的1.8倍

----------
参照示例风格1：

一、流程层：抓"两头"保障可靠性
- 研发入口：
  - 技术方案评审、稳定性准入机制、架构韧性评估，从一开始就嵌入质量保障；
- 运维尾端：
  - 上线前进行风险演练与准入审核
  - 上线中实时监控、限流降级与故障转移
  - 上线后快速响应、根因定位与复盘改进

二、工具层：让流程"跑到平台上"
- 可观测性标准化：统一指标、日志与 Trace 采集格式，打通全链路视图；
- 自动化应急响应：基于规则引擎自动触发告警、自愈脚本，并将执行结果反馈回规则中心；
- 变更安全防控：灰度发布、限流熔断与一键回滚，减少人工操作盲区；
- 核心目标：以一条可复用的工具链承载流程，提升协作效率，杜绝人为失误。

三、组织层：超预案场景的"兜底"
- AI 知识库联动：故障经验、SOP、监控规则等在知识库中沉淀，供应急时快速检索；
- 作战室机制：事故或演练触发后，跨团队迅速集结，统一指挥、协同处置；
- 使命：在流程与工具之外，用人力与组织协同保障未知场景的快速决策与落地。
正是在这样的双重困境下，团队构建了"前置防护–平台化工具–分级组织"三层运维体系，下一步我们将详细介绍这些策略如何帮助米家在亿级设备与千万用户规模下，实现从预防到响应、从发布到复盘的全链路高可用保障。
-----------------

----------
参照示例风格2：

核心目标：构建抗故障的能力，保障业务的连续性
容灾层面（Disaster Recovery）
  - 多活部署：验证数据层、应用层和业务层是否在异地多活机房中并行运行；
  - 数据一致性：检查跨机房的数据备份与回滚机制，确保出现故障后可快速回溯到安全状态；
故障恢复能力（Failure Recovery）
  - 自主健康检查：每条业务链路都要具备实时自检能力，能及时发现异常；
  - 自动故障转移：在发现服务不可用时，能够无缝切换到备用实例或机房；
  - 限流降级：遇到大规模故障或流量洪峰，立即触发限流与降级策略，优先保留核心功能；
韧性验证（Resilience Verification）
  - 故障注入与混沌演练：通过自动化脚本或混沌工程，定期模拟网络抖动、节点宕机等场景；
  - 红蓝对抗与安全攻防：邀请专业团队渗透测试，识别潜在漏洞与配置缺陷；

-----------------

幻灯片描述：
-------------
{slide_description}
-------------

演讲文本：
-------------
{transcript_text}
-------------

请提供整合后的最终解说文本，不要添加任何额外的解释或评论。
"""

# Prompt for describing a slide in light-plus mode
LIGHT_DESCRIBE_SLIDE_PROMPT = """请扮演 SRE 专家，阅读这张幻灯片，并提取“用于校对口述稿”的关键信息。

请重点输出以下内容：
1. 这一页的标题或主题
2. 图中出现的关键术语、专有名词、产品名、系统名、英文缩写
3. 图表或流程图真正表达的结论、步骤关系或数据关系
4. 容易被 ASR/转写稿写错的词、数字、英文单词、组件名

请注意：
- 这不是为了生成一段完整解说，而是为了给口述稿纠错和补充上下文
- 不要大段描述版式、配色、左右布局、字体字号等视觉细节
- 不要添加幻灯片中没有的信息
- 尽量使用简洁、结构化的要点输出，方便后续对照口述稿
"""

# Prompt for integrating slide context with transcript in light-plus mode
LIGHT_TRANSCRIPT_INTEGRATION_PROMPT = """请扮演 SRE 专家，对以下“口述稿正文”进行轻度整理。另附“图片辅助信息”仅用于帮助你理解上下文、校正错误和补足必要指代。

你的核心目标不是重写一篇新文章，而是基于口述稿做“轻编辑”：
- 以口述稿正文为主体
- 图片辅助信息只用于校对，不是正文素材库
- 优先修正：术语错误、ASR 识别错误、数字/英文拼写错误、指代不清、句子断裂、顺序轻微错乱
- 如果图片能帮助确认概念或步骤关系，只允许做最小必要补充

请严格遵守：
1. 不要把图片中出现但讲者没有真正讲到的大段内容写入正文
2. 新增内容应尽量少，原则上不要超过口述稿长度的 10%-15%
3. 尽量保留讲者原本的表达顺序和核心意思，不要重写成全新的文章
4. 允许把明显的口语病、重复词、发言者标记清理掉，但不要把整段改写得过于书面
5. 只有在原文本身明显是步骤、列表、并列信息时，才使用 bullet points；否则优先保留自然段
6. 保留所有重要的技术细节和专业术语
7. 不要输出“以下是整理后的内容”等说明性前言

图片辅助信息（仅用于校对，不是正文素材）：
-------------
{slide_description}
-------------

口述稿正文：
-------------
{transcript_text}
-------------

请直接输出整理后的口述稿，不要添加任何额外解释或评论。
"""

# [prompt - Polisher]
POLISH_MAX_TOKENS = 32768

POLISH_PROMPT = """你是一位技术文档编辑。下面是一篇由逐页幻灯片独立生成的演讲整理稿，因为每页独立处理，存在以下问题：
1. 几乎每个章节都有重复的开场白（"各位SRE专家们，大家好"、"尊敬的听众们"、"好的，作为SRE专家"等）
2. 大量关于幻灯片视觉布局的描述（"幻灯片采用橙色柱状图图标"、"左侧…右侧…对称布局"等）
3. 对幻灯片本身的元描述（"本页幻灯片旨在…"、"这张幻灯片的核心是…"）
4. 相同的流程/列表被重复多次（例如"创建预估版本→…→限流和资源回调"这10步流程出现了5次以上）
5. 各章节之间缺乏上下文衔接，读起来像独立的片段而非连贯的文章

请对整篇文档进行重写，要求：

**必须做的：**
- 去掉所有重复的开场白和客套话
- 去掉所有关于幻灯片视觉布局、配色、图标样式的描述
- 去掉"本页幻灯片旨在…"之类的元描述
- 重复出现的流程/列表只在第一次出现时详细展开，后续简要引用即可
- 在章节之间加入自然的过渡衔接，让全文读起来是一篇连贯的技术文章
- 保持精炼，总长度控制在原文的 60%-70%

**必须保留的：**
- 所有图片引用，格式为 ![...](...)，原样保留，不要修改
- 所有 --- 分隔符，原样保留
- 所有 ## 和 ### 标题层级结构
- 所有技术细节、数据点、具体示例、专业术语
- bullet points 格式

**不要做的：**
- 不要添加原文没有的信息
- 不要输出"以下是重写后的文档"之类的前言，直接输出重写后的内容

原文如下：
----------
{content}
----------
"""

# [prompt - Transcription]
TRANSCRIPTION_SYSTEM_PROMPT = """You are a helpful assistant that transcribes audio accurately. Maintain original formatting, punctuation, and paragraph breaks where possible."""

TRANSCRIPTION_USER_PROMPT = """Please transcribe the attached audio file accurately. Include speaker identification if multiple speakers are present."""



# Volcano Engine API Configuration

# API key（推荐；也可通过环境变量或 WATCHLESS_VOLCENGINE_CONFIG 指向本地配置）
VOLCENGINE_API_KEY = "YOUR_VOLCENGINE_API_KEY"
# 旧版控制台如需双字段鉴权，再填写 APP_KEY，并把 Access Token 填到 ACCESS_KEY。
APP_KEY = ""
ACCESS_KEY = ""

# ASR Flash：本地音频 Base64 直传，一次请求直接返回识别结果
RECOGNIZE_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
RESOURCE_ID = "volc.bigasr.auc_turbo"

# Default settings
DEFAULT_LANGUAGE = "zh-CN"

# Supported file formats
SUPPORTED_AUDIO_FORMATS = ['.mp3', '.wav', '.ogg']
SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv']
