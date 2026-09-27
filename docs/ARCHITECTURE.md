# Architecture

## Maintained application surface

VoiceStudio is a local-first desktop application. The maintained UI is Electron under `electron/`; do not restore the removed Tauri or legacy UI runtimes.

The repository is organized around these maintained boundaries:

- `electron/` — user-facing Electron desktop UI, renderer, preload, browser assets, tests, and packaging.
- `backend/` — shared FastAPI/backend services, engine routing, model lifecycle, audio processing, dubbing, speaker/voice operations, persistence, and API services.
- `omnivoice/` — core voice-engine package code used by the application.
- `native/` — native desktop bridge/runtime components.
- `scripts/` — deterministic setup, build, migration, CI-support, and maintenance tooling.
- `tests/` and `backend/tests/` — backend, integration, regression, and repository-contract tests.
- `docs/` — product, architecture-decision, operational, and project authority documents.

Repository-local agent rules in `AGENTS.md` and `CLAUDE.md` remain authoritative.

## Voice engine boundary

Speech synthesis, voice cloning, voice design, dubbing, transcription, and singing are separate capabilities. Engine support must be explicit; a speech-cloning engine is not assumed to support singing.

Existing reusable infrastructure includes engine routing, model lifecycle, device detection, speaker cloning/reference handling, audio DSP, dubbing, vocal/source processing, queue/project storage, and API/MCP patterns.

## Singing Mode

The active Singing Mode authority is `docs/projects/singing-mode.md`.

The initial milestone order is:

`S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8`

The first MVP is singing voice conversion. It must preserve guide-vocal timing and melody explicitly; it must not silently replace singing with ordinary speech synthesis or a style-tag approximation.

Singing-specific architecture should remain separable from ordinary TTS:

```text
source/guide vocal
    -> optional vocal isolation
    -> pitch/F0 + voiced/unvoiced analysis
    -> target voice identity/reference
    -> singing conversion engine
    -> deterministic alignment/pitch checks
    -> preview/export + provenance

later:
lyrics + MIDI/MusicXML
    -> tool-independent note/phoneme timeline
    -> singing synthesis engine
```

Capability discovery should model singing independently, including `singing_conversion`, `singing_synthesis`, pitch conditioning, phoneme timing, lyric alignment, speaker identity, MIDI/MusicXML input, and expressive controls as they are implemented.

## Deterministic versus Product Reality evidence

Automated verification may prove:

- schema and capability routing;
- pitch/F0 serialization and numerical fidelity;
- voiced/unvoiced segmentation;
- onset/timing and duration drift;
- octave-error rate;
- clipping/loudness constraints;
- deterministic provenance and source/output hashes;
- resume/idempotency behavior;
- API and storage contracts.

Automated checks do not prove that a converted voice subjectively resembles the intended person, that lyrics are intelligible enough, or that vibrato/transitions/sustained vowels sound natural. Those remain explicit human Product Reality checks after deterministic gates pass.

## Security, privacy, consent, licensing, and provenance

Voice material may contain sensitive biometric-like identity information. Keep source/reference audio local by default and do not add required network calls for Singing Mode.

Only clone or convert voices the user has permission to use. Preserve source hashes and generation provenance where Singing Mode defines them.

Application licensing and model licensing are separate. Do not bundle model weights when their license prohibits redistribution. Surface known commercial-use restrictions before export when applicable.

## Human boundary

Routine implementation, deterministic testing, branch repair, CI diagnosis, and promotion preparation may be automated under repository rules.

Human authority remains required for:

- subjective Singing Mode Product Reality judgments;
- consent/voice-rights decisions that cannot be established from repository evidence;
- choosing a default engine when license, quality, or architecture evidence is materially ambiguous;
- release/publishing authorization;
- destructive migrations, credential changes, or security/privacy boundary changes.

## Change discipline

Use the smallest coherent change, add fail-before/pass-after regression protection when practical, keep docs synchronized with user-visible changes, preserve cross-platform behavior, and follow the merge protocol in `AGENTS.md`.
