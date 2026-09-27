# ADR-SING-001: Treat singing as a separate engine capability

**Status:** Accepted  
**Date:** 2026-09-27  
**Scope:** VoiceStudio Singing Mode  
**Authority:** `docs/projects/singing-mode.md`

## Context

VoiceStudio already supports speech synthesis, voice cloning, dubbing, voice design, model routing, and audio processing. Those capabilities do not imply that a speech engine can preserve a sung performance.

The active Singing Mode plan requires two distinct workflows:

1. **Singing voice conversion** — a guide vocal supplies melody, rhythm, phrasing, timing, and lyrics; VoiceStudio transfers the authorized target voice while preserving the musical performance.
2. **Singing synthesis** — lyrics plus an explicit melody/note representation drive a singing-specific synthesis engine.

The first MVP is singing voice conversion.

The archived `docs/adr/SPIKE-02-singing.md` selected an OmniVoice singing finetune, but that approach is superseded for melody-preserving Singing Mode because it does not provide source-song F0/MIDI conditioning. It may remain useful only as an expressive-TTS style mechanism and must not be treated as the active Singing Mode architecture.

## Decision

Singing is a **first-class, separate engine capability**.

VoiceStudio must not infer singing support from ordinary TTS, speech cloning, speaker cloning, or a style/control tag. Engines advertise singing support explicitly through capability metadata.

The capability vocabulary may grow over time, but the architecture reserves at least these independent concepts:

- `singing_conversion`
- `singing_synthesis`
- `pitch_conditioning`
- `phoneme_timing`
- `lyrics_alignment`
- `speaker_clone`
- `speaker_embedding`
- `vibrato_control`
- `breath_control`
- `midi_input`
- `musicxml_input`

An engine that supports `speaker_clone` but not `singing_conversion` is not eligible for Singing Mode conversion.

An engine that supports speech generation but lacks a singing capability must never be selected as an implicit fallback.

## Conversion boundary

The MVP conversion pipeline is conceptually:

```text
source or guide vocal
  -> optional vocal isolation
  -> source hash + audio metadata
  -> F0 / voiced-unvoiced analysis
  -> target voice identity/reference
  -> singing-conversion engine
  -> deterministic timing/pitch/provenance checks
  -> preview/export
```

The guide vocal remains the timing and melody authority unless a future engine explicitly exposes controlled pitch/timing modification.

The conversion engine is responsible for timbre/voice transfer. It is not allowed to invent a replacement melody because the engine lacks conditioning support.

## Synthesis boundary

Future lyrics + MIDI/MusicXML synthesis remains separate:

```text
lyrics + melody/notes
  -> tool-independent note/phoneme timeline
  -> singing-synthesis engine
  -> mark_synthetic (mandatory synthetic-audio provenance chokepoint)
  -> deterministic timing/pitch/provenance checks
  -> preview/export
```

Singing synthesis must not force its model-private event representation into the project data model. S10 defines the first tool-independent note representation.

## Routing rules

1. Singing work is routed only to engines that explicitly advertise the required singing capability.
2. Missing singing capability is a visible incompatibility, not a reason to route to speech TTS.
3. Engine/model licensing is evaluated independently from the application license.
4. Local-first operation remains the default.
5. Source/reference voice material and derived artifacts remain distinct.
6. Model/engine/version and source/output hashes are provenance requirements for completed renders.

## Synthetic-audio marking boundary

Every generated Singing Mode audio artifact — conversion or synthesis — must pass through the repository's existing `mark_synthetic` chokepoint before it can be exposed through preview, history, export, API/MCP delivery, or batch completion.

Deterministic singing provenance (source hashes, engine/model/version, target voice identity, F0/timing evidence) supplements that mandatory synthetic-audio marking; it does not replace it. No adapter may write a user-consumable singing render directly around `mark_synthetic`.

## Verification boundary

Automated verification may establish objective properties including:

- F0 serialization fidelity;
- voiced/unvoiced agreement;
- pitch error in cents;
- onset timing difference;
- duration drift;
- octave-error rate;
- clipping/loudness constraints;
- source/output hashes;
- engine/model/version provenance;
- resume/idempotency behavior;
- API/storage/capability routing contracts.

Automated evidence must **not** claim that:

- the output subjectively resembles the intended target voice;
- lyrics are sufficiently intelligible;
- transitions sound musical;
- vibrato sounds natural;
- sustained vowels are perceptually stable.

Those are human Product Reality checks after deterministic gates pass.

## Consent and safety boundary

Singing conversion and synthesis may use only voices the user has permission to use. The system must not weaken VoiceStudio's existing local-first behavior, model-license disclosure, or provenance requirements in order to add Singing Mode.

## Consequences

### Positive

- prevents ordinary TTS engines from being misrepresented as singing engines;
- keeps source melody/timing explicit and measurable;
- allows multiple SVC/singing-synthesis engines without coupling the project to one model;
- gives the Model Catalogue and UI a precise compatibility contract;
- separates deterministic audio correctness from subjective listening judgments.

### Trade-offs

- engine metadata requires new capability fields;
- existing engines need explicit compatibility declarations rather than implicit eligibility;
- Product Reality remains a necessary serial boundary for perceived identity and musical quality;
- conversion and synthesis need different adapters and may have different reference/training requirements.

## Follow-up

- **S1:** add singing capability schema + catalogue filtering.
- **S2:** define singing project/input data model.
- **S3:** implement F0/pitch analysis with golden fixtures.
- **S4:** add the first local singing voice-conversion adapter.

This ADR completes **S0** of `docs/projects/singing-mode.md`.
