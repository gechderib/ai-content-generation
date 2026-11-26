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
python -m pipeline shots --import-dir D  # ingest real Wan 2.2 clips from Kaggle
python -m pipeline music --fallback      # placeholder score bed (no GPU)
python -m pipeline music --import-dir D  # ingest real ACE-Step candidates from Kaggle
python -m pipeline assemble              # final cut, both aspect ratios
```

`--shot sNN` limits `narration`/`keyframes`/`shots` to one shot; `--force`
ignores the cache and regenerates.

## Upgrading to real motion and music

The no-GPU path (`--fallback`) is what makes `make film` work without a GPU
session at all - a pan/zoom over each keyframe, and a quiet placeholder pad
under the narration. For the real thing, two notebook pairs are provided -
pick one platform:

- **Google Colab** (`notebooks/wan_shots_colab.ipynb` /
  `notebooks/ace_step_music_colab.ipynb`) - upload the dataset zip directly in
  the notebook (a cell, no separate dataset step), `HF_TOKEN` goes in via
  Colab's own Secrets panel (key icon, left sidebar). This is the primary
  path - Kaggle's free GPU queue was unreliable in practice (see FAILURES.md).
- **Kaggle** (`notebooks/wan_shots.ipynb` / `notebooks/ace_step_music.ipynb`)
  - needs a Kaggle Dataset containing the same zip attached, and `HF_TOKEN` as
  a Kaggle Secret.

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
