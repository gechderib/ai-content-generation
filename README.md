# The Starting Price

A 60-90 second AI-generated short film: a boy is embarrassed when his mother
haggles down the price of a pair of jeans in a small Ethiopian town - and
learns, by the end, that there was nothing to be embarrassed about. Narrated
in Amharic with English subtitles, set in Debre Tabor, South Gondar.

Made for the IoAcademy "AI-Content Generation: Heritage Short" challenge.

## Quickstart

```
make install   # creates venv/, installs requirements.txt
make film      # full no-GPU pipeline: storyboard -> narration -> keyframes
               # -> Ken Burns clips -> placeholder score -> final cut
```

Output lands at `outputs/final/9x16.mp4` (portrait) and `outputs/final/16x9.mp4`
(landscape). `make film` needs API keys in `.env` first (see below) - it is
not a from-scratch-with-no-credentials command, since narration and keyframes
call real model APIs.

`make test` runs the test suite (pytest, no network calls - everything that
touches a real API is mocked).

## .env

```
GEMINI_API_KEY=...      # narration (TTS) and any future text calls
CF_ACCOUNT_ID=...       # keyframes, reference (Cloudflare Workers AI)
CF_API_TOKEN=...
HF_TOKEN=...            # only needed inside the Kaggle Wan 2.2 notebook
KAGGLE_USERNAME=...     # only if driving Kaggle via its API/CLI
KAGGLE_KEY=...
```

## Pipeline stages

Single source of truth: `storyboard.json`, validated against
`schema/storyboard.schema.json`. Each stage reads it (and, from `narration`
onward, `outputs/timing.json`) and writes content-addressed files under
`outputs/<stage>/` - re-running a stage with unchanged inputs is a no-op, and
changing one shot only invalidates that shot's cached files. Every model/GPU
call is appended to `runs.jsonl` (see ARCHITECTURE.md).

```
python -m pipeline validate              # schema + cross-field checks
python -m pipeline smoke                 # confirm each provider is reachable
python -m pipeline narration             # Amharic TTS per shot; writes outputs/timing.json
python -m pipeline radio                 # narration-only "radio cut" prototype (no visuals)
python -m pipeline reference             # 4 character-sheet candidates
python -m pipeline reference --pick N    # choose candidate N as the golden reference
python -m pipeline keyframes             # one keyframe image per shot
python -m pipeline shots --fallback      # Ken Burns clip per shot (no GPU)
python -m pipeline shots --import-dir D  # ingest real Wan 2.2 clips (Kaggle/Colab) or Agnes AI clips
python -m pipeline music --fallback      # placeholder score bed (no GPU)
python -m pipeline music --import-dir D  # ingest real ACE-Step candidates (Kaggle/Colab)
python -m pipeline agnes                 # hosted image-to-video (Agnes AI); writes outputs/agnes/
python -m pipeline agnes --shot sNN      # just one shot
python -m pipeline assemble              # final cut, both aspect ratios
```

`--shot sNN` limits `narration`/`keyframes`/`shots` to one shot; `--force`
ignores the cache and regenerates.

## Upgrading to real motion and music

The no-GPU path (`--fallback`) is what makes `make film` work without a GPU
session at all - a pan/zoom over each keyframe, and a quiet placeholder pad
under the narration.

**Real Wan 2.2 motion via a free-tier GPU is a confirmed dead end** - tested
exhaustively on both Kaggle and Colab's free 16GB T4s, every dependency bug
fixed, every available `--size`/`--frame_num` setting tried down to the
practical floor, every single shot still OOM-killed. Wan2.2 TI2V-5B's own
README states it needs >=24GB VRAM; a free T4 genuinely cannot run it. See
FAILURES.md for the full trail before spending time on this path again - it
would need a GPU with >=24GB VRAM (a paid Colab A100 session, or a rented
24GB+ GPU on RunPod/Vast.ai).

Two routes that don't need a local/rented GPU at all:

- **`python -m pipeline agnes`** - hosted image-to-video via Agnes AI
  (`agnes-video-2.5-flash`, free during its current trial promotion). Needs
  `AGNES_API_KEY` plus `CLOUDINARY_CLOUD_NAME`/`CLOUDINARY_UPLOAD_PRESET` in
  `.env` (Cloudinary unsigned-upload hosts each keyframe publicly, since
  Agnes requires a public image URL - see `pipeline/agnes.py`'s docstring and
  FAILURES.md for why that specific combination). Writes directly to
  `outputs/agnes/` in the same shape `shots --import-dir` expects - run that
  next. Was hitting a persistent free-tier queue-full error as of this
  writing; worth retrying later or at a less busy time.
- **Magic Hour** (tried first, not currently wired into the CLI) - real
  working image-to-video via its hosted `wan-2.2`, but the account used here
  ran out of starter credits after 3 shots and its output carries a
  watermark on the free tier. 3 real clips exist in `outputs/magichour/`.

For ACE-Step music specifically, the Kaggle/Colab GPU notebooks
(`notebooks/ace_step_music.ipynb` / `notebooks/ace_step_music_colab.ipynb`)
are still the documented path - that one hasn't hit the same VRAM wall.

Either way:

1. Zip `storyboard.json` + `outputs/timing.json` + `outputs/keyframes/`
   (Colab: upload that zip directly in the notebook's upload cell; Kaggle:
   upload it as a Kaggle Dataset first, then attach it to the notebook).
2. Run the Wan 2.2 notebook (image-to-video, needs a GPU) and the ACE-Step
   notebook (music, needs a GPU) - see the markdown cell at the top of each
   for exact setup.
3. Download each notebook's output zip, unzip locally, then:
   ```
   python -m pipeline shots --import-dir path/to/unzipped/clips
   python -m pipeline music --import-dir path/to/unzipped/music
   python -m pipeline assemble --force
   ```
`assemble` always picks the most-recently-modified clip/score per shot, so
this transparently replaces the fallback material with no code changes.

## Documentation

- `DESIGN.md` - the creative brief: story, visual style, character sheet, why Debre Tabor
- `ARCHITECTURE.md` - how the pipeline is built: contracts, caching, retries, assemble's filter graph
- `EXPERIMENTS.md` - what was tried, what was picked, and why
- `FAILURES.md` - real errors hit against the live APIs/tools, and their fixes
- `COSTS.md` - what every stage actually cost (spoiler: $0 so far, free tiers only)
- `ETHICS.md` - consent record for the real people referenced by this film
