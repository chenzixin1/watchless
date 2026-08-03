# Watchless Legal and Compliance Notice

> [English](LEGAL.en.md) | [简体中文](LEGAL.md)

Last updated: 2026-07-13

Watchless is designed for private, internal use. This document provides general risk information and project-use boundaries. It is not legal advice and cannot replace professional review for specific content, jurisdictions, or intended uses.

## Principal risks

### 1. Platform terms and account risk

YouTube's Terms of Service restrict downloading, copying, and automated access unless expressly authorized by the service or in writing by YouTube and the relevant rightsholders. They also prohibit bypassing security features that prevent or restrict copying or other use of content. Chrome cookies are only a form of local authentication: they do not create copyright, download, or distribution rights, and do not eliminate the risk of account restrictions.

### 2. Copyright and redistribution risk

Video, audio, subtitles, screenshots, charts, and show packaging may all be protected by copyright. Transcription, translation, screenshot-led notes, HTML, and PDFs can implicate reproduction, adaptation, or distribution rights. Commentary, research, and teaching may qualify for fair use or analogous exceptions in some jurisdictions, but this must be assessed case by case; there is no universally safe number of screenshots, word ratio, or video duration. A public document complete enough to substitute for the source video is usually riskier than private research notes.

### 3. Privacy, personal information, and confidentiality

Audio, images, names, voices, speaker labels, and identity inferences can be personal information. Biometric information is sensitive personal information in some jurisdictions. Private meetings, unpublished interviews, content involving minors, and medical or financial information may face stricter limits. Reprocessing information that is already public does not automatically permit unrestricted identification, aggregation, or public distribution.

### 4. Third-party speech recognition

By default, Volcengine ASR sends audio to a third-party service for processing. Users should confirm that they are permitted to make that transfer and review the applicable product terms, privacy policy, data-retention practices, and regional rules. For confidential material, sensitive personal information, or material without necessary authorization, use explicitly enabled local Whisper or stop processing.

### 5. Speaker misidentification and content accuracy

Automatic transcription, speaker diarization, and identity mapping can all be wrong. Misattribution can create reputational, privacy, or commercial risk. A human must review any external use. When evidence is weak, retain `Speaker N`; never present a guess as fact, and never use the result for hiring, credit, law-enforcement, medical, or other decisions affecting individuals' rights or interests.

## Private-use boundaries

When using Watchless, meet all of the following requirements:

1. Process only content you own, are explicitly authorized to process, that is in the public domain, or that you have independently determined you may lawfully process.
2. Do not use this project to defeat or bypass DRM, paywalls, membership limits, private access, regional restrictions, CAPTCHAs, account restrictions, or other access controls.
3. Chrome cookies may be read transiently by the program only from the local browser profile. Do not export, copy, print, log, upload, or commit them to Git.
4. Obtain necessary authorization for private or confidential recordings and comply with contractual, employment, meeting, and data-protection obligations.
5. Resolve speaker names only from show descriptions, self-introductions, on-screen lower thirds, or other reliable public evidence. Do not perform facial or voice biometric identification.
6. Keep outputs private by default. Any public release, commercial use, or third-party distribution requires a renewed review of source terms, copyright, privacy, confidentiality, and attribution.
7. When public disclosure is necessary, retain only the screenshots and quotations needed for commentary or explanation, identify and link the source, and avoid publishing complete transcripts or screenshot-led reconstructions that substitute for the original work.
8. Delete source videos, cookie-derived state, transcripts, and intermediate files when they are no longer needed, and restrict access to `outputs/`.

## Project responsibility boundary

Watchless is not affiliated with, endorsed by, or sponsored by YouTube, Google, Volcengine, or the authors, channels, or producers of the example videos. Third-party names and images are used only to explain compatibility and a private research workflow; their rights belong to their respective owners.

The software is provided “as is” under the [MIT License](LICENSE), without a warranty of successful downloading, transcription, identity resolution, content accuracy, or lawfulness for any particular purpose. Users are responsible for determining whether their inputs, processing, and output uses are lawful and compliant. Consult a qualified lawyer or compliance professional before commercial publication, batch processing, protected content, material involving minors or sensitive personal information, or cross-border data transfers.

## Official references

- [YouTube Terms of Service](https://www.youtube.com/static?template=terms)
- [U.S. Copyright Office Fair Use Index](https://www.copyright.gov/fair-use/)
- [Personal Information Protection Law of the People's Republic of China](https://www.samr.gov.cn/wljys/gzzd/art/2023/art_3ef1e889c1e644d4b65b5f5c7f432386.html)
- [Volcengine Privacy Policy](https://www.volcengine.com/docs/6256/64902)
