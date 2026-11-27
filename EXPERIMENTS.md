# Experiments

What was tried, what was picked, and why. Evidence for all of this is in
`runs.jsonl` (every call) and the git history (every prompt/config change).

## Voice

`GEMINI_DEFAULT_VOICE = "Charon"` was picked for a male voice to match the
narrator (the boy, as an adult). Confirmed callable against the live API;
confirmed correct by ear after the first full narration pass (see
FAILURES.md for the style-leak bug found in that same listening pass).

## TTS model: primary vs. lite fallback

`gemini-3.8-flash-tts` is primary, `gemini-3.8-flash-lite-tts` is the
fallback. Both are free-tier (10 requests/day each, confirmed live), so some
shots in the current `outputs/narration/` were generated on the lite model
when the primary's daily quota was hit mid-batch - audibly close enough in
quality that this wasn't worth blocking on, but the primary should be used
for a final-quality pass once its quota resets, batching all 12 shots in one
run rather than iterating.

## Character consistency: image conditioning vs. text repetition

First approach tried: condition Cloudflare's `flux-2-klein-4b` on the golden
reference image (an `image` multipart field, then a guessed `strength`
field). Both returned 200 OK but ignored the reference entirely (wrong
ethnicity, wrong clothing, wrong setting, twice) - see FAILURES.md. Pivoted
to the brief's own anticipated fallback: repeating `character_sheet`'s full
text description and `style_block` in every shot's prompt
(`keyframes.shot_prompt`), with a heuristic (`_mentions`) that only pulls in
the mother's or shop owner's description when a shot's own `image_prompt`
text actually names them - picked over including all supporting characters
in every prompt, which diluted the boy's own description and made his
appearance less consistent across shots.

## Reference candidates

4 candidates per round (`reference.DEFAULT_VARIANTS`), via `flux-1-schnell`
(cheap, fast, no reference-conditioning claim to fail). Two rounds: the
first before the boy's trousers change, the second after. Both rounds
picked variant 1 - no strong reason to prefer another candidate either time,
and keeping the same slot made it easy to tell which reference was current.

## Keyframe model: klein vs. schnell

`flux-2-klein-4b` is primary (the project's two-model slate, see
`config.py`), falling back to `flux-1-schnell` on any `HttpCallError`.
Klein's output generally read as more painterly/consistent with
`style_block`'s "hand-painted illustration" direction than schnell's; schnell
was kept as the fallback specifically because it's the one Cloudflare's own
schema documents fully (strict JSON body, no silently-ignored fields), making
it the more predictable of the two when klein is unavailable.

## Pacing: planned duration vs. narration-driven duration

Two separate instances of the same underlying choice:
- **Radio cut** (`radio.py`): paces each line on `narration_duration_s + 0.4s`
  rather than `timing.json`'s `effective_duration_s`, since the radio cut has
  no visuals to fill the extra time with - this was caught by ear on the
  first radio cut (long gaps between lines).
- **Assemble** (`assemble.py`): same fix, applied later, for the same reason
  caught the same way - the first full assembled cut held each shot open to
  its storyboard-era planned `duration_s` even when the narration finished
  several seconds earlier, which read as sluggish pacing once there was
  picture *and* sound to judge it by. Both now use the narration's own length
  plus a small fixed pad instead of the planning estimate.

## Ducking and loudness

`sidechaincompress` on the music bed, keyed off the narration track:
`threshold=0.05, ratio=8, attack=20ms, release=300ms`. Attack fast enough to
duck before a line gets stepped on, release slow enough (300ms) not to pump
audibly between syllables. Final mix loudness-normalised to `I=-14 LUFS,
TP=-1.5, LRA=11` - a conventional streaming-video loudness target, not
derived from anything specific to this film; no measured-vs-target
comparison pass was run (ffmpeg's single-pass `loudnorm` was used, not the
two-pass measure-then-normalise variant), so the final figure is an estimate
rather than a verified exact match.

## Motion generation: three routes, compared

Three real image-to-video routes were tried, in this order, each abandoned
or kept for a concrete, measured reason (full narrative in `FAILURES.md`;
per-shot cost figures in `MEASUREMENT.md`):

| route | cost | shots completed | reliability | watermark | why kept/dropped |
|---|---|---:|---|---|---|
| Wan 2.2 TI2V-5B, free GPU (Kaggle + Colab T4, 16GB) | $0 | 0 / 12 | 0% - OOM-killed (`SIGKILL`) on every attempt, at every `--frame_num` down to the practical floor | n/a | **Dropped.** Confirmed hardware wall, not a bug: the model's own README states >=24GB VRAM; a free T4 has 16GB. No smaller `--size` exists for this task to fall back to. |
| Agnes AI hosted API (`agnes-video-2.5-flash`, free trial) | $0 | 0 / 12 | 0% - persistent `503 video_queue_full` even after 8 retries at a 60s backoff cap | none (not reached) | **Dropped (for now).** Integration itself works end-to-end (confirmed via its own specific 400/503 responses, not silent failures) - blocked by the service's own free-tier capacity, not by this project's code. Left wired in (`python -m pipeline agnes`) as a $0 retry-later option. |
| Magic Hour hosted API (`wan-2.2`, 480p) | $1.90 total (see `MEASUREMENT.md`) | 12 / 12 | 100% - every attempted shot succeeded | yes, on free tier | **Kept.** Only route that produced real, working motion for all 12 shots. Cost was absorbed across 6 free-credit accounts (~400 credits/account, 2-3 shots each) rather than paid outright. Watermark fixed separately (see FAILURES.md's blur-patch entry) rather than switching providers again. |

The pattern across all three: free-tier GPU compute (Wan 2.2) failed on a
hard resource ceiling no amount of debugging could fix, while free-tier
*hosted-API* compute (Agnes, Magic Hour) failed or succeeded on each
provider's own account/capacity limits - a meaningfully different failure
mode, and the reason the second kind was worth retrying across multiple
routes/accounts while the first wasn't.

## Music candidate (pending)

`storyboard.json`'s `music` block (caption/bpm/instrumental/seed) was written
once and has not been iterated on, since ACE-Step only runs on a Kaggle GPU
(see `notebooks/ace_step_music.ipynb`) and that session was still queued at
the time of writing. Once candidates come back: this section should record
which of the `NUM_CANDIDATES` was picked and why (the no-GPU placeholder pad
in current use is a quiet two-tone texture, not a real score, and isn't a
candidate in this sense).
