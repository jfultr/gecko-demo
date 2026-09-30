import { ArrowUpRight } from 'lucide-react'
import { formatTime } from './format'
import type { VideoManifest } from './types'

type PeakEvent = VideoManifest['peaks'][number]

export function PeakNavigator({
  peaks,
  currentTime,
  canSeek,
  onSeek,
}: {
  peaks: PeakEvent[]
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
        <span className="peaks-count">{rankedPeaks.length} events · highest match first</span>
      </div>
      {rankedPeaks.length > 0 && (
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
                  aria-label={`Peak ${index + 1}, ${formatTime(peak.timestamp_seconds)}, semantic similarity ${Math.round(peak.score)} out of 100. Seek video`}
                >
                  <span className="peak-rank">{String(index + 1).padStart(2, '0')}</span>
                  <span className="peak-time">{formatTime(peak.timestamp_seconds)}</span>
                  <span className="peak-level">{peak.level} match</span>
                  <span className="peak-score">{Math.round(peak.score)}<small>/100</small></span>
                  <ArrowUpRight size={17} aria-hidden="true" />
                </button>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
