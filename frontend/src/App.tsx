import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Check,
  ChevronRight,
  Clock3,
  FileVideo2,
  Gauge,
  Pause,
  Play,
  RotateCcw,
  Sparkles,
} from 'lucide-react'
import { demoManifest, resolvePreviewMedia } from './manifest'
import { formatTime } from './format'
import { PeakNavigator } from './PeakNavigator'
import type { RiskSample, ScoreLevel } from './types'
import { ApiError, uploadVideo } from './api'
import type { UploadResponse } from './api'
import { UploadScreen } from './UploadScreen'
import { JobScreen } from './JobScreen'
import type { VideoManifest } from './types'

function nearestSample(samples: RiskSample[], currentTime: number) {
  return samples.reduce<RiskSample | undefined>((nearest, sample) => {
    if (!nearest) return sample
    const distance = Math.abs(sample.timestamp_seconds - currentTime)
    const nearestDistance = Math.abs(nearest.timestamp_seconds - currentTime)
    return distance < nearestDistance ? sample : nearest
  }, undefined)
}

function scoreLevel(score: number): ScoreLevel {
  if (score >= 75) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
}

function levelLabel(level: ScoreLevel) {
  return level === 'high' ? 'High match' : level === 'medium' ? 'Medium match' : 'Lower match'
}

function Timeline({
  samples,
  duration,
  currentTime,
  onSeek,
}: {
  samples: RiskSample[]
  duration: number
  currentTime: number
  onSeek: (nextTime: number) => void
}) {
  const activeSample = nearestSample(samples, currentTime)
  const width = 1000
  const height = 180
  const chartTop = 14
  const chartBottom = 148
  const chartHeight = chartBottom - chartTop
  const points = samples
    .map((sample) => {
      const x = (sample.timestamp_seconds / duration) * width
      const y = chartBottom - (sample.score / 100) * chartHeight
      return `${x},${y}`
    })
    .join(' ')
  const areaPoints = `0,${chartBottom} ${points} ${width},${chartBottom}`
  const playheadPosition = Math.min(100, Math.max(0, (currentTime / duration) * 100))

  return (
    <section className="timeline-section" aria-labelledby="timeline-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Temporal analysis</span>
          <h2 id="timeline-title">Similarity timeline</h2>
        </div>
        <div className="timeline-legend" aria-label="Display ranges">
          <span><i className="dot dot-low" />0–39 Lower</span>
          <span><i className="dot dot-medium" />40–74 Medium</span>
          <span><i className="dot dot-high" />75–100 High</span>
        </div>
      </div>

      <div className="chart-shell">
        <div className="range-labels" aria-hidden="true">
          <span>100</span>
          <span>75</span>
          <span>40</span>
          <span>0</span>
        </div>
        <div className="chart-area">
          <svg
            className="score-chart"
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="none"
            role="img"
            aria-label={`${samples.length} semantic similarity samples ranging from 0 to 100`}
          >
            <defs>
              <linearGradient id="scoreStroke" x1="0" x2="1">
                <stop offset="0" stopColor="#39d98a" />
                <stop offset="0.58" stopColor="#f2b84b" />
                <stop offset="1" stopColor="#ff635f" />
              </linearGradient>
              <linearGradient id="scoreFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor="#f2b84b" stopOpacity="0.24" />
                <stop offset="1" stopColor="#f2b84b" stopOpacity="0" />
              </linearGradient>
            </defs>
            {[0, 40, 75, 100].map((value) => {
              const y = chartBottom - (value / 100) * chartHeight
              return <line key={value} x1="0" x2={width} y1={y} y2={y} className="grid-line" />
            })}
            <polygon points={areaPoints} fill="url(#scoreFill)" />
            <polyline points={points} fill="none" stroke="url(#scoreStroke)" strokeWidth="4" vectorEffect="non-scaling-stroke" />
            {samples.map((sample) => (
              <circle
                key={sample.timestamp_seconds}
                cx={(sample.timestamp_seconds / duration) * width}
                cy={chartBottom - (sample.score / 100) * chartHeight}
                r={sample === activeSample ? 8 : 4.5}
                className={sample === activeSample ? 'sample-dot active' : 'sample-dot'}
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </svg>
          <div className="playhead" style={{ left: `${playheadPosition}%` }} aria-hidden="true">
            <span className="playhead-label">{formatTime(currentTime)}</span>
          </div>
          <input
            className="timeline-input"
            type="range"
            min="0"
            max={duration}
            step="0.1"
            value={Math.min(currentTime, duration)}
            onChange={(event) => onSeek(Number(event.target.value))}
            aria-label="Seek video by analysis timeline"
            aria-valuetext={`${formatTime(currentTime)}, semantic similarity ${Math.round(activeSample?.score ?? 0)} out of 100`}
          />
        </div>
      </div>
      <div className="time-axis" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((step) => <span key={step}>{formatTime((duration * step) / 4)}</span>)}
      </div>
    </section>
  )
}

function ScoreGauge({ score }: { score: number }) {
  const level = scoreLevel(score)
  return (
    <section className="score-card" aria-labelledby="score-title">
      <div className="score-heading">
        <span className="eyebrow">Current frame</span>
        <span className={`level-badge level-${level}`}><i />{levelLabel(level)}</span>
      </div>
      <div className="score-value-row">
        <div>
          <p id="score-title" className="score-label">Semantic similarity</p>
          <p className="score-value"><strong>{Math.round(score)}</strong><span>/100</span></p>
        </div>
        <Gauge size={32} strokeWidth={1.5} aria-hidden="true" />
      </div>
      <div className="thermometer" aria-hidden="true">
        <div className="thermometer-scale" />
        <div className="thermometer-marker" style={{ left: `calc(${score}% - 7px)` }} />
      </div>
      <div className="thermometer-labels" aria-hidden="true"><span>Lower</span><span>Medium</span><span>High</span></div>
      <p className="score-note">How closely this frame matches the configured prompts. This is not a verified safety decision.</p>
    </section>
  )
}

function ReviewScreen({ manifest, onBack, isFixture }: { manifest: VideoManifest; onBack: () => void; isFixture: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [mediaStatus, setMediaStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [reloadKey, setReloadKey] = useState(0)
  const activeSample = useMemo(
    () => nearestSample(manifest.samples, currentTime) ?? { timestamp_seconds: 0, score: 0 },
    [currentTime, manifest.samples],
  )

  async function togglePlayback() {
    const video = videoRef.current
    if (!video || mediaStatus !== 'ready') return
    if (video.ended) video.currentTime = 0
    if (video.paused) await video.play()
    else video.pause()
  }

  function seek(nextTime: number) {
    const clamped = Math.min(manifest.video.duration_seconds, Math.max(0, nextTime))
    if (videoRef.current && mediaStatus === 'ready') videoRef.current.currentTime = clamped
    setCurrentTime(clamped)
  }

  const playbackLabel = videoRef.current?.ended ? 'Replay video' : isPlaying ? 'Pause video' : 'Play video'

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Gecko Vision video review">
          <span className="brand-mark"><Activity size={19} aria-hidden="true" /></span>
          <span>Gecko<span>Vision</span></span>
        </a>
        <div className="context-path" aria-label="Current page"><span>Analysis</span><ChevronRight size={14} /><strong>Video review</strong></div>
        <button className="fixture-pill fixture-link" type="button" onClick={onBack}><Sparkles size={13} aria-hidden="true" /> New analysis</button>
      </header>

      <div className="page" id="top">
        <div className="page-heading">
          <div>
            <span className="eyebrow">Review session · {isFixture ? 'Fixture preview' : manifest.video.video_id.slice(0, 8)}</span>
            <h1>{isFixture ? 'Warehouse walkthrough' : manifest.video.filename}</h1>
            <p>Inspect semantic similarity across the processed video timeline.</p>
          </div>
          <div className="analysis-state"><span><Check size={13} /></span><div><strong>Analysis complete</strong><small>{manifest.samples.length} samples · v{manifest.schema_version}</small></div></div>
        </div>

        <div className="review-grid">
          <section className="player-card" aria-labelledby="player-title">
            <div className="card-topline">
              <div><FileVideo2 size={16} aria-hidden="true" /><span id="player-title">{manifest.video.filename}</span></div>
              <span>{manifest.video.width} × {manifest.video.height}</span>
            </div>
            <div className="video-stage">
              <video
                key={reloadKey}
                ref={videoRef}
                src={resolvePreviewMedia(manifest.video.source_url)}
                poster={isFixture ? '/demo/warehouse-poster.svg' : undefined}
                preload="metadata"
                controls
                onLoadedMetadata={() => setMediaStatus('ready')}
                onCanPlay={() => setMediaStatus('ready')}
                onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
                onSeeking={(event) => setCurrentTime(event.currentTarget.currentTime)}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                onEnded={() => setIsPlaying(false)}
                onError={() => setMediaStatus('error')}
                aria-label={`${manifest.video.filename} video preview`}
              />
              {mediaStatus === 'loading' && <div className="video-overlay" role="status"><span className="spinner" />Loading preview video…</div>}
              {mediaStatus === 'error' && (
                <div className="video-overlay video-error" role="status">
                  <AlertTriangle size={26} aria-hidden="true" />
                  <strong>Preview video unavailable</strong>
                  <span>Check the video source and try again.</span>
                  <button onClick={() => { setMediaStatus('loading'); setReloadKey((key) => key + 1) }}><RotateCcw size={15} />Reload media</button>
                </div>
              )}
              {isFixture && <div className="video-watermark" aria-hidden="true">Fixture preview</div>}
            </div>

            <div className="custom-controls">
              <button className="play-button" onClick={togglePlayback} disabled={mediaStatus !== 'ready'} aria-label={playbackLabel} aria-pressed={isPlaying}>
                {isPlaying ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
              </button>
              <div className="playback-time"><strong>{formatTime(currentTime)}</strong><span>/ {formatTime(manifest.video.duration_seconds)}</span></div>
              <div className="sample-chip"><span /> Sample {formatTime(activeSample.timestamp_seconds)} · {Math.round(activeSample.score)}</div>
            </div>
          </section>

          <aside className="inspector" aria-label="Analysis summary">
            <ScoreGauge score={activeSample.score} />
            <section className="details-card">
              <div className="section-heading compact"><div><span className="eyebrow">Analysis setup</span><h2>Review context</h2></div></div>
              <dl className="details-list">
                <div><dt><Clock3 size={15} />Duration</dt><dd>{formatTime(manifest.video.duration_seconds)}</dd></div>
                <div><dt><Activity size={15} />Samples</dt><dd>{manifest.samples.length} observations</dd></div>
                <div><dt><Sparkles size={15} />Preset</dt><dd>{manifest.preset.label}</dd></div>
              </dl>
              <div className="prompt-summary"><span>Positive prompts</span><strong>{manifest.preset.positive_prompts.length}</strong></div>
              <p className="prompt-preview">“{manifest.preset.positive_prompts[0]}”</p>
            </section>
          </aside>
        </div>

        <Timeline samples={manifest.samples} duration={manifest.video.duration_seconds} currentTime={currentTime} onSeek={seek} />
        <PeakNavigator peaks={manifest.peaks} currentTime={currentTime} canSeek={mediaStatus === 'ready'} onSeek={seek} />
        <footer><span>Generated {new Date(manifest.generated_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</span><span>Manifest {manifest.schema_version} · {manifest.samples.length} observations</span></footer>
      </div>
    </main>
  )
}

export default function App() {
  const [view, setView] = useState<'upload' | 'accepted' | 'review' | 'fixture'>('upload')
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)
  const [uploadError, setUploadError] = useState<ApiError | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [accepted, setAccepted] = useState<UploadResponse | null>(null)
  const [resultManifest, setResultManifest] = useState<VideoManifest | null>(null)
  const currentUpload = useRef<ReturnType<typeof uploadVideo> | null>(null)

  useEffect(() => () => currentUpload.current?.abort(), [])

  async function startUpload(file: File) {
    setUploadError(null)
    setAccepted(null)
    setUploadProgress(null)
    setIsUploading(true)
    const request = uploadVideo(file, setUploadProgress)
    currentUpload.current = request
    try {
      const result = await request.promise
      setAccepted(result)
      setView('accepted')
    } catch (error) {
      setUploadError(error instanceof ApiError ? error : new ApiError('The upload could not be completed.', 'UPLOAD_FAILED'))
    } finally {
      currentUpload.current = null
      setIsUploading(false)
    }
  }

  if (view === 'fixture') return <ReviewScreen manifest={demoManifest} isFixture onBack={() => setView('upload')} />
  if (view === 'review' && resultManifest) return <ReviewScreen manifest={resultManifest} isFixture={false} onBack={() => setView('upload')} />
  if (view === 'accepted' && accepted) {
    return <JobScreen accepted={accepted} onComplete={(manifest) => { setResultManifest(manifest); setView('review') }} onStartNew={() => setView('upload')} />
  }
  return <UploadScreen onSubmit={startUpload} onViewFixture={() => setView('fixture')} onSelectionChange={() => setUploadError(null)} disabled={isUploading} uploadProgress={uploadProgress} uploadError={uploadError} />
}
