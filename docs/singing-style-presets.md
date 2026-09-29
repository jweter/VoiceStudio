# Singing + Performance-Style Presets

**Status:** planned  
**Roadmap:** Phase 4.7  
**Added:** 2026-09-29

## Product vision

VoiceStudio should let a user clone **their own** voice and then choose a reusable singing, rap, or spoken-performance style. The output should sound like the same person adopting a different performance vocabulary—not like the system replaced them with the reference artist.

The design therefore separates two concepts:

- **Identity:** who is speaking or singing.
- **Performance style:** how that identity delivers the line.

That separation is the feature.

## User story

1. Create or select a consented VoiceStudio voice profile.
2. Choose **Performance Style**.
3. Pick a preset or create a custom one.
4. Set **Style Strength** from 0–100.
5. Sing, speak, import lyrics + melody, or provide a guide vocal.
6. Preview a short phrase immediately.
7. Adjust style dimensions if desired.
8. Render the complete vocal while retaining the selected voice identity.

## Control model

A style profile should be serializable and engine-independent where possible.

Suggested dimensions:

- mode: sung / rap / spoken / hybrid
- energy
- register preference
- chest/head/mix tendency
- onset hardness
- consonant attack
- vowel openness / shaping
- breathiness
- rasp / grit / distortion intent
- vibrato rate
- vibrato depth
- pitch scoop / slide tendency
- melisma tendency
- pitch stability
- rhythmic placement: ahead / centered / behind beat
- phrase length
- pause frequency
- legato vs clipped articulation
- dynamic range
- intimacy / projection
- ad-lib probability
- non-lexical vocalization tendency
- formant-shift allowance
- double-track / harmony tendency
- FX hints stored separately from the dry vocal identity transform

Each dimension needs a documented range, default, interaction rules, and engine capability fallback.

## Initial reference map

The first preset set should explore the user's preferred performance space:

- Ozzy Osbourne / Black Sabbath → Haunted Doom Croon
- Metallica → Percussive Thrash Bark
- Tool → Controlled Alt-Metal Intensity
- Primus → Elastic Funk-Metal Character
- Judas Priest → Operatic Metal Screamer
- Iron Maiden → Galloping Arena Tenor
- Type O Negative → Deep Gothic Baritone
- Korn → Nu-Metal Whisper-to-Break
- Eminem → Precision Rapid-Fire Rap
- Snoop Dogg → Laid-Back West-Coast Flow
- Rammstein → Industrial Command Baritone
- Christopher Walken → Staccato Dramatic Spoken
- Freddie Mercury → Theatrical Operatic Rock
- Led Zeppelin → Blues-Rock Wail

These references are research targets for measurable performance traits. User-facing names should remain descriptive unless appropriate rights/licensing support branded naming.

## Technical architecture

### 1. Identity representation

Use the selected cloned voice/profile as the identity anchor. The style subsystem must not overwrite the speaker embedding.

Requirements:

- identity embedding generated independently of style reference
- stable identity representation across presets
- explicit provenance + consent metadata
- same identity embedding usable for sung, spoken, and rap modes
- identity similarity measured before post-FX

### 2. Performance-style representation

Start deterministic before learned.

**Stage A — parameter presets**

Hand-authored control vectors make behavior inspectable and testable. This is the fastest path to proving the UX and disentanglement architecture.

**Stage B — style encoder**

Learn a style representation from authorized reference audio while explicitly excluding speaker identity as much as practical. Compare disentanglement approaches, reference encoders, prosody encoders, and token-based style representations.

A learned style asset must carry:

- source provenance
- license / authorization state
- extraction model version
- dimensional summary
- embedding version
- quality/eval results

### 3. Pitch + timing input

Support progressively:

1. guide vocal pitch extraction
2. MIDI note input
3. MusicXML
4. manual piano-roll editing
5. generated melody contour
6. rap/spoken free-rhythm mode

Represent the plan as time-indexed pitch, phoneme/syllable alignment, note boundaries, dynamics, and optional ornament markers.

### 4. Renderer

Renderer inputs should include:

- identity / voice profile
- lyrics
- performance style
- style strength from 0.0 to 1.0
- optional pitch plan
- optional timing plan
- language
- preview or final quality mode

The engine adapter should declare which style dimensions it supports so unsupported controls degrade gracefully.

### 5. Vocal production stage

Keep production FX separate from style/identity synthesis.

Possible chain:

- corrective EQ
- de-esser
- compression
- saturation / controlled distortion
- doubling
- harmony generation
- slap delay / tempo delay
- reverb
- limiter

Identity evaluation should be run on the dry or lightly normalized vocal before these effects.

## Style-strength behavior

Style Strength should not be a naive audio blend.

At 0:
- baseline cloned voice
- neutral delivery

At 25:
- light phrasing/articulation influence

At 50:
- clearly recognizable performance behavior

At 75:
- strong style behavior while preserving identity

At 100:
- maximum allowed style transform subject to identity-retention and artifact gates

Per-dimension caps should prevent extreme presets from producing physically implausible or unstable outputs.

## Preset blending

Later milestone: blend two **performance** presets.

Examples:

- Deep Gothic Baritone + Industrial Command Baritone
- Theatrical Operatic Rock + Blues-Rock Wail
- Percussive Thrash Bark + Controlled Alt-Metal Intensity

Do not interpolate raw speaker identities. Blend normalized style dimensions / embeddings only.

## Evaluation harness

Every preset and renderer revision should run the same fixture suite.

### Identity retention

Compare generated output against the user's neutral clone:

- speaker verification similarity
- embedding cosine similarity
- human same-speaker preference test

Set a floor; style improvements cannot ship if identity falls below it.

### Style adherence

For each preset:

- human rubric against named acoustic traits
- automated prosody features where meaningful
- pitch contour statistics
- vibrato rate/depth
- onset / consonant envelope
- timing offset from beat
- spectral tilt / harmonicity / roughness where relevant

### Musical accuracy

- note onset error
- F0 cents error on voiced frames
- sustained-note drift
- lyric/phoneme alignment
- timing deviation

### Audio quality

- clipping
- dropouts
- discontinuities
- excessive formant warping
- intelligibility
- naturalness pairwise preference

### Performance targets

Preview:
- first audible phrase within the existing interactive-preview budget when hardware allows
- partial rerender of one phrase instead of whole song

Final:
- deterministic seed support
- resume from phrase/checkpoint
- per-phrase cache keyed by identity + lyrics + pitch plan + style vector + engine/version

## UI plan

### Voice Profile

Add:

- Performance Style selector
- Style Strength slider
- Favorite styles
- Try-it phrase
- A/B neutral vs styled
- Save as combination

### Singing Studio

Initial controls:

- guide vocal / MIDI / manual melody input
- lyric alignment
- preset selector
- style strength
- advanced style dimensions
- preview selected phrase
- render selected range
- render full vocal

### Custom style editor

Users should be able to save their own named styles without machine learning:

- duplicate preset
- alter dimensions
- audition phrase
- save locally
- export/import style JSON

Later, authorized reference audio can initialize those dimensions or a learned style embedding.

## Data model sketch

A style record should contain:

- id
- name
- version
- performance mode
- normalized parameter map
- optional learned embedding
- provenance type
- authorization state
- extraction/model version
- evaluation summary

## Milestones

### S0 — taxonomy + schema
- freeze first style dimensions
- JSON schema
- engine capability contract
- neutral baseline preset
- identity-retention metric harness

### S1 — deterministic preset engine
- style preset storage
- 0–100 strength
- backend API
- Voice Profile UI
- 3 contrasting presets

Suggested first three:

1. Deep Gothic Baritone
2. Precision Rapid-Fire Rap
3. Theatrical Operatic Rock

They exercise very different pitch/rhythm/register behavior and expose whether the control model generalizes.

### S2 — singing input pipeline
- guide-vocal F0 extraction
- lyrics alignment
- MIDI import
- phrase slicing
- preview cache

### S3 — full initial preset library
Implement and tune all current reference targets.

### S4 — learned style representation
Only after deterministic presets and evaluation gates work.

### S5 — custom styles + blending
- user-created presets
- two-style blend
- favorites
- portable style files

## Rights / consent / provenance

- A voice identity must be consented by the person whose voice is cloned.
- Keep named artist references in R&D documentation as performance-analysis targets; prefer descriptive product preset names unless appropriately licensed.
- Learned style assets require traceable authorized/licensed source material.
- Never make a learned style asset impossible to remove independently of a user's voice profile.
- Store provenance with every learned style model/embedding.
- Do not let post-FX hide identity-retention failures during evaluation.

## Definition of done for Phase 4.7

Phase 4.7 is complete when:

1. One cloned user voice can render neutral plus at least six substantially different singing/rap/spoken presets.
2. The system passes the agreed same-speaker identity threshold across those presets.
3. Style Strength produces a monotonic perceptual increase without abrupt identity collapse.
4. Guide-vocal and MIDI-driven singing both work end-to-end.
5. Phrase-level preview and rerender are available.
6. Presets are serialized and portable.
7. The fixture/evaluation suite blocks regressions in identity, pitch/timing, and artifact rate.
8. The user can create and save at least a parameter-based custom style.
