import { useState } from 'react'
import { ArrowUpRight } from 'lucide-react'
import { formatTime } from './format'
import { resolveEvidenceMedia } from './manifest'
import type { VideoManifest } from './types'

type PeakEvent = VideoManifest['peaks'][number]

function EvidenceFrame({ peak, isFixture }: { peak: PeakEvent; isFixture: boolean }) {
  const [failed, setFailed] = useState(false)
  return (
    <span className="peak-evidence">
      {failed ? (
        <span className="peak-evidence-fallback">Frame unavailable</span>
      ) : (
        <img
          src={resolveEvidenceMedia(peak.frame.image_url, isFixture)}
          alt=""
          loading="lazy"
          onError={() => setFailed(true)}
        />
      )}
    </span>
  )
}

export function PeakNavigator({
  peaks,
  presetLabel,
  isFixture,
  currentTime,
  canSeek,
  onSeek,
}: {
  peaks: PeakEvent[]
  presetLabel: string
  isFixture: boolean
  currentTime: number
  canSeek: boolean
  onSeek: (time: number) => void
}) {
  const rankedPeaks = [...peaks].sort(
    (a, b) => b.score - a.score || a.timestamp_seconds - b.timestamp_seconds,
  )

  return (
    <section className="peaks-section" aria-labelledby="peaks-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Review points</span>
          <h2 id="peaks-title">Peak events</h2>
        </div>
        <span className="peaks-count">{rankedPeaks.length} {rankedPeaks.length === 1 ? 'event' : 'events'}{rankedPeaks.length > 0 ? ' · highest match first' : ''}</span>
      </div>
      {rankedPeaks.length === 0 ? (
        <div className="peaks-empty">
          <strong>No peak events in this analysis</strong>
          <p>The processor found no local peaks to review. Inspect individual observations in the similarity timeline above.</p>
        </div>
      ) : (
        <ol className="peak-list">
          {rankedPeaks.map((peak, index) => {
            const isCurrent = Math.abs(currentTime - peak.timestamp_seconds) < 0.5
            return (
              <li key={peak.event_id}>
                <button
                  className={`peak-button${isCurrent ? ' is-current' : ''}`}
                  type="button"
                  onClick={() => onSeek(peak.timestamp_seconds)}
                  disabled={!canSeek}
                  aria-current={isCurrent ? 'true' : undefined}
                >
                  <EvidenceFrame peak={peak} isFixture={isFixture} />
                  <span className="peak-description">
                    <span className="peak-meta">Event {String(index + 1).padStart(2, '0')} · {formatTime(peak.timestamp_seconds)}</span>
                    <strong>{peak.prompt}</strong>
                    <span>Preset: {presetLabel}</span>
                  </span>
                  <span className="peak-metric">
                    <strong>{Math.round(peak.score)}<small>/100</small></strong>
                    <span>{peak.level} match</span>
                  </span>
                  <span className="sr-only">Seek video to this event. Semantic similarity score, not a verified safety decision.</span>
                  <ArrowUpRight size={17} aria-hidden="true" />
                </button>
              </li>
            )
          })}
        </ol>
      )}
      <p className="peaks-note">Scores describe semantic similarity to the configured prompts. They are not verified safety decisions.</p>
    </section>
  )
}
