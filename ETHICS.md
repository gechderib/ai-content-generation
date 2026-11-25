# Ethics

## Consent for likeness and voice

| Person | Role in the film | Appears as | Consent |
|---|---|---|---|
| The filmmaker's mother | "the mother" character | Anonymized/stylized illustration, shown only from behind, in silhouette, or as hands/gestures - no face, no literal photo likeness used as model input | **Given.** Confirmed 2026-11-25 by the filmmaker that she knows about the project and consents to this stylized, non-identifying depiction in a short film that will be posted publicly with an AI-content label. |
| The filmmaker (as a child) | "the boy" character | Anonymized/stylized illustration, shown mostly from behind or at a distance, no detailed face - described in words (approximate age, skin tone, hair, clothing), not generated from an actual childhood or current photo | Self (the filmmaker is both the subject and the one directing the project). |
| The shop owner | "the shop owner" character | Fully fictionalized/composite character, not based on a specific real person, shown only as a silhouette or hands | N/A - not a real identifiable person. |

Two real reference photographs (an adult photo of the filmmaker, and a photo of his mother) were shared during development to ground the characters' general appearance (skin tone, build, clothing style) and to confirm the setting. **Neither photo was sent to any image-generation API or otherwise used as direct model input** - the free tools in this pipeline (Cloudflare Workers AI's FLUX models) are plain text-to-image / style-reference generators, not identity-preserving face tools, and using a real, identifiable third party's photo that way without her own informed consent for that specific technical use would not be appropriate. Character descriptions in `storyboard.json` are written in words only, and both characters keep the no-detailed-face, mostly-from-behind/silhouette framing throughout, independent of the consent above - this was the design from the start, not a workaround.

TODO before final submission: record the date/medium of the mother's consent in more detail (e.g. a short note on how it was confirmed - in person, a message, etc.) if the assignment's grading wants more than a developer's log entry here.

## Labelling

- The platform's AI-content disclosure will be switched on when the film is posted (TikTok/YouTube/Meta all support this).
- The end card ("Made with AI") is a required deliverable of the film itself (see `storyboard.json`'s `end_card`).
- Provenance metadata/watermarks (SynthID, C2PA) from any generating model are left intact in exported files, not stripped.

## Licences

| Model | Provider | Licence / terms (as found) |
|---|---|---|
| Gemini 3.8 Flash / Flash-lite / 3.6 Flash | Google (Gemini API) | Google's API terms of service; free tier, no redistribution of the API itself. Generated text/output ownership per Google's Gemini API additional terms (not independently re-verified here - check the current terms page before relying on this for submission). |
| Gemini 3.8 Flash TTS / Flash-lite TTS | Google (Gemini API) | Same as above; generated audio output. |
| FLUX.1 schnell | Black Forest Labs, via Cloudflare Workers AI | Apache 2.0 (per Black Forest Labs' own release). |
| FLUX.2 klein (4B) | Black Forest Labs, via Cloudflare Workers AI | Apache 2.0 (4B variant); the 9B variant is non-commercial - only the 4B is used here. |
| Wan 2.2 TI2V-5B | Wan-Video / Alibaba, via Kaggle | Apache 2.0 (per the official GitHub repo). |
| ACE-Step 1.5 | ACE-Step, via Kaggle | MIT (confirmed directly from the repo's licence file). Training-data provenance (licensed/royalty-free/synthetic) is claimed by the project but not independently re-verified here - mark as unverified if asked. |

## Style

Prompts describe qualities (warm, hand-painted, golden light, Ethiopian highland town) rather than naming a living artist, by design - see `storyboard.json`'s `style_block`.

## Private data

Real family details (names, exact addresses, the mother's actual photograph) are kept out of any prompt sent to a free hosted endpoint, since those endpoints may use submitted data for training. Only the two reference photographs mentioned above were ever present locally; they were not uploaded to Gemini, Cloudflare, or any other API.
