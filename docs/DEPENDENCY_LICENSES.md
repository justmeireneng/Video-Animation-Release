# Dependency and license audit

Last reviewed: 2026-09-16.

This is an engineering audit, not legal advice. A release must re-check every
locked dependency and every binary/model actually included in its installer.
`REVIEW REQUIRED` means the asset must not be bundled in a distributable
installer until its terms and provenance have been recorded for that build.

## Release gates

| Gate | Status | Why |
| --- | --- | --- |
| Paid cloud API required for core workflow | Pass | The project does not call Flow/Veo, OpenAI, ElevenLabs, or a cloud render API. |
| Fully offline narration with the current runtime | Blocked | The current `OmniVoiceProvider` delegates to `edge-tts`, which contacts Microsoft's online speech service. |
| Bundle official OmniVoice weights | Blocked | The upstream model card licenses the pre-trained weights as CC-BY-NC; this is unsuitable for a commercial/distributable model pack without separate permission. |
| Use Remotion without a paid license | Conditional | The Remotion free license covers individuals, non-profits, and for-profit organizations with up to three employees. Larger for-profit organizations need a Company License. |
| Bundle the current FFmpeg binary | Review required | The binary currently comes from Remotion's compositor package. Its exact configure flags, codec patents, and redistribution notices must be audited before shipping it. |

## Direct runtime dependencies

| Name | Version / source | Purpose | License | Commercial use allowed? | Redistribution allowed? | Attribution / notice | Status and notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Python | 3.12.14 local venv | Local orchestrator | PSF License | Yes | Yes | Preserve license notice | Pass. |
| `edge-tts` | 7.2.8 | Current speech transport behind `OmniVoiceProvider` | MIT (upstream project; verify in locked source archive) | Code: yes | Code: yes | Include MIT notice if bundled | **Not offline.** It is retained only as the current development fallback, not evidence of an offline voice engine. |
| OmniVoice source code | `k2-fsa/OmniVoice` | Future local voice provider implementation | Apache-2.0 | Yes | Yes | Apache notice / NOTICE where applicable | Do not install or bundle until a compatible model plan is approved. [Source](https://github.com/k2-fsa/OmniVoice/blob/master/LICENSE) |
| OmniVoice pretrained weights | `k2-fsa/OmniVoice` | Local synthesis model | CC-BY-NC | **No commercial use** | Subject to CC-BY-NC | Attribution + non-commercial conditions | **Blocked for commercial/distributable model pack.** Upstream model card explicitly distinguishes its Apache-2.0 code from CC-BY-NC weights. [Model card](https://huggingface.co/k2-fsa/OmniVoice) |
| Remotion | 4.0.523 | React video composition and local render CLI | Remotion License | Conditional | Conditional | Preserve Remotion license | Conditional: free only for individual, non-profit, or for-profit organization of up to 3 employees. [License](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) |
| React | 19.2.3 | Remotion UI runtime | MIT | Yes | Yes | MIT notice | Audit from the lockfile before packaging. |
| TypeScript | 5.9.3 | Remotion compilation | Apache-2.0 | Yes | Yes | Apache notice | Audit from the lockfile before packaging. |
| FFmpeg | Remotion compositor package / system installation | Probe, mix, normalize, mux | LGPL-2.1-or-later by default; can become GPL depending on build | Conditional | Conditional | Required notices/source offer depend on build | **Review required.** A release may instead require an externally installed FFmpeg until a known LGPL build and compliance package are selected. [FFmpeg legal](https://ffmpeg.org/legal.html) |
| Be Vietnam Pro | bundled `assets/fonts/*.ttf` | Vietnamese and multilingual subtitle glyph coverage | SIL Open Font License 1.1 | Yes | Yes, including bundle | Keep OFL and copyright notice | Pass; `assets/fonts/OFL.txt` is retained with the fonts. |

## Python requirements not yet locked for a distributable build

`requirements.txt` declares `numpy`, `opencv-python`, `soundfile`, `scipy`,
`pydantic`, and `python-dotenv` with version ranges. Their exact resolved
versions and transitive licenses must be captured in a locked build manifest
before a Windows installer is published. These packages are therefore
**REVIEW REQUIRED for installer redistribution**, not rejected from local
development.

## Packaging policy until these gates are cleared

1. Never download, install, start, or bundle VoiceStudio.
2. Never download or bundle official OmniVoice weights automatically.
3. Do not claim the speech engine is offline while it uses `edge-tts`.
4. Do not ship the current Remotion or FFmpeg runtime in a commercial
   installer without confirming the intended organization meets the relevant
   license terms and that the FFmpeg binary has a documented compliant build.
5. User-provided ZIP videos, BGM, SFX, and reference audio stay local and are
   never included in the application package.
