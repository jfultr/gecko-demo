# ROB-5 video review UI requirements

## Purpose

The screen lets an operator review one processed video and understand how the
returned semantic-similarity score changes over time. The score is supporting
evidence for review. It is not a probability, a certified risk measurement, or
an automated safety verdict.

## Information hierarchy

1. **Video and playback context.** The video is the largest element. Its title,
   current time, total duration, and playback state stay close to the media.
2. **Current semantic similarity.** Show the numeric value, the label
   `Semantic similarity`, and a short explanation together. Do not use the word
   `risk` as the primary label for the value.
3. **Score timeline.** Place the timeline immediately below the video so its
   playhead reads as an extension of the media controls.
4. **Analysis context.** Show the active preset and the `0–100` score range in a
   compact secondary panel. Prompt-level detail and peak evidence belong to
   ROB-6.

## Layout

Desktop widths use a two-column review surface. The video and timeline occupy
the flexible main column. A narrow summary column contains the current score,
scale, filename, resolution, duration, and preset. The page header contains the
product name, the `Video review` context label, and a fixture/demo indicator.

At widths below 900 CSS pixels, the summary moves below the video. At 600 CSS
pixels and below, page padding and card padding decrease, metadata wraps into a
single column, and all controls remain at least 44 CSS pixels tall. The video
keeps its source aspect ratio at every width. The page must never require
horizontal scrolling at 375 CSS pixels.

```text
┌──────────────────────────────────────────────────────────────┐
│ Gecko Vision · Video review                    Fixture data  │
├───────────────────────────────────┬──────────────────────────┤
│                                   │ Semantic similarity      │
│             VIDEO                 │ 82 / 100 · High          │
│                                   │ descriptive note         │
├───────────────────────────────────┤                          │
│ play  00:20 / 01:00               │ video + preset metadata  │
│ SCORE TIMELINE + PLAYHEAD          │                          │
└───────────────────────────────────┴──────────────────────────┘
```

## Visual direction

- Use a quiet, high-integrity dark interface suited to video inspection. The
  content should feel technical and precise without looking like a monitoring
  wall.
- Use a neutral near-black canvas, elevated slate panels, high-contrast off-white
  text, and restrained blue for interactive focus. Amber and red may mark higher
  score regions, but text and position must repeat the meaning.
- Use a legible sans-serif for interface copy and tabular numerals for time and
  scores. Avoid decorative display type, glass effects, heavy gradients, and
  ornamental animation.
- Use thin separators, 12–16 px radii, and a consistent 8 px spacing rhythm.
  Hover and focus transitions should be subtle and complete within 150–200 ms.

## Score language and encoding

The current value is displayed as `Semantic similarity: {score} / 100`. A
secondary category label may use the manifest vocabulary `Low`, `Medium`, or
`High`, with the clarification `display range`. The interface includes the note:

> Similarity indicates how closely a frame matches the configured prompts. It is
> not a verified safety decision.

The score timeline uses height and a printed value at the active sample in
addition to hue. Low, medium, and high ranges have visible labels or boundary
ticks. Green must not imply that a scene is safe.

## Screen states

- **Loading:** reserve the final video and timeline geometry, show concise status
  text, and avoid layout shifts.
- **Empty:** explain that no score samples were returned; keep video playback
  available when a source exists.
- **Media unavailable:** keep fixture metadata and the score timeline visible,
  replace the video with a clear local-preview message, and expose a retry action
  only when retrying can help.
- **Unsupported manifest:** stop rendering analysis data and name the unsupported
  schema version.

## Deferred decisions

- Peak navigation and evidence cards are owned by ROB-6.
- Upload and processing progress are owned by ROB-4.
- Captions are shown when a track exists. Caption generation is outside ROB-5.
- The backend remains authoritative for score samples and display levels; the
  frontend does not recompute analysis results.
