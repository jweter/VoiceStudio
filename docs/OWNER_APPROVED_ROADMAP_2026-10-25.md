# Owner-approved roadmap direction — 2026-10-25

Status: proposed roadmap addendum for review, not an accepted implementation or permission to execute.

This records explicit owner decisions. Reconcile with the authoritative local roadmap, AGENTS.md, active claims, dirty worktrees, and newer accepted work before implementation. Existing safety, provenance, testing, product-reality, controller authorization, and worker lease gates remain mandatory. Do not treat GitHub main as newer than the authoritative local version.

## Singing Mode first usable milestone
- Import recorded speech, choose a singing style, generate a singing performance, preview playback, and export audio.
- Preserve existing VoiceStudio capabilities; implement singing as a coherent workflow rather than unrelated processing experiments.
- Validate project/source paths, duration, pitch and timing quality, audible output, and real export; no synthetic-only acceptance.

## Next slices
1. Reconcile and verify existing Singing Mode S2 project-model branch rather than rebuild it.
2. Implement bounded pitch/timing analysis and transformation contracts with native tests.
3. Connect style selection, generation, preview, and export; conduct audible Product Reality acceptance.
