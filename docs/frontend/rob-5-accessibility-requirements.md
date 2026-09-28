# ROB-5 accessibility and responsive acceptance criteria

## Keyboard and control semantics

- Every action uses a native interactive element. A pointer is not required for
  play, pause, replay, retry, or timeline seeking.
- Tab order follows the visual reading order: video, playback action, timeline,
  then secondary information. No positive `tabindex` values are used.
- All focusable elements show a high-contrast focus ring that is not clipped or
  covered by another element.
- The main playback control exposes `Play video`, `Pause video`, or `Replay video`
  as its accessible name and is at least 44 by 44 CSS pixels.
- The timeline is a native range input. Arrow keys seek in one-second increments;
  Page Up and Page Down use a larger browser-native step; Home and End reach the
  start and end. Its accessible value text includes current time and nearest
  semantic-similarity score.
- Keyboard seeking never starts playback implicitly.

## Media behavior

- Video never autoplays. The initial state is click-to-play with `preload="metadata"`.
- Native video controls remain available as a fallback. Custom actions must not
  remove browser access to volume, fullscreen, playback position, or captions.
- When a caption track exists, the browser can expose it. The fixture preview may
  state that captions are unavailable; it must not show an empty caption control
  that appears functional.
- Loading and playback errors are announced through a polite status region.
  Repeated `timeupdate` events are not announced live.

## Score semantics

- The numeric value is always adjacent to the text `Semantic similarity` and the
  maximum value `/ 100`.
- Low, medium, and high display ranges use text labels, boundary values, and
  position in addition to color. Green is described as lower similarity, never
  as safe.
- The active timeline sample has a visible marker and a text value. Hover is not
  the only way to access a score.
- The explanatory note states that the score is prompt similarity and is not a
  verified safety decision.
- Chart decoration is hidden from assistive technology. A concise accessible
  summary names the number of samples, current value, sampled timestamp, and
  overall score range.

## Visual requirements

- Normal text meets at least 4.5:1 contrast; large text and meaningful graphical
  controls meet at least 3:1 against adjacent colors.
- Focus indicators meet 3:1 contrast and remain visible in high-score red/amber
  areas.
- Body copy is at least 16 CSS pixels with a line height of at least 1.5. Compact
  metadata may use 13–14 CSS pixels when it remains secondary and meets contrast.
- Pointer targets are at least 44 by 44 CSS pixels with at least 8 CSS pixels of
  separation where controls sit beside each other.
- The interface does not disable browser zoom.

## Motion

- Playback is the only continuous motion required by the task.
- UI transitions are limited to color, opacity, and small transforms lasting no
  more than 200 ms.
- Under `prefers-reduced-motion: reduce`, nonessential transitions are removed and
  all content renders in its final state. Timeline movement follows playback but
  does not animate independently.

## Responsive checks

Manually inspect these CSS viewport widths:

| Width | Expected result |
| --- | --- |
| 375 px | One column; no horizontal page scroll; controls remain 44 px; labels do not truncate essential meaning. |
| 768 px | One column with comfortable page gutters; video keeps its aspect ratio; metadata may use two columns. |
| 1024 px | Video and summary use two columns; the timeline keeps enough width for useful seeking. |
| 1440 px | Content is width-limited; line lengths and video size remain comfortable instead of stretching edge to edge. |

At every width, the page must preserve document zoom, avoid fixed card heights,
wrap long filenames and preset labels, and keep focused controls at least partly
visible under any sticky header.

## Manual acceptance checklist

- [ ] Complete every action with Tab, Shift+Tab, Enter/Space, and arrow keys.
- [ ] Verify visible focus on every action and the timeline.
- [ ] Confirm play/pause/replay names track the real video state.
- [ ] Confirm the timeline's value text reports time and semantic similarity.
- [ ] Confirm score meaning remains clear in grayscale and with color disabled.
- [ ] Confirm no autoplay and no unexpected motion with reduced motion enabled.
- [ ] Confirm loading and media errors are announced once without focus theft.
- [ ] Check 375, 768, 1024, and 1440 px widths with 200% browser zoom.
- [ ] Confirm there is no horizontal page scroll and the video aspect ratio holds.
