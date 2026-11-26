# Failures

Real errors hit against the live APIs and tools used by this project, in the
order they were found, with root cause and fix. Evidence for the API-side
ones is in `runs.jsonl` (`status: "error"` entries); this file is the
narrative version of that log.

## Gemini (narration)

- **Wrong API surface assumed.** The code was first written against the
  documented `generateContent` request/response shape. The real, live
  endpoint is the Interactions API (`POST /v1beta/interactions`, model in the
  body not the URL, `Api-Revision: 2026-05-20` header), whose response
  `steps[]` mixes `"thought"` and `"model_output"` entries. Fixed in
  `pipeline/gemini.py` after confirming the real shape against the live API.
- **Nonexistent model ids.** `gemini-3.7-flash` and `gemini-3.8-flash-lite`
  were both guessed and both don't exist; the API's own error pointed at the
  real ids (`gemini-3.6-flash`, `gemini-3.1-flash-lite`). Fixed in
  `config.py`.
- **Sustained 503 on the primary text model.** `gemini-3.8-flash` returned
  "currently experiencing high demand" for three retry attempts in a row
  during testing. `call_with_model_fallback` originally only fell through to
  the next model on a 404 (`ModelUnavailableError`); broadened to fall
  through on any non-fatal `HttpCallError`, since a persistent 503 is just as
  unusable as a missing model for this run.
- **TTS style instruction read aloud.** `storyboard.json`'s
  `narration.tts_style` field (e.g. "calm, warm, slow") was first sent as a
  spoken prefix ("Say calmly and slowly: ..."), which the model read aloud as
  literal content instead of following as a style cue. Two other channels
  were tried and both rejected: `system_instruction` ("Developer instruction
  is not enabled for this model"), and a guessed `style_instructions` field
  in `speech_config` (400, unknown parameter). No working non-spoken
  instruction channel was found for this API; fixed by sending only the raw
  narration text (`narration._tts_input`), keeping `tts_style` in
  `storyboard.json` as documented intent for a human (or a future provider)
  rather than something sent to this API.
- **Free-tier TTS quota: 10 requests/day per model, per Google account.**
  Confirmed live via a 429 naming the exact limit. Confirmed it's tied to the
  account/project, not the API key, by testing a new key from the same
  account (still blocked, same countdown) and then a key from a genuinely
  different account (worked). This is why some shots in the current
  narration pass used the lite fallback model rather than the primary - see
  EXPERIMENTS.md.
- **26 stale-key 401s in `runs.jsonl`'s smoke history.** Artifacts of testing
  successive `.env` key rotations during the quota investigation above, not
  a code bug - left in the log rather than scrubbed, since `runs.jsonl` is
  meant to be a complete record.

## Cloudflare Workers AI (reference images, keyframes)

- **`flux-1-schnell` rejects a `seed` parameter.** 400: "Additional or
  unevaluated properties '/seed' at '/' not allowed" - its schema is strict
  and documents exactly what it accepts. Fixed by dropping `seed` entirely
  and using a local "variant" label (never sent to the API) purely to keep
  cache keys distinct across candidates.
- **Output is JPEG, not PNG.** Despite initial assumption, every image
  response from this provider is JPEG bytes. Files and the `reference_image`
  path were renamed `.jpg` throughout.
- **Wrong model slug.** `"flux-2-klein"` 400s ("No route for that URI") - the
  real slug is `"flux-2-klein-4b"`. Cloudflare's own docs don't list this
  model's slug or its multipart body fields at all; confirmed by testing
  directly against the live endpoint.
- **Reference-image conditioning silently does nothing.** Uploading the
  golden reference via a guessed `image` multipart field, and separately a
  guessed `strength` field, both returned 200 OK - but the output ignored
  them completely both times (wrong ethnicity, wrong clothing, wrong art
  style, unrelated setting). Unlike `flux-1-schnell`'s strict schema (extra
  fields 400), this endpoint appears to silently drop unrecognised fields
  rather than use or reject them. Concluded real reference-image conditioning
  isn't available through this endpoint as used, and pivoted to text-only
  character consistency (see EXPERIMENTS.md) - the brief's own anticipated
  fallback for exactly this situation.

## Pacing (radio cut, then assemble - same root cause twice)

`timing.json`'s `effective_duration_s` pads a shot to at least its
storyboard-era planned `duration_s`, written before any narration existed.
When the narration finishes well before that (common - several shots' actual
read time is 2-3s under the plan), holding the shot open for the full planned
length leaves a silent-but-for-music gap. This was caught by ear twice,
independently, in two different places that both initially used
`effective_duration_s` for pacing:
- **Radio cut** - long gaps between lines on first listen; fixed by pacing on
  `narration_duration_s + 0.4s` (`radio.GAP_S`) instead.
- **Assemble** - same symptom, same fix, once there was a full assembled cut
  to listen to (`assemble.SHOT_PAD_S`). Confirmed fixed afterward with
  `ffmpeg`'s `silencedetect`: zero gaps ≥1s in the final mix other than the
  end card.

## assemble.py build issues (found while first building the stage, not live-API issues)

- **MP4 can't contain `pcm_s16le` audio.** First per-shot segment encode used
  `pcm_s16le` for the narration track (matching the source WAVs exactly);
  ffmpeg refused to mux it into an `.mp4` container ("codec not currently
  supported"). Fixed by encoding segment audio as AAC instead.
- **Crop filter sizing bug.** The 9:16 export path first scaled the square
  master to `{width}x{width}` (1080x1080) and then tried to crop it to
  `1080x1920` - cropping to a size larger than the input, which ffmpeg
  correctly refused ("Invalid too big or non positive size"). Fixed by
  scaling to `max(width, height)` on both sides first, then centre-cropping
  down to the target size.
- **Subtitles overflowing the frame in the 9:16 export.** The generated ASS
  track's `WrapStyle: 2` ("no word wrap, `\N` breaks only") meant a subtitle
  line too wide for the 1080px-wide portrait canvas wasn't wrapped - it was
  cut off at both edges instead, found by extracting and looking at an actual
  frame. Fixed to `WrapStyle: 0` (automatic wrapping within the style's
  margins); re-verified by extracting the same frame again.

## Project file hygiene (not API/model issues)

- **Markdown code fences left in `storyboard.json`.** A manual edit left
  literal ` ```json ` / ` ``` ` lines wrapping the file, making it invalid
  JSON. Fixed with `sed -i '1d;$d'`.
- **`.gitignore` only excluded one directory level.** `outputs/*` +
  `!outputs/*/` + `!outputs/*/.gitkeep` let nested files (e.g.
  `outputs/narration/*.wav`) show as untracked instead of ignored. Fixed to
  `outputs/**` + `!outputs/**/.gitkeep`.
- **Orphaned keyframe files.** Content-addressed caching means every prompt
  change creates a new file rather than replacing the old one by design - but
  this meant `outputs/keyframes/` accumulated roughly 20 files for 12 shots
  after several rounds of character-description edits. Not itself a bug, but
  needed a one-off manual cleanup before each full regeneration pass to keep
  the directory legible.

## Kaggle (Wan 2.2 / ACE-Step GPU stages)

- **Both notebooks stuck at "Queued" for 10+, then 16+, hours with a GPU
  attached.** Not a code issue - Kaggle's batch "Save Version" commit queue,
  most likely caused by the account's weekly GPU quota being exhausted (or
  platform-wide demand). Recommended fix: check the quota at
  kaggle.com/settings, and run the notebook interactively (editor session)
  rather than as a queued commit, which gets a GPU immediately if quota is
  available.
- **DNS resolution failures inside `wan_shots.ipynb`** (`git clone` and the
  Kaggle Secrets lookup both failed with "Temporary failure in name
  resolution"). Initially suspected the notebook's Internet toggle being off;
  a screenshot of the Settings menu showed internet was already enabled
  ("Turn off internet" is the toggle's label when it's currently *on*), so
  that wasn't actually the cause. Not fully diagnosed - plausibly the same
  underlying session/quota problem as the queueing above (a session that
  never actually reached a running state wouldn't have network either), but
  this hasn't been confirmed against a session that got far enough to prove
  it one way or the other.
