# Costs

**Total spend so far: $1.90.** Every stage except real Wan 2.2 motion ran on
a free tier (`ffmpeg` work - Ken Burns clips, placeholder score, the whole
`assemble` stage - is local and free by construction). The one real cost is
12 Wan 2.2 motion clips bought through Magic Hour's hosted API, after a free
16GB-GPU route (Kaggle/Colab) was confirmed unable to run the model at all
(see FAILURES.md) - per-shot cost breakdown is in `MEASUREMENT.md`. Figures
below are counted directly from `runs.jsonl` (348 logged calls as of this
writing).

## Calls by stage

| stage | calls | errors | models used |
|---|---:|---:|---|
| smoke | 218 | 55 | gemini-3.8-flash, gemini-3.8-flash-tts, flux-1-schnell, and later additions |
| keyframes | 36 | 0 | flux-2-klein-4b (primary), flux-1-schnell (fallback) |
| narration | 48 | 4 | gemini-3.8-flash-tts (primary), gemini-3.8-flash-lite-tts (fallback) |
| reference | 21 | 1 | flux-1-schnell |
| shots | 24 | 0 | ffmpeg-kenburns-fallback (12, no GPU) + magichour/wan-2.2 (12, real motion, $1.90 total) |
| music | 1 | 0 | ffmpeg-placeholder-pad (no GPU) |

Error counts are mostly from live-testing during development (quota checks,
model-name discovery, API-key rotation while chasing the Gemini TTS quota
issue - see FAILURES.md), not failures in the current, working pipeline.
`smoke`'s 218 calls in particular reflect repeated connectivity checks across
several `.env` key changes, not 218 separate narration/image attempts. Full
per-stage success-rate and latency numbers are in `MEASUREMENT.md`.

## Why $0 (everything except real motion)

- **Gemini** (narration, and any text calls): free tier, rate-limited rather
  than billed (confirmed live: 10 requests/day per TTS model, per Google
  account - see FAILURES.md).
- **Cloudflare Workers AI** (reference, keyframes): used within its free
  allocation; no billing configured.
- **ffmpeg** (radio cut, shots `--fallback`, music `--fallback`, all of
  `assemble`): runs locally, no API involved.

## Real motion: $1.90 (Wan 2.2 via Magic Hour)

A free 16GB-GPU route for real Wan 2.2 motion (Kaggle and Colab T4s) was
tested exhaustively and is a **confirmed dead end** - the model's own README
states it needs >=24GB VRAM, and every shot OOM-killed regardless of
`--frame_num`, with no smaller `--size` available for this task (full trail
in FAILURES.md). Real motion for all 12 shots instead came from Magic Hour's
hosted `wan-2.2` API, billed per second of output: $1.9008 total, spread
across 6 free-credit accounts (~400 starter credits each) rather than paid
outright. Per-shot cost breakdown is in `MEASUREMENT.md`. Agnes AI
(`agnes-video-2.5-flash`) was also integrated as a $0 alternative but is
currently blocked by the provider's own free-tier capacity (`503
video_queue_full`), not by anything in this project - see FAILURES.md.

ACE-Step music generation still needs a GPU session (Kaggle/Colab) that
hasn't been run to completion yet, so its cost (expected $0, GPU-quota-based
not billed) isn't reflected above.

## If this needed to scale beyond free tiers

Not costed in detail here since it hasn't happened, but the shape of it:
Gemini TTS beyond the free quota is billed per character; Cloudflare Workers
AI beyond its free allocation is billed per image; a paid GPU (rather than
Kaggle's free weekly quota) would be billed per GPU-hour. None of these were
needed to produce the current film.
