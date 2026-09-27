# Singing Mode Expansion

## Project intent

Extend the VoiceStudio fork with a first-class **Singing Mode** while preserving the existing local-first, pluggable-engine architecture.

The target is not to force a speech TTS engine to sing. Singing Mode should treat singing as its own audio task with explicit pitch, timing, lyric, and voice-identity requirements.

## User-facing goal

A user should eventually be able to choose one of two workflows:

1. **Singing voice conversion**
   - Input: a guide vocal that already contains the desired melody, rhythm, phrasing, and lyrics.
   - Output: the same performance characteristics rendered with the selected/cloned target voice.

2. **Singing synthesis**
   - Input: lyrics + melody/notes (MIDI/MusicXML or an internal note timeline).
   - Output: a generated sung vocal in the selected/cloned target voice.

The first MVP should focus on **singing voice conversion**, because the melody and timing already exist in the guide vocal and the system only needs to solve timbre/voice transfer reliably.

## Design principles

- Local-first by default.
- Reuse VoiceStudio's engine catalogue, model lifecycle, device detection, batch queue, project storage, and API/MCP patterns where practical.
- Add singing as a distinct capability instead of hiding it behind the ordinary TTS contract.
- Never silently fall back from singing to speech synthesis.
- Keep pitch/timing data explicit and inspectable.
- Cache expensive preprocessing and generation stages.
- Preserve source audio and derived artifacts separately.
- Track engine/model provenance for reproducible results.
- Treat model licenses independently from the VoiceStudio application license.

## Proposed architecture

```text
Singing workspace
      |
      +-- guide vocal / song audio
      |       |
      |       +-- optional vocal isolation
      |       +-- pitch (F0) extraction
      |       +-- timing / segmentation
      |       +-- lyric alignment if available
      |       |
      |       +--> Singing Voice Conversion engine
      |
      +-- MIDI / MusicXML + lyrics
              |
              +-- note/phoneme timeline
              +-- duration + pitch controls
              |
              +--> Singing Synthesis engine

Both paths
      |
      +--> target voice / speaker identity
      +--> render
      +--> post-process
      +--> preview / compare
      +--> export stems
```

## Capability model

Add explicit engine capabilities rather than assuming all voice-cloning engines can sing.

Candidate flags:

```text
singing_conversion
singing_synthesis
pitch_conditioning
phoneme_timing
lyrics_alignment
speaker_clone
speaker_embedding
emotion_control
vibrato_control
breath_control
midi_input
musicxml_input
```

The Model Catalogue should display these independently from ordinary TTS cloning support.

## MVP — Singing Voice Conversion

### Inputs

- clean guide vocal, or
- full mix that can pass through the existing Vocal Isolation feature;
- selected/cloned target voice;
- optional lyrics for QA/alignment.

### Processing

1. Ingest and hash source.
2. Isolate or accept vocal stem.
3. Detect sample rate, duration, and channels.
4. Extract pitch/F0 contour.
5. Segment voiced/unvoiced regions.
6. Run singing voice conversion.
7. Preserve original timing and pitch contour unless the engine explicitly supports controlled modification.
8. Loudness-normalize preview.
9. Produce original-vs-converted A/B preview.
10. Export converted vocal stem plus provenance metadata.

### Acceptance criteria

- output duration remains aligned to the guide vocal;
- no unexplained global timing shift;
- voiced regions preserve intended melody;
- output contains no catastrophic octave jumps;
- source and output hashes are recorded;
- engine/model/version are recorded;
- batch generation can resume without redoing completed stages;
- failures stop cleanly and keep prior successful artifacts.

## Phase 2 — Lyrics + MIDI singing synthesis

### Inputs

- MIDI or MusicXML melody;
- lyrics;
- tempo/time-signature data;
- selected target voice.

### Internal representation

Use a tool-independent event model, for example:

```json
{
  "note_id": "n0001",
  "start": 12.500,
  "duration": 0.625,
  "midi_pitch": 64,
  "lyric": "light",
  "phonemes": [],
  "velocity": 0.82,
  "expression": {},
  "source": "midi"
}
```

Do not bind the project permanently to one singing model's private format.

### Future controls

- vibrato depth/rate;
- pitch-bend curve;
- breathiness;
- dynamics;
- legato;
- consonant timing;
- note transitions;
- harmony generation;
- octave/key transposition.

## Voice identity strategy

Speech-clone compatibility does **not** automatically imply singing compatibility.

Research should compare:

- engines that can reuse a speech reference directly;
- engines that require a dedicated singing dataset;
- engines that require a trained speaker model;
- engines that use speaker embeddings;
- zero-shot vs fine-tuned conversion quality.

The application should tell the user which kind of reference material each singing engine actually needs.

## Engine research lane

Evaluate local/open implementations before selecting a default.

Candidate classes to benchmark:

- singing voice conversion (SVC);
- retrieval-based voice conversion;
- diffusion singing synthesis;
- MIDI/phoneme conditioned singing synthesis.

For every candidate record:

- license and commercial-use restrictions;
- Windows support;
- CPU support;
- CUDA requirements;
- VRAM/RAM use;
- inference speed;
- minimum training/reference data;
- zero-shot cloning support;
- output sample rate;
- API/CLI stability;
- quality on sustained vowels;
- pitch fidelity;
- consonant intelligibility;
- vibrato preservation;
- cross-language behavior.

No engine becomes the default based only on popularity.

## UI concept

Add a new **Singing** workspace next to the existing Voice Cloning / Dubbing / Voice Design workspaces.

Initial screen:

```text
SINGING

Mode:
  (o) Convert an existing vocal
  ( ) Generate from lyrics + melody   [later]

Guide vocal: [Choose file]
Target voice: [Voice selector]
Engine:       [Compatible singing engines only]

[Analyze]
[Generate preview]
[Render full vocal]

A/B:
Original | Converted

Pitch trace:
guide F0 vs output F0
```

The pitch trace is important: Singing Mode should show whether the model preserved the musical performance instead of asking the user to trust it blindly.

## API direction

Keep singing separate from ordinary `/generate` speech calls.

Possible future endpoints:

```text
POST /v1/audio/singing/convert
POST /v1/audio/singing/synthesize
GET  /v1/audio/singing/jobs/{id}
GET  /v1/audio/singing/engines
```

MCP tools can wrap the same service so agents can render vocals programmatically.

## Project / batch artifacts

Suggested project layout:

```text
project/
  source/
    guide_vocal.*
    original_mix.*
  analysis/
    f0.json
    segments.json
    lyric_alignment.json
  voice/
    target_voice.json
  renders/
    preview.wav
    vocal_full.wav
  metadata/
    generation.json
  logs/
```

## Testing strategy

### Unit tests

- MIDI pitch conversion;
- timestamp/duration conversion;
- F0 serialization;
- segment boundaries;
- resampling;
- output duration tolerances;
- capability routing;
- metadata/provenance schema.

### Golden audio tests

Use short legally safe fixtures with known melodies.

Measure:

- F0 error in cents;
- voiced/unvoiced agreement;
- onset timing difference;
- duration drift;
- octave-error rate;
- output clipping;
- loudness;
- deterministic metadata integrity.

### Human Product Reality checks

Only after deterministic checks pass:

- does the converted voice plausibly resemble the target voice?
- are lyrics intelligible?
- do transitions sound musical?
- is vibrato natural?
- are sustained vowels stable?

## Licensing and consent

- Clone/convert only voices the user has permission to use.
- Keep application license and model license decisions separate.
- Surface commercial-use restrictions for the selected model before export when known.
- Do not bundle model weights whose licenses prohibit redistribution.

## Implementation status\n\nS0/S1 establish a fail-closed singing boundary in `backend/services/singing_backend.py` and explicit catalogue capability metadata. The deterministic backend is a plumbing/test harness only; it does **not** claim audible voice conversion quality or satisfy Product Reality. Real SVC remains S4 after the project/input and pitch-analysis foundations.\n\n## Initial implementation milestones

- [x] S0 — Architecture decision: singing as separate engine capability.
- [x] S1 — Singing engine capability schema + catalogue filtering.
- [ ] S2 — Singing project/input data model.
- [ ] S3 — F0/pitch-analysis service with golden fixtures.
- [ ] S4 — First local singing voice-conversion adapter.
- [ ] S5 — Singing workspace: guide vocal + target voice + preview.
- [ ] S6 — A/B playback + pitch comparison.
- [ ] S7 — Batch/resume + provenance metadata.
- [ ] S8 — API/MCP singing conversion endpoint.
- [ ] S9 — Benchmark multiple local SVC engines.
- [ ] S10 — Lyrics + MIDI internal representation.
- [ ] S11 — First singing-synthesis adapter.
- [ ] S12 — Full lyrics + melody Singing Mode.

## Definition of MVP success

Given a short, clean sung guide vocal and an authorized target voice, VoiceStudio can locally generate a converted vocal that:

1. preserves the guide's musical timing;
2. preserves the intended melody within defined pitch tolerances;
3. audibly transfers target-speaker identity;
4. exports a reusable vocal stem;
5. records enough provenance to reproduce the render;
6. requires no cloud service.

The first milestone is **not** "make any text sing." The first milestone is a reliable, measurable singing-voice-conversion path that gives VoiceStudio a real musical-voice capability without compromising the existing speech architecture.
