# Naming Options for a Complete Video-Understanding Skill

> [English](naming-options.md) | [简体中文](naming-options.zh-CN.md)

> Final choice: **Watchless** (Skill and GitHub slug: `watchless`)

## Product opportunity

This is neither a meeting-notes tool nor a video summarizer. It is a complete video-understanding pipeline: video acquisition, word-level transcription, route selection, semantic segmentation, keyframe selection, speaker resolution, Light-plus text, visual commentary, HTML, PDF, ZIP, and quality auditing.

Its core value is:

> Turn a video that must normally be watched in time order into a visual document that can be read, searched, and shared completely in image-and-text order.

The name should therefore:

- Avoid `session`: the product is not limited to meetings, courses, or talks.
- Avoid `summary`: the output aims for complete understanding, not a compressed summary.
- Prefer not to use `notes`: it is easily mistaken for short notes or meeting minutes.
- Cover slide decks, explainers, interviews, podcasts, and product demos.
- Work as a Codex Skill name, GitHub repository name, and a possible independent brand.
- Be easy to pronounce and spell in English, with a simple kebab-case slug.

## Candidate names from three perspectives

### Product-manager perspective: state the core value first

| Name | Repository | Product meaning | Strength | Risk |
| --- | --- | --- | --- | --- |
| **VideoCodex** | `video-codex` | Turns video into a complete, structured, readable codex | Echoes both video documentation and the Codex runtime; covers the end-to-end capability | Tied closely to Codex; needs explanation if it later moves beyond Codex |
| **Watchless** | `watchless` | Gain complete understanding without watching the whole video | Direct value proposition with a memorable hook | A negative construction that does not itself describe the visual-document output |
| **VideoAtlas** | `video-atlas` | Organizes a video into a navigable content map | Emphasizes completeness, structure, and browsing | “Atlas” sounds more like an index and understates the writing component |
| **FullScene** | `full-scene` | Retains every complete semantic scene without omission | Emphasizes full coverage and semantic segmentation | Less brandable and easily mistaken for video-editing software |
| **ReadTheVideo** | `read-the-video` | Makes a video readable like an article | Clear user benefit and communicable | Slightly long and conversational for a Skill or command |

### Product-design perspective: emphasize the image-and-text experience

| Name | Repository | Product meaning | Strength | Risk |
| --- | --- | --- | --- | --- |
| **SceneScribe** | `scene-scribe` | Selects an image for each semantic scene and describes it faithfully | Precisely describes scene segmentation plus writing; elegant sound | Weaker expression of acquisition, ASR, and the complete pipeline |
| **FrameAtlas** | `frame-atlas` | Builds a visual atlas of a video from keyframes | Closely matches the “one image, one passage” reading experience | Could be mistaken for frame extraction or image browsing only |
| **StoryLens** | `story-lens` | Re-reads video narrative through a visual lens | Visually evocative and brandable | Less accurate for slides and technical demos |
| **ScenePaper** | `scene-paper` | Lays video scenes out as a readable document | Directly describes the output | Slightly static; lower technical resonance |
| **FrameTrail** | `frame-trail` | Follows the video through a trail of keyframes and text | Fits a timeline-style reading experience | Does not clearly convey transcription or complete semantic understanding |

### Software-engineering perspective: emphasize the pipeline and extensibility

| Name | Repository | Product meaning | Strength | Risk |
| --- | --- | --- | --- | --- |
| **FrameForge** | `frame-forge` | “Forges” raw video into keyframes and knowledge assets | Strong engineering feel; works for an end-to-end pipeline | “Frame” may imply image processing is the whole product |
| **VideoWeave** | `video-weave` | Weaves transcripts, scenes, speakers, and visuals into a document | Accurately captures multimodal composition | A softer name with weaker recall than VideoCodex |
| **SceneGraph** | `scene-graph` | Represents a video through structured scenes | Fits an internal data model and future API | An established computer-vision term with possible ambiguity |
| **VidCompile** | `vid-compile` | “Compiles” video into HTML, PDF, and ZIP | Strong technical signal for input-to-output transformation | Less accessible for non-engineering users |
| **ChronicleKit** | `chronicle-kit` | Organizes a timeline into a lasting, complete record | Works for future expansion into a toolkit | Does not clearly identify video as the input |

## The five highest-priority names

Scoring dimensions: core-value expression 35%, memorability 25%, Skill/GitHub usability 20%, and future extensibility 20%. Scores are relative to the present positioning; they do not verify domain, trademark, or GitHub availability.

| Rank | Name | Overall judgment | Key assumption |
| --- | --- | --- | --- |
| 1 | **VideoCodex** | Best represents a full video compiled into a structured visual codex, and naturally communicates a complete Skill inside Codex | Users understand the Codex wordplay and do not mistake it for an official OpenAI product |
| 2 | **SceneScribe** | Most accurately describes the core interaction: semantic scenes, keyframes, and faithful writing | Users care more about the content experience than the full pipeline |
| 3 | **FrameAtlas** | Strongest visual feeling and closest to the final image-and-text document | The product remains centered on screenshot-led documents rather than moving to audio-only or text-only processing |
| 4 | **Watchless** | Strongest expression of user benefit; good for outreach and a homepage headline | Users accept a slightly provocative “watch less” brand tone |
| 5 | **VideoWeave** | Best explains multimodal fusion of transcript, visuals, speakers, and semantics | Users are willing to learn the product through a subtitle rather than requiring the name to explain itself |

## Final decision

### Watchless

Official product identity:

```text
Display name: Watchless
Skill name: watchless
GitHub repository: watchless
Tagline: Watch less. Understand more.
```

Recommended subtitle:

> Turn any video into a complete visual document, so you can understand it without watching the whole thing.

Recommended one-line description:

> Watchless is a complete video-understanding Skill that runs locally in Codex. Starting with acquisition and word-level transcription, it selects a route from content structure, identifies semantic scenes, keyframes, and speakers, and produces faithful visual explanations, HTML, PDF, and a shareable ZIP.

### Why not Video Notes Maker?

`Video Notes Maker` is clear but lacks a distinctive brand. `Notes` also makes readers expect a short summary. `Watchless` expresses the benefit directly: users do not need to watch the whole video to achieve complete understanding.

1. **Clear outcome:** the name answers why someone would use the Skill.
2. **Memorable:** it feels closer to an independent product brand than a descriptive tool name.
3. **Content-agnostic:** it works for slide decks, explainers, interviews, podcasts, and demos.
4. **Platform-agnostic:** the brand still works if the project expands beyond Codex.

## Assumptions to validate

Before formally renaming or publishing to GitHub, validate:

1. Whether target users understand from `Watchless` and the subtitle that it creates a complete visual document, not a shorter video.
2. Whether the GitHub repository name, Python package name, common domains, and social accounts have obvious conflicts.
3. Whether users accept the slightly challenging “watch less” tone.
4. Whether a Chinese supporting name is useful; the current recommendation is to use the English brand alone to preserve recall.

If users cannot infer the output shape from the subtitle, the preferred fallback is **SceneScribe**, which still accurately describes the core of “semantic scenes plus image-and-text writing.”
