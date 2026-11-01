# VoiceStudio Pocket — New Mobile Project Charter

**Planning status:** proposed separate iOS product track; **not** a current executable iOS app, installed service, or owner runtime-mode change. 2026-11-01.

**Parent project:** [VoiceStudio](https://github.com/jweter/VoiceStudio)  
**Product form:** Offline recording + audio creation, progressing toward on-device speech models  
**Project ID:** `voicestudio_pocket`

## Vision and product promise

Deliver a genuinely usable pocket voice studio with private, local-first recording, editing, transcription and voice playback, then add higher-value on-device generation/voice conversion only when independent model feasibility, permissions, licenses and real-device performance prove it works. Remote desktop inference is an optional enhancement, never an MVP dependency.

## Current verified foundation

The parent provides a Python speech backend, Electron UI, model catalog and local API; `docs/sharing.md` explicitly describes LAN PIN/QR sharing and Tailscale. Its existing voice-cloning/dubbing pipelines are not automatically portable into an iOS process, and current model availability/performance on iPhone remains unverified.

## First real user journey

With airplane mode enabled, record a voice clip, trim and normalize it, play it, run offline speech-to-text if the current device/language supports it, correct the transcript, synthesize a spoken preview using an installed system voice, and export the audio/transcript to Files. Later, test opt-in on-device custom voice generation without a remote service.

## Non-negotiable standalone contract

- On-device microphone recording, project library, edit/trim/normalize, playback, markers, audio format export and local queue.
- Offline transcription only for device/locale combinations where Apple recognizer explicitly confirms on-device support, or after benchmarking a bundled permissively licensed model.
- Offline system speech synthesis via iOS voices; clearly distinguish it from actual voice cloning or the desktop OmniVoice model.
- No login, Tailscale, server or network required for core workflow; local project exports and deletion remain under user control.

## Optional connected expansion (not a dependency)

Secure pairing with existing VoiceStudio backend for heavyweight voice cloning, synthesis, dubbing and batch operations when desired. Keep jobs explicitly tagged 'On iPhone' versus 'On desktop'; no automatic upload. Use private HTTPS/Tailscale where supported, never assume encrypted tunnel http:// automatically grants browser secure-context APIs.

## Out of scope and honest feasibility boundary

Voice cloning with the same capabilities as full desktop VoiceStudio cannot be promised for every iPhone. Release useful standalone recording/transcription/audio work first; optional on-device advanced inference follows proof.

## Portfolio operating principles

- Phone-first: app launches and performs its declared MVP value in airplane mode without Azathoth, GitHub, a hosted API, or a paid service.
- Native-first for the long run; a PWA or companion prototype may validate UX sooner, but may not be represented as proof of fully native offline functionality.
- One source of product truth: share formats, algorithms and fixtures with parent project; never fork the entire Python/Windows backend or invent duplicate business rules.
- Optional sync must be explicit, authenticated, revocable and resilient to disconnection; an offline session must never trigger an implicit network request.
- Protect user data: use iOS sandbox, Files integration, file protection/Keychain for secrets; avoid collecting unnecessary user content and telemetry.
- Keep parent project quality policies: narrow branches, exact-head tests, licensing/provenance checks, review and product reality. Do not install or alter the running Iron God release.
- Measure device performance, memory, thermals and battery on physical supported iPhones; record actual evidence before making capability or compatibility claims.
- Maintain accessibility (VoiceOver, Dynamic Type where applicable, contrast, touch targets), cancel/resume behavior and storage bounds.
- No Apple membership purchase, Mac rental, new paid service, signing certificate or public App Store distribution without separate explicit owner decision.

## Build environment and cost constraints

Native iOS signing, on-device testing and App Store submission normally require macOS/Xcode infrastructure; the Windows laptop can remain the source-development and test workstation. Start with portable C++/Swift contract fixtures and SwiftUI design prototypes where a Mac runner/device is not yet available. Personal device development can start without paid Apple Developer Program membership, subject to Apple's provisioning limits; App Store/TestFlight distribution requires program enrollment.

Default cost target $0 before owner-approved developer membership, build-machine access or cloud usage. Keep optional model downloads, paid APIs, hosted inference and other recurring costs opt-in. No automatic spending.

## Parent-code and platform references

- https://github.com/jweter/VoiceStudio/blob/main/docs/sharing.md
- https://github.com/jweter/VoiceStudio/blob/main/README.md
- https://developer.apple.com/documentation/speech/sfspeechrecognizer/supportsondevicerecognition


---

# VoiceStudio Pocket — Phased iPhone Roadmap

**Status:** PLANNED. Phases are evidence gates, **not calendar commitments**. Parent projects retain authority over their existing implementation and product quality.

## Release strategy

Start by proving a no-server/no-laptop local user journey. Give native/local capabilities their own implementation and acceptance tests. Add external integrations only after the standalone core works. For every phase: maintain a narrow branch, exact-head tests, real device evidence and explicit limitations; do not call draft prototypes complete.

## P0 — Portable feature/model feasibility

**Deliverables**

- Map desktop pipelines, model sizes, CPU/GPU, license and memory usage; choose one short, representative offline speech workload.
- Confirm iOS speech-recognition locale support and AVAudio recording/playback permission behavior on physical device.
- Make an on-device voice cloning feasibility matrix: supported hardware, inference/runtime, quality, size, temperature, model distribution and consent.

**Exit gate:** Document viable free offline primitives; do not promise cloning until one real device runs a representative licensed model and produces quality evidence.

## P1 — Standalone pocket recorder

**Deliverables**

- Create SwiftUI library, recording, trimming, markers, loudness view, playback and offline export.
- Use local files and versioned project metadata, resumable editing and deterministic sample fixtures.
- Add permission-denial, interruptions, route-switch/headphone tests and VoiceOver/Dynamic Type.

**Exit gate:** Airplane-mode end-to-end recording, editing, saving and exporting survives app restart with desktop powered off.

## P2 — Local transcription and voice tools

**Deliverables**

- Add actual on-device STT with device/locale capability detection and transcript correction, never silent cloud fallback.
- Add offline system-voice TTS and segment export; integrate the app with Files/Share sheet.
- Benchmark long clips, streaming memory and background audio/export behavior using iOS-supported modes.

**Exit gate:** On-device supported-locale transcript and local voice preview demonstrated; unsupported locales show explicit explanation and do not use network.

## P3 — Experimental fully local custom speech

**Deliverables**

- Port or convert one compatible, licensed generation/cloning model for a bounded audio case.
- Benchmark latency, storage, memory, thermal throttling, voice quality, speaker consent and runtime fallback; record product-reality listening evidence.
- Only expose the feature as production-ready if all quality/security/hardware gates pass; otherwise keep it experimental and retain offline v1 value.

**Exit gate:** One actual on-device generated custom-voice clip with measured quality/performance and consent; no desktop inference falsely labeled local.

## P4 — Optional remote advanced processing

**Deliverables**

- Implement a private desktop pairing adapter with explicit upload decisions and revoke/disconnect.
- Support queued voice cloning, longform/dubbing and desktop output retrieval while providing local progress/history.
- Test offline reconnect and cancellation with no duplicate jobs or unexpected data export.

**Exit gate:** Desktop-off case remains fully usable for local tools; remote jobs clearly indicate their external dependency.

## P5 — iPhone beta

**Deliverables**

- Review speech-data rights, consent, model licenses, retention, background-audio policies and privacy manifests.
- Test representative phones/headsets, languages, accessibility and cold-start/device heat.
- Distribute beta only after Apple build/signing and owner-approved costs.

**Exit gate:** Offline recorder/STT/TTS functions pass native iPhone acceptance and no unapproved network contact.

## First independently actionable engineering slices

1. VSP-001: catalog current backend models and actual iPhone portability with license/provenance
2. VSP-002: native offline microphone/AVAudioEngine device spike
3. VSP-003: file-backed recording editor + export regression suite
4. VSP-004: availability-gated offline STT and local TTS experiment
5. VSP-005: candidate custom-voice on-device benchmark before implementation commitment

## External blockers / decisions held for later

Voice cloning with the same capabilities as full desktop VoiceStudio cannot be promised for every iPhone. Release useful standalone recording/transcription/audio work first; optional on-device advanced inference follows proof.

Open decisions to defer: name/icon/branding; minimum iOS version and target devices after a build smoke; distribution model and monetization; Apple signing infrastructure; optional online sync; optional on-device inference models. None block offline planning and portable-contract work.

## Change-control and roadmap hygiene

This iOS roadmap is a distinct **proposal** and does not silently expand the owner-approved desktop implementation roadmap. On approval of a phase, add narrowly bounded capability graph entries or planning issues in the appropriate development project; do not auto-enroll these proposals in the active Iron God production dispatcher, grant runtime execution rights, or compete with its owner/session control. Cross-repo dependencies must reference the specific parent schema/commit and explicit acceptance evidence. Record verified milestone outcomes, not guesses.


---

# VoiceStudio Pocket — Architecture, Risks and Validation

## System components and reuse seams

- `PocketAudio` in SwiftUI/AVAudioEngine/AVFoundation with device-local project storage, waveform editing and export.
- `SpeechAdapter` chooses availability-checked on-device speech recognition, with hard fail-closed offline behavior; `NativeSpeechPreview` uses system TTS.
- `ModelRuntime` research adapter behind feature flags: Core ML/Core AI or another vetted locally packaged engine, quantization, memory and thermal watchdog; convert/re-implement only warranted primitives.
- `DesktopBridge` optional, versioned contract consuming existing VoiceStudio API and preserving explicit consent, progress and output provenance.

## Offline / optional-online data flow

**Offline:** Files / mic / touch input → local validated parser → versioned local store → deterministic logic and (if proven) on-device inference → local UI / Files export. No remote call is necessary for the core workflow.

**Online enhancement:** explicit user action → permission/identity check → versioned optional adapter → external backend or online public source → source/receipt validation → local persisted result. Network failure leaves the offline product functional; remote-only operations fail visibly and never impersonate local results.

## Technical and delivery risks

- **Model size and battery:** Desktop voice models may not fit or run acceptably on iPhone; gate true offline cloning behind measured device proof.
- **Speech availability:** On-device speech recognition support depends on locale/device: check before claiming offline.
- **Voice and copyright safety:** Require user rights/consent for supplied voices and source media; do not bundle copyrighted voices or content.
- **Network sharing:** Existing backend is local-only by default and optional network sharing must not become a required app dependency.

## Cross-cutting real-device acceptance matrix

1. Fresh install + airplane mode + Azathoth completely off: app launches and completes the documented core user journey without stalls or hidden remote services.
2. Cold start, memory peak, battery/thermal behavior, model/download size and task latency measured on an actual physical device. Set release budgets from the first spike rather than inventing benchmark successes.
3. No unauthenticated inbound listening port, leaked token, bundled source secret, plaintext private sync credential or surprise upload; perform negative network test.
4. App returns a visible failure state when inputs, permissions, local model assets or Files permissions are missing. No fabricated output or false completion.
5. User can export, back up and delete locally created work without a server; app survives force quit and offline relaunch without losing completed edits.
6. Cross-platform contract/fixture tests verify imported/exported formats against the parent repository; snapshots are not treated as live or authoritative.
7. Standard automated checks, independent review, privacy/permissions declarations, App Store licensing/provenance review and actual iPhone product test must pass before external beta.

## Release evidence template

- Exact source head and build identity; Xcode/SDK/device/OS and model/runtime version if used.
- Recorded airplane-mode test with desktop/server powered off, input fixtures, expected outputs, pass/fail and timings.
- Memory/CPU/battery/thermal/storage measurements; accessible UI screen review; interruption/resume evidence.
- Data privacy/security review, license inventory, signed-build provenance, reviewer approval and open blocker list.
- Explicit distinction: proposed concept vs prototype vs device-proven vs App Store distributable.

## References

- https://github.com/jweter/VoiceStudio/blob/main/docs/sharing.md
- https://github.com/jweter/VoiceStudio/blob/main/README.md
- https://developer.apple.com/documentation/speech/sfspeechrecognizer/supportsondevicerecognition
