# VoiceStudio Pocket — Offline-First iPhone Project Charter and Roadmap

**Status: EXPLORATORY MOBILE PROJECT / PLANNING ONLY (2026-11-01).** The owner wants to explore genuine standalone iPhone products. This document establishes a distinct VoiceStudio Pocket project, but does not replace the desktop roadmap, authorize an Iron God runtime execution session, change running services, spend money, or grant permission to publish an app.

## Product vision

A genuinely useful iPhone voice-creation workbench without Azathoth, a server, cloud inference or a mandatory account. Record, audition, trim, organize and export audio entirely on-device. The current desktop VoiceStudio's voice cloning, synthesis, dubbing and model catalog are **optional capabilities to investigate**, not a promise that large speech models already fit the phone.

**Primary user journeys:** record an idea or dialogue on the move; edit it non-destructively; keep a local project library; export for a collaborator or desktop editing; optionally transcribe speech when that feature is supported locally. Advanced voice generation is a later research track gated on quality, latency, app size, battery, privacy and licensing.

## Technical architecture and reuse

- **Native client candidate:** SwiftUI + AVFoundation/AVAudioEngine for capture, editing and playback; SwiftData or SQLite for file and project metadata; Files/Share Sheet for import/export.
- **True local core:** audio files, edits, project metadata, waveform cache, bookmarks and basic deterministic DSP are stored and processed in the iOS sandbox. Originals stay unmodified; derivative edits record source fingerprints and parameters.
- **Experimental on-device inference:** Apple Speech on-device recognition where available for the actual device and language; benchmark compact permissible Core ML/audio models before adopting. An unavailable capability should be labeled honestly, never silently routed to a server.
- **Optional augmented mode:** explicit secure LAN/Tailscale pairing with the **existing** VoiceStudio backend for expensive cloning, video dubbing or big models; clear consent for every upload. Disabling network must not disable core recording/editing/export.
- **Contracts:** reuse existing VoiceStudio metadata, audio formats and job representations where compatible; avoid wholesale Electron/Python rewrites. Audit AGPL-3.0 obligations and all bundled inference/model weights and third-party licenses before any new distribution.
- **Security:** no automatic audio telemetry, no default cloud backups, no network permission necessary for MVP, private project storage, explicit audio delete/export, no recording without visible microphone consent.

## Roadmap and acceptance gates

### VP-00 — Feasibility, product design and architecture
Audit desktop audio/UI/API interfaces and dependencies, confirm iOS input/output file format support, design record/library/editor/transcript/export screens, profile a real-device capture baseline, confirm licensing. **Gate:** testable offline UX, bounded build target, clear non-goals, no silent server fallbacks.

### VP-01 — First fully offline vertical slice
Build one-tap record, visible microphone state, pause/resume, non-destructive trim, waveform, playback, rename, local library and WAV/M4A export with Files. **Gate:** fresh install + airplane mode → capture ≥60 seconds → trim → save → relaunch → export correctly; no Azathoth/server/network traffic.

### VP-02 — Standalone creative MVP
Multiple projects, autosave, undo, simple deterministic normalization/cleanup, markers, batch export, interruption and Bluetooth-device handling, safe storage cleanup, accessible controls and large-text handling. Optional device-supported local transcription must fail transparently where unavailable. **Gate:** reopen a multi-clip project after termination or device interruption without corrupting the original; export unchanged media where requested.

### VP-03 — Local AI feasibility research
Measure permitted small on-device transcription, pitch/F0 analysis, local voice transformation and eventually voice-cloning candidates. Document cold start, median/slow inference, peak RAM, thermal throttling, battery and quality against representative recordings. **Gate:** each model feature accepted or rejected by real device measurements; no guarantee of desktop-quality cloning on all iPhones.

### VP-04 — Optional secure desktop augmentation
Use existing VoiceStudio server over user-enabled Tailscale/HTTPS and authenticated job API. Choose exactly which clips to send; display job/source identity, progress, results and deletion controls. **Gate:** offline workflows remain identical if host is off, connection unavailable or account absent.

### VP-05 — iPhone Product Reality and distribution
Real-device recording/microphone tests, rotation/background-interruption safety, accessibility, privacy labels, license clearance, signed build and optional TestFlight/App Store. **Gate:** tested evidence from a specific commit and target device, explicit consent, complete offline baseline, no invented model capability.

## First bounded planning tasks

1. Produce a desktop-to-iOS reuse map: audio formats, data contracts, licenses and impossible Windows/Electron dependencies.
2. Prove the complete on-device recording/edit/library/export loop on one physical iPhone.
3. Benchmark supported offline transcription vs approved compact models, with honest device/language gating.

## Definition of done for MVP

VoiceStudio Pocket starts and works in airplane mode, records and edits user-generated voice, safely saves a project, restores it after process termination, and exports a usable audio file. It needs **neither VoiceStudio desktop nor an account** to complete that workflow. No Product Reality claim from mocks alone.

## Portfolio governance

This is one of five mobile product charters: Iron God Pocket, VoiceStudio Pocket, Knowledge Engine Pocket, Rocksmith Pocket Workshop, and Everward iOS. Product work remains in its governing repo; larger remote processing stays in the existing backend where needed. Keep all existing VoiceStudio CI/review/branch protections and Claude's active CI fixes untouched. This is documentation only; implementation proposals should be separately reviewed and tested.
