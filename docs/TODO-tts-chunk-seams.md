# TODO — TTS chunk-seam audibility investigation (Phase 5 / T2)

## Problem reported by user during editorial decisions (2026-04-14)

> "T2 ok but jumps between each is very audible and speaker change it voices"

Two symptoms observed in production episodes:

1. **Audible chunk transitions** — the 150ms crossfade softens but does not mask the edit points between Cartesia-generated TTS chunks.
2. **Speaker voice drift** — voice timbre and pacing shift slightly between chunks, as if the speaker changed mid-sentence.

## Likely root causes

- Cartesia generates each 1500-char chunk **statelessly**. No voice state is shared across API calls, so the model picks a slightly different prosodic baseline each time.
- Current stitching is file-level (pydub `AudioSegment.append(crossfade=150)`), not sample-level. Short crossfade doesn't blend formant/pitch differences.
- Chunk boundaries currently fall on paragraph breaks (`split_script` in `tts/cartesia.py`). If a paragraph ends with a rising intonation and the next begins abruptly, the discontinuity is perceptible.

## Proposed experiments (require user approval to apply)

Per user: **"T2 confirm but need to be tested for approval"** — run each experiment, produce a short A/B sample, user listens and approves before merging.

### E1 — Longer crossfade
Raise `crossfade` in `cartesia.py:56` from 150 ms to 300 ms or 500 ms. Simplest change.
Risk: clipped words if paragraphs don't end with trailing silence.

### E2 — Cartesia voice-continuity parameters
Check if the current Cartesia API version (`2025-04-16`) exposes `context_id`, `speaker_continuity_token`, or similar. If yes, pass the previous chunk's output as context to the next call.
Risk: API version mismatch — may require upgrading `CARTESIA_VERSION`.

### E3 — Sentence-aware chunking
Rework `split_script` to break on sentence boundaries (regex on `.!?`) rather than paragraph count. Fewer, larger chunks → fewer seams.
Risk: larger chunks may hit Cartesia's TTS length limit or increase per-call latency.

### E4 — Single-call synthesis
Some TTS APIs accept the entire script in one call (returns one stream). Check if Cartesia supports this for scripts up to ~15 min. If yes, eliminates seams entirely.
Risk: longer API calls, higher timeout risk, harder retry semantics.

### E5 — Post-processing EQ / compression
Apply a light compressor + high-shelf EQ in pydub to normalize timbre across chunks. Doesn't fix root cause but may mask it.
Risk: audio quality side-effects on the whole file.

## Suggested order

1. **E1** (quick fix — 10 min work, 1 test run)
2. **E3** (medium — refactor chunker, 1-2 test runs)
3. **E2** (depends on Cartesia API — read docs first)
4. **E4** (biggest win if supported)
5. **E5** (last resort cosmetic patch)

## Not in scope for Phase 6

This investigation is deliberately out of Phase 6 because:
- Any fix requires **empirical audio validation** (listening to samples)
- User has explicitly asked for the result to be previewed before approval
- Code changes here are low-risk but **quality regressions are user-visible**

When picking this up: create a new branch, run experiment, generate a 1-min sample MP3, share with user, iterate.
