# Singing engine evaluation (S4)

Status: evaluation complete, 2026-11-04. Documentation only: no dependency, model download or code was added.
Authority: the "Engine research lane" in [singing-mode.md](singing-mode.md) and the S4 slice `s4-engine-evaluation`
in `engineering/capability-graph.json` (owner roadmap 2026-10-25, standing development authorization).

Method: each fact below was read from the project's own repository, README, license file or release notes on
2026-11-04 (GitHub metadata through the API). Nothing was installed or run, so every attribute that needs a
measurement is marked **UNKNOWN** rather than guessed. UNKNOWN items become acceptance checks for the first adapter
(S4 `s4-first-adapter`), not blockers for choosing it.

Selection criteria, in order (from the S4 slice): runs fully offline, runs on Windows, usable licence for a
commercial desktop app, stable invocation. Popularity alone is not a reason.

## Candidates

Four open, locally runnable candidates in the "singing voice conversion" and "retrieval-based voice conversion"
classes of the research lane. Diffusion-synthesis and MIDI-conditioned classes (for example DiffSinger) take notes or
phonemes, not a guide vocal, so they do not fit the S4 input and are out of scope here.

| Attribute | RVC (Retrieval-based-Voice-Conversion-WebUI) | so-vits-svc-fork | DDSP-SVC (yxlllc) | Fish Diffusion |
|---|---|---|---|---|
| Class | retrieval-based VC | SVC (fork of so-vits-svc) | SVC, DDSP plus rectified-flow | diffusion SVC/SVS/TTS framework |
| Code licence | MIT ([repo](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI), [LICENSE note](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/MIT%E5%8D%8F%E8%AE%AE%E6%9A%A8%E7%9B%B8%E5%85%B3%E5%BC%95%E7%94%A8%E5%BA%93%E5%8D%8F%E8%AE%AE)) | MIT text with two copyright holders; GitHub reports "NOASSERTION" ([LICENSE](https://github.com/voicepaw/so-vits-svc-fork/blob/main/LICENSE)) | MIT ([repo](https://github.com/yxlllc/DDSP-SVC)) | MIT ([repo](https://github.com/fishaudio/fish-diffusion)) |
| Pretrained-weight licence | Base model trained on the open VCTK set, README states no copyright concern ([README](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI#readme)); ContentVec MIT ([repo](https://github.com/auspicious3000/contentvec)); RMVPE pitch model licence UNKNOWN (no LICENSE file in [yxlllc/RMVPE](https://github.com/yxlllc/RMVPE)) | UNKNOWN (README points to third-party Hugging Face / CIVITAI models, [README](https://github.com/voicepaw/so-vits-svc-fork#readme)) | Requires the NSF-HiFiGAN vocoder weights, released under **CC BY-NC-SA 4.0 (non-commercial)** ([release notes](https://github.com/openvpi/vocoders/releases/tag/pc-nsf-hifigan-44.1k-hop512-128bin-2025.02)); ContentVec MIT | Downloads NSF-HiFiGAN weights only after agreeing to **CC BY-NC-SA 4.0** ([README](https://github.com/fishaudio/fish-diffusion#readme)) |
| Commercial-use restriction | None found for code or base model; RMVPE weights unresolved | Code none; weights UNKNOWN | **Yes: the default vocoder is non-commercial**; the README offers fine-tuning your own vocoder with SingingVocoders ([README](https://github.com/yxlllc/DDSP-SVC#readme)) | **Yes** (same vocoder); also requires attribution and an AI-generated disclosure on derivative audio ([README](https://github.com/fishaudio/fish-diffusion#readme)) |
| Windows | Yes: documented Windows install, Python 3.12 x64, ffmpeg.exe ([README](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI#readme)) | Yes: documented Windows install, one-click .bat, Python 3.11 ([README](https://github.com/voicepaw/so-vits-svc-fork#readme)) | Yes: "python 3.11 (windows) + cuda 13.0 + torch 2.9.1 works" ([README](https://github.com/yxlllc/DDSP-SVC#readme)) | UNKNOWN (conda, Python 3.10 instructions only) |
| CPU | Yes: a CPU requirements file `requirments_cpu_py312.txt` and CPU device fallback in `configs/config.py` ([source](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/configs/config.py)) | Yes: README says CPU inference "is fast enough" (vendor claim) | UNKNOWN (README documents CUDA only) | UNKNOWN |
| CUDA | Optional (cu118 / cu128 requirement files) | Optional; GPU inference needs 4 GB VRAM | Documented against CUDA 13.0 | UNKNOWN |
| VRAM / RAM | UNKNOWN | Inference 4 GB VRAM if on GPU; RAM UNKNOWN | UNKNOWN ("significantly lower" than so-vits-svc and RVC for training, vendor claim) | UNKNOWN |
| Inference speed | UNKNOWN (real-time GUI latency claimed 170 ms end to end on its own hardware) | UNKNOWN | UNKNOWN | UNKNOWN |
| Minimum reference / training data | At least 10 minutes of low-noise speech recommended | UNKNOWN | About 1000 clips recommended for training | UNKNOWN |
| Zero-shot cloning | No: needs a per-voice trained model | No (per-voice model) | No (per-voice model) | No (per-voice model) |
| Output sample rate | Model-dependent; repository ships 32k and 48k v2 configs and a `--resample-sr` option ([configs](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/tree/main/configs/v2), [cli.py](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/infer/cli.py)) | UNKNOWN | 44100 Hz in the default config ([reflow.yaml](https://github.com/yxlllc/DDSP-SVC/blob/6.3/configs/reflow.yaml)) | UNKNOWN |
| Invocation | `infer/cli.py` with `--model --input --output --pitch --index-rate --resample-sr --protect`; the README documents only the web UI, so the CLI is not a documented contract | Documented Typer CLI (`svc infer source.wav`), published on PyPI | Documented script (`main_reflow.py -i -m -o -k`) | Documented training and inference scripts |
| Maintenance | Last push 2026-08-04; tag 2.3.260718 (2026-07-21) | Last push 2026-11-04; v4.2.30 (2026-02-02) | Last push 2026-11-03; tag 5.0 (2024-02-08) | Last push 2026-11-02; last tag v2.1.0 (2023-03-26) |
| Quality (sustained vowels, pitch fidelity, consonants) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

Upstream so-vits-svc itself (AGPL-3.0, archived, last push 2023-11-11) and Seed-VC (GPL-3.0, archived) were checked and
excluded: their copyleft licences and archived state fail the commercial-use and stable-invocation criteria
([so-vits-svc](https://github.com/svc-develop-team/so-vits-svc), [seed-vc](https://github.com/Plachtaa/seed-vc)).

## Ranking

All four pass "runs offline once the weights are downloaded", with the exceptions marked UNKNOWN above.

1. **RVC (recommended).** The only candidate with an explicit, favourable licence story for every component the
   product would redistribute: MIT code, a base model trained on an open dataset, MIT ContentVec. It has an explicit
   Windows and CPU path on a current Python (3.12) and was updated this year. Its weak points are recorded, not hidden:
   the RMVPE pitch weights have no stated licence, the CLI is not a documented contract, and speed and quality are
   unmeasured.
2. **so-vits-svc-fork (runner-up).** Best invocation story (documented CLI, versioned PyPI package) and actively
   maintained, but the weight licence is UNKNOWN because models come from third parties, which fails "usable licence"
   until a redistributable base model is identified.
3. **DDSP-SVC.** Technically attractive, but its default vocoder is non-commercial. It becomes viable only if a
   self-trained vocoder is produced, which is a training project, not an adapter.
4. **Fish Diffusion.** Same non-commercial vocoder, an attribution and AI-disclosure obligation, a Python 3.10 conda
   setup, and no release since 2023.

Popularity was not used: so-vits-svc and RVC have far more stars than DDSP-SVC, which does not change the licence result.

## Decision

The first adapter targets **RVC**, pinned to a tag or commit, invoked as a subprocess behind the S4 adapter contract
(never imported into the backend process), as an optional dependency absent by default.

Conditions carried into `s4-first-adapter` (each is an acceptance check, resolving an UNKNOWN above):

1. Pin the exact RVC tag and record it, with model and input/output hashes, in the conversion provenance.
2. Wrap `infer/cli.py` behind an adapter that fails with a clear "optional singing engine not installed" error, and
   treat any change in its arguments as a version-bump task, because the CLI is undocumented.
3. Resolve the RMVPE licence before shipping its weights. The product already has its own F0 track (S3
   `extract_f0`); the adapter should prefer supplying or selecting a pitch method with a clear licence over bundling RMVPE.
4. Measure CPU inference time and memory on the adapter's one smoke test and record them in this document.
5. If RVC's CLI proves unstable, fall back to so-vits-svc-fork after identifying a redistributable base model.

## Not established here

Inference speed, memory use, and the three quality attributes (sustained vowels, pitch fidelity, consonant
intelligibility) need audio runs, which this slice does not do. The S3 evaluator (`evaluate_f0` in
`backend/services/singing_pitch.py`) is the instrument for pitch fidelity when the adapter exists.
