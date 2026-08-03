# Video Content Patterns and Visual-Article Extraction Strategy

> [English](video-pattern-research.md) | [简体中文](video-pattern-research.zh-CN.md)

## Conclusion

Videos should not be classified only by channel-style labels such as “slides, explainer, podcast.” Two orthogonal dimensions actually determine visual-article extraction quality:

1. **Content organization:** page-driven, scripted argument, multi-person conversation, or step-by-step operation.
2. **Visual responsibility:** people, evidence, B-roll, documents, charts, or interface state.

Watchless therefore uses four primary extractors and allows visual strategies to be combined:

| Primary route | Core segmentation unit | Default visual strategy | Uses a visual algorithm? |
| --- | --- | --- | --- |
| `slides` | Slide or build state | `slide-state` | This route alone uses hybrid keyframes plus SSIM |
| `explainer` | Complete argument, example, or visual function | `evidence + dense-visual` | No scoring; Codex reads candidate images directly |
| `conversation` | Complete Q&A or topic unit | `speaker` | No scoring; Codex reads candidate images directly |
| `demo` | Executable step and result | `screen-state + evidence` | No scoring; Codex reads candidate images directly |

## Sample matrix

| Sample | Actual pattern | Recommended route | Why |
| --- | --- | --- | --- |
| a16z, *Software in the Age of Agents* | Three-person studio or remote conversation, long stable shots, occasional cards | `conversation + speaker` | Screenshots do not carry most of the information; Q&A and speaker identity matter most |
| Silicon Valley 101, Nathan Lambert interview | Deep two-person interview intercut with locations, historical clips, source cards, and an office tour | `conversation + evidence + broll` | Dialogue drives the content, but some B-roll is more informative than people shots |
| XiaoLinShuo, *Capital Conflict Between AI Giants* | One-person scripted narrative with frequent charts, cards, news, animation, and source footage | `explainer + dense-visual + evidence` | Arguments and visuals explain together; candidate density must increase and charts take priority |
| Best Partners, *Harness Engineering* | Presenter narration alternating with paper pages, excerpts, flowcharts, and formulas | `explainer + document-evidence` | Documents and charts are the main evidence, but they are not a stable continuous slide deck, so pure slide-change segmentation is wrong |
| YC Design Review | Two-person explanation alternating with continuous screen operation | `demo + screen-state + evidence` | Key screenshots are completed pages, design variants, and tool states, not camera changes |
| YC Lightcone, *FDE Playbook* | Four-person roundtable with long people-only shots | `conversation + speaker` | Use large topic units, speaker resolution, and a small number of representative people frames |
| YC Office Hours | Multi-person roundtable Q&A | `conversation + speaker` | Do not split on camera changes; split on startup questions and complete answers |
| Class-representative interview | Long remote two-person interview with very few title cards | `conversation + speaker` | A 95-minute video needs topic-level grouping, not fixed intervals that create many repeated people frames |
| MKBHD, *Apple Lost the AI Race* | Lightweight two-person chat with occasional product images | Low-weight `conversation + speaker` | High view count but low visual-document substitution value and information density; it should not dominate route design |
| Bloomberg interview with Chey Tae-won | On-location two-person news interview with occasional chip images, lower thirds, and live headlines | `conversation(news) + speaker + evidence` | People remain the backbone, but evenly sampled frames can miss brief data graphics and news cards |
| Silicon Valley Coordinates × Chang Jing | Long two-person interview with official chapters and brief Munger material at the start | `conversation(chaptered) + speaker` | Chapters can suggest topics, but final boundaries must preserve complete Q&A and qualifications |

## Best practices by route

### Slides

- Have Codex confirm the fixed slide region from the whole-video overview; use the full frame when no crop is needed.
- Scan H.264 keyframes at low resolution and use SSIM to identify change candidates.
- When candidates cluster, refine locally at a fixed interval only near the cluster; use an accurate whole-video scan only when keyframes are unavailable.
- Choose the stable frame after each transition and have Codex reject black frames, fades, occlusions, and incomplete animations.
- Align text strictly to slide start and end times; one page corresponds to one complete transcript block.

### Explainer

- Segment the transcript into complete arguments, examples, and visual functions; a camera cut is not itself a boundary.
- Generate evenly distributed candidates within each semantic scene; `dense-visual` and `document-evidence` increase candidate density.
- Prefer charts, final animation states, source excerpts, maps, interfaces, and objects over the presenter's face.
- Preserve the complete narrative order. Screenshots are visual evidence, not a reason to compress the text.

### Conversation

- Use word-level ASR and speaker diarization to retain Q&A, then segment by complete Q&A or topic unit.
- Confirm names with official descriptions, self-introductions, lower thirds, and shot handoffs; retain `Speaker N` for weak evidence.
- First choose a profile—`studio`, `edited`, `news`, `chaptered`, or backward-compatible `general`. It changes candidate density and boundary hints, not the primary route.
- Generate three distributed candidates per semantic scene for `studio`, nine for `edited`, eight for `news`, and five by default for other profiles.
- For `edited` and `news`, add local candidates when subtitles explicitly mention charts, data, reports, papers, products, chips, or screens, and mark them `evidence` on the contact sheet.
- Evidence triggers raise recall only. Do not run SSIM, hashing, histogram, face, or aesthetic scoring; Codex still chooses from images directly.
- Write official chapters to `chapter-hints.json` as rough boundaries only. Merge or split when a chapter cuts through a question, answer, example, or qualification.
- For pure studio conversations, prefer the current speaker or a multi-person shot. For edited interviews, `evidence` and `broll` can override people frames.
- For long, visually sparse videos, enlarge topic units and reduce repeated people frames. Never split images at fixed 60- or 90-second intervals.

## Quality loop

- After Finalize, read `verify/quality-audit.json` to verify ordered full transcript coverage, matching scene/note/keyframe counts, completed conversation-speaker work, and byte-identical duplicate selections.
- `candidate_reasons` records distributed candidates and subtitle-triggered evidence candidates, making it possible to trace why a frame was captured at a particular time.
- Write actual token counts to `work/token-usage.json` when the runtime provides them. Keep the value unknown when it does not; never pass estimates off as measured data.
- Calculate cost only from a current rate explicitly passed at runtime or a clear actual billing amount. Do not hard-code changeable prices in the Skill.

### Demo

- Segment by “goal or precondition → action → observable result,” not by subtitle paragraph or camera change.
- Have candidates cover early, middle, and late states, with a default bias toward the roughly 90%-complete state.
- Retain the necessary buttons, inputs, menus, configuration, error messages, and final pages so readers can reproduce the steps from text alone.
- A UI tutorial may have two presenters, but speaker count does not change its primary route: its organization is still step-driven.

## Constraints informed by external research

- YouTube recommends grouping content by buckets such as format, series, style, and tone, then comparing retention rather than treating one popular video as representative of all content. This project therefore uses MKBHD as a low-weight counterexample rather than a core template. [YouTube: Choosing what content to create](https://support.google.com/youtube/answer/13616340)
- Retention top moments, spikes, and dips show where viewers keep watching, rewatch, or skip. If a channel's own analytics become available, replay peaks can become visual-evidence candidates, but public view counts must not be treated as content density. [YouTube: Key moments for audience retention](https://support.google.com/youtube/answer/9314415)
- Slide-transition detection is a separate problem; research uses dedicated transition candidates and refinement rather than treating a lecture as an ordinary shot-summary video. [SliTraNet](https://arxiv.org/abs/2202.03540)
- Topic boundaries in instructional video depend on text, audio, and visual coherence, supporting semantic segmentation plus targeted visual inspection around decision points instead of fixed windows across the whole video. [Multimodal Fusion and Coherence Modeling for Video Topic Segmentation](https://aclanthology.org/2025.findings-acl.904/)
- UI-tutorial summaries need executable steps and associated keyframes. Ordinary semantic summaries cannot reliably cover operational detail, so `demo` must remain separate from `explainer`. [MS4UI](https://arxiv.org/abs/2506.12623)
- A practical multimodal video-summary objective generates both keyframes and associated text, rather than writing a text-only summary and attaching arbitrary images afterward. [Keyframe-Caption Pairs](https://arxiv.org/abs/2312.01575)

## Classifying future samples

For every new sample, record six properties rather than adding a new route immediately:

1. Whether the main content progresses through pages, a script, conversation, or steps.
2. How many real speakers exist and whether identity mapping is needed.
3. Whether visuals mainly carry people, evidence, B-roll, documents, charts, or interface state.
4. Whether visual changes correspond to content changes or merely editing and camera-angle changes.
5. The smallest independently readable unit.
6. What one representative image should show first.

Add a primary route only when a new sample cannot be expressed by the four routes plus visual strategies and requires a different segmentation unit.
