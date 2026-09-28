# ROB-5 fixture-driven player behavior

## Source contract

The player accepts a `VideoManifest` with `schema_version: "1.0"`. The checked-in
`fixtures/manifest.v1.json` is the reference input. The frontend treats
`video.source_url`, sample timestamps, sample scores, score range, and preset as
server-owned data. It does not infer timestamps from array indexes or recalculate
peaks and display buckets.

Before rendering, the client verifies that the schema version is supported, the
video duration is positive, the score range is `[0, 100]`, and every sample has a
finite timestamp and score inside the documented ranges. Samples are ordered by
timestamp for rendering while preserving their returned values.

## Playback synchronization

The HTML video element is the playback clock. Its `currentTime` is copied into
React state on `timeupdate`, seeking, loaded-metadata, play, pause, and ended
events. The UI never advances a separate timer.

- Play and pause update the visible control label and `aria-pressed` state.
- Seeking through the score timeline sets `video.currentTime` and the visible
  current time. Seeking does not start paused media.
- Native video seeking and keyboard seeking update the score playhead and current
  score in the same way as timeline scrubbing.
- When media duration differs from `manifest.video.duration_seconds`, the
  manifest duration remains the score-axis domain and the video element remains
  authoritative for playback bounds. Show a development warning, not a new user
  state.
- At `ended`, the playhead stays at the final time and the action becomes Replay.

## Active sample rule

At time `t`, the active sample is the sample whose timestamp is nearest to `t`.
If two samples are equally near, choose the earlier sample. This provides stable,
deterministic behavior between sparse measurements without inventing interpolated
model output.

Before the first sample, use the first sample. After the last sample, use the last
sample. With no samples, show `No score available`, omit the numeric score and
render an empty timeline. A single sample fills the whole timeline domain as one
known observation and remains active for all playback times.

The current display reads:

```text
Semantic similarity
82 / 100
sampled at 00:20
```

The sample timestamp is always visible so users can distinguish a sampled value
from a continuously measured signal.

## Timeline behavior

The horizontal axis runs from `0` to `manifest.video.duration_seconds`. Each
sample is positioned from its explicit `timestamp_seconds`. Its score is encoded
by vertical position or bar height and repeated in the active-value text. The
timeline includes labeled low, medium, and high display ranges and a distinct
playhead.

The timeline is a native range input layered over a visual chart. Pointer drag,
arrow keys, Home, and End all use native range behavior. Its accessible value text
contains formatted time and the nearest semantic-similarity score. Tooltips are
supplementary and never contain the only copy of a value.

## Loading and failure behavior

1. Load and validate the fixture/manifest.
2. Render metadata and timeline geometry.
3. Load video metadata without autoplay.
4. Enable playback actions after the browser reports that media can be played.

While the manifest is loading, reserve the final layout and label the region
`Loading analysis`. While media is loading, keep timeline data visible and disable
playback actions with `Loading video` status.

If the media URL fails, show `Preview video unavailable` in the video frame and
retain all valid analysis data. A Retry action reloads the same source. If the
manifest fails validation or uses another schema version, show an analysis error
and do not partially render its scores.

## Explicit non-goals

- Upload, queue, processing, and failed-job states belong to ROB-4.
- Peak selection, evidence frames, and peak-to-player navigation belong to ROB-6.
- The frontend does not interpolate model scores, derive safety decisions, or
  convert semantic similarity into probability.
