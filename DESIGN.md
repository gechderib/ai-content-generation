# Design

## Story

A boy remembers, as a child, going with his mother to buy a pair of jeans in
a small Ethiopian boutique street. The owner names 2000 birr; his mother
counters at 300. The boy is mortified - he wants the ground to swallow him.
The owner refuses, she starts to walk out, the owner calls her back at 1000,
she still refuses, and turns back herself with a final offer of 500 - which
the owner accepts warmly, telling her she's now a regular customer. They buy
the jeans for 500. The narrator (the boy, as an adult) closes on the lesson:
being ashamed, and losing out because of it, isn't kindness - it's just a
loss. 12 shots, ~66s of content plus a 2.5s end card.

## Audience and intent

Young Ethiopians and diaspora friends, watching on phones (per
`storyboard.json`'s `audience`/`intent` fields) - the film should read as
specific and local, not as a generic "Africa" stock scene, and should land as
warm/funny rather than as a lecture about negotiation.

## Why Debre Tabor, South Gondar

The filmmaker is from Debre Tabor; the story is set there rather than in
Addis Ababa or an unspecified town so the street, the boutiques, and the
highland hills behind them are recognisable to someone who actually knows the
place - not "a generic African village," which `style_block` explicitly rules
out. Two real reference photos (the filmmaker as a child, and his mother)
were shared to ground the characters' look but were deliberately **not** fed
into any image-generation API - see ETHICS.md for why and how consent for
this was handled.

## Visual style

Warm, soft, hand-painted illustration with gentle film grain and nostalgic
golden-afternoon light - picked to feel like a remembered scene rather than a
documentary, and to sit comfortably alongside a children's-book-style
narration. Explicitly not photorealistic (`style_block`: "avoid
photorealism"), and explicitly not AI-generic: real local details (corrugated
roofing, hand-painted shop signage implied without rendering actual text,
clothes hanging at boutique entrances) carry the specificity the audience
should recognise.

## Character sheet

- **The boy**: ~8 years old, dark brown skin, short black coily hair, yellow
  t-shirt, faded blue full-length trousers (changed from shorts mid-project -
  trousers read as more period/place-accurate and avoid an unintentionally
  younger-reading silhouette). Shown from behind or at a distance - no
  detailed face, so the character reads as "a boy" rather than as a specific
  individual's likeness.
- **The mother**: traditional habesha kemis (white dress with a woven
  colourful border) and matching netela shawl - shown only from behind, in
  silhouette, or as hands.
- **The shop owner**: simple casual clothes (a plain short-sleeved shirt) -
  deliberately not a suit or waistcoat, which read as too formal for a small
  boutique owner and were corrected after an early keyframe pass over-dressed
  him.

All three are shown without a identifiable face (behind/silhouette/hands),
consistent with ETHICS.md's position that the boy and shop owner are
composite/fictionalised characters, not portraits of specific real people.

## Narration and subtitles

Amharic narration (voice "Charon," male), English `subtitle_en` burned in per
shot - the film is meant to be watched by Amharic speakers by ear and by
everyone else by the subtitles, not treated as a dubbed/translated version of
itself. `overlay_text` price captions (2000 ETB, 300 ETB, 1000 ETB, 500 ETB)
are a separate, distinctly-styled on-screen layer (bold, upper third) so the
negotiation's numbers land as a visual beat even for a viewer not reading
every subtitle line closely.

## Music

A gentle, warm acoustic score (soft plucked strings, light hand percussion,
80 BPM, instrumental, no lead melody) - meant to sit under the narration
without competing with it, which is also why `assemble.py` ducks it via
`sidechaincompress` rather than just mixing it at a fixed low volume.

## Aspect ratios

Exported both 9:16 (phones, the stated primary audience) and 16:9
(anywhere else it might be shown) from one shared square master - see
ARCHITECTURE.md for how.
