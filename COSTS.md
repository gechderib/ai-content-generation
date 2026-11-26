# Costs

**Total spend so far: $0.00.** Every model call this project has made is on a
free tier; `ffmpeg` work (Ken Burns clips, placeholder score, the whole
`assemble` stage) is local and free by construction. Figures below are
counted directly from `runs.jsonl` (237 logged calls as of this writing).

## Calls by stage

| stage | calls | errors | models used |
|---|---:|---:|---|
| smoke | 122 | 31 | gemini-3.8-flash, gemini-3.8-flash-tts, flux-1-schnell |
| keyframes | 33 | 0 | flux-2-klein-4b (primary), flux-1-schnell (fallback) |
| narration | 48 | 4 | gemini-3.8-flash-tts (primary), gemini-3.8-flash-lite-tts (fallback) |
| reference | 21 | 1 | flux-1-schnell |
| shots | 12 | 0 | ffmpeg-kenburns-fallback (no GPU) |
| music | 1 | 0 | ffmpeg-placeholder-pad (no GPU) |

Error counts are mostly from live-testing during development (quota checks,
model-name discovery, API-key rotation while chasing the Gemini TTS quota
issue - see FAILURES.md), not failures in the current, working pipeline.
`smoke`'s 122 calls in particular reflect repeated connectivity checks across
several `.env` key changes, not 122 separate narration/image attempts.

## Why $0

- **Gemini** (narration, and any text calls): free tier, rate-limited rather
  than billed (confirmed live: 10 requests/day per TTS model, per Google
  account - see FAILURES.md).
- **Cloudflare Workers AI** (reference, keyframes): used within its free
  allocation; no billing configured.
- **ffmpeg** (radio cut, shots `--fallback`, music `--fallback`, all of
  `assemble`): runs locally, no API involved.

## GPU minutes (Wan 2.2, ACE-Step) - not yet incurred

`runs_log.log_call`'s `gpu_minutes` field exists specifically for
Kaggle-imported clips/candidates (read from each notebook's own
`gpu_log.json`), but as of this writing both Kaggle notebooks have been stuck
in Kaggle's queue rather than actually running (see FAILURES.md), so no real
GPU time has been spent yet. Once they run, this section should be updated
with: total GPU-minutes for the 12 Wan 2.2 clips and the ACE-Step candidates,
and Kaggle's GPU usage is itself free (quota-limited, ~30 hours/week on the
free tier) rather than billed, so this is expected to also be $0 unless that
free quota is exceeded.

## If this needed to scale beyond free tiers

Not costed in detail here since it hasn't happened, but the shape of it:
Gemini TTS beyond the free quota is billed per character; Cloudflare Workers
AI beyond its free allocation is billed per image; a paid GPU (rather than
Kaggle's free weekly quota) would be billed per GPU-hour. None of these were
needed to produce the current film.
