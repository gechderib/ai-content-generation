# Measurement

Quantitative read of this project's own `runs.jsonl` audit log - every number
below is counted directly from the 348 logged calls, not estimated. Companion
to `COSTS.md` (cost framing) and `FAILURES.md` (narrative of what broke and
why); this file is the aggregate numbers underneath both.

## Per-stage reliability and latency

| stage | calls | ok | error | success rate | avg latency | median latency | max latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| smoke | 218 | 163 | 55 | 74.8% | 517 ms | 0 ms | 27.1 s |
| narration | 48 | 44 | 4 | 91.7% | 9.6 s | 4.8 s | 67.4 s |
| reference | 21 | 20 | 1 | 95.2% | 3.8 s | 2.8 s | 9.7 s |
| keyframes | 36 | 36 | 0 | 100% | 11.1 s | 10.5 s | 21.6 s |
| shots | 24 | 24 | 0 | 100% | - (ffmpeg local / imported clip) | - | - |
| music | 1 | 1 | 0 | 100% | - (ffmpeg local) | - | - |

`smoke`'s 74.8% is the outlier, and it's not a production reliability number:
`smoke` is the connectivity-check command re-run by hand every time a `.env`
key was rotated, a new model name was tried, or a quota was being probed
during development (see `FAILURES.md`) - its 55 errors are development
history, not 55 failed attempts to make the film. `keyframes` and `shots`,
the stages that actually produced the delivered film's assets, are both
100% successful as logged.

## Retries and fallback actually firing (not just present in the code)

Two separate resilience mechanisms exist (`pipeline/http.py`'s
`request_with_retry` for transient HTTP errors, `pipeline/gemini.py`'s
`call_with_model_fallback` for exhausted/unavailable models), and both have
real, logged instances of firing rather than sitting unused:

**Retry-then-exhaust, logged verbatim:**
```
"error": "503 from https://generativelanguage.googleapis.com/v1beta/interactions
after 3 attempt(s): {\"error\":{\"message\":\"gemini-3.8-flash is currently
experiencing high demand...\"}}"
```
(`request_with_retry` retried 3 times with backoff before giving up and
logging the failure - this is what "after 3 attempt(s)" in the error string
records.)

**Model-fallback chain, logged verbatim:**
```
"error": "all models unavailable: ['gemini-3.8-flash-tts',
'gemini-3.8-flash-lite-tts']; last error: network error after 3 attempt(s): ..."
```
(both the primary and fallback TTS model were tried, each itself retried 3x,
before the call was logged as a failure - `narration`'s 4 real errors are all
this shape.)

Individual retry attempts inside a single logical call are not each written
as their own `runs.jsonl` row (only the final outcome is) - this is why the
table above shows 0 "multi-attempt" rows despite retries demonstrably
happening; the evidence for retries is the `after N attempt(s)` text baked
into the final error message by `request_with_retry` itself, shown above.

## Cost, by shot, for the one stage that wasn't free

Every other stage ran entirely on free tiers ($0, see `COSTS.md`). The one
real cost is the 12 real Wan 2.2 motion clips bought through Magic Hour's
hosted API, read from `gpu_log.json` and logged per-shot in `runs.jsonl`:

| shot | model | cost (USD) |
|---|---|---:|
| s01 | magichour/wan-2.2 | $0.1728 |
| s02 | magichour/wan-2.2 | $0.1728 |
| s03 | magichour/wan-2.2 | $0.1152 |
| s04 | magichour/wan-2.2 | $0.0864 |
| s05 | magichour/wan-2.2 | $0.1152 |
| s06 | magichour/wan-2.2 | $0.0864 |
| s07 | magichour/wan-2.2 | $0.1440 |
| s08 | magichour/wan-2.2 | $0.2304 |
| s09 | magichour/wan-2.2 | $0.2016 |
| s10 | magichour/wan-2.2 | $0.2592 |
| s11 | magichour/wan-2.2 | $0.0864 |
| s12 | magichour/wan-2.2 | $0.2304 |
| **total** | | **$1.9008** |

Average $0.158/shot; the spread (3-10s per clip, Magic Hour bills per
second) tracks each shot's `timing.json`-driven duration directly - the two
cheapest shots (s04, s06, s11 at $0.0864) are this film's shortest clips,
the three most expensive (s08, s10, s12 at >$0.20) its longest. $1.90 total
across 12 shots and 6 free-credit accounts (see `FAILURES.md`) is the real,
all-in cost of the only non-$0 stage in the pipeline.

## What this doesn't yet measure

- No end-to-end wall-clock time for a full `make film` run has been
  recorded (each stage's timing above is per-call, not per-stage-run).
- No measured-vs-target loudness pass on the final mix (noted already in
  `EXPERIMENTS.md` - single-pass `loudnorm`, not verified against the
  -14 LUFS target with a second measurement pass).
- No audience-facing metric (watch-through rate, comprehension, subtitle
  legibility) - see the user-testing note below/in `EXPERIMENTS.md`.
