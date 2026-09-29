import { useEffect, useState } from 'react'
import { AlertTriangle, Check, Clock3, LoaderCircle, RotateCcw } from 'lucide-react'
import { ApiError, getJob, getManifest } from './api'
import type { JobResponse, UploadResponse } from './api'
import type { VideoManifest } from './types'

export function JobScreen({ accepted, onComplete, onStartNew }: {
  accepted: UploadResponse
  onComplete: (manifest: VideoManifest) => void
  onStartNew: () => void
}) {
  const [job, setJob] = useState<JobResponse | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [resultError, setResultError] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    let failures = 0

    async function poll() {
      try {
        const { job: nextJob, retryAfter } = await getJob(accepted.job_id, controller.signal)
        if (controller.signal.aborted) return
        if (nextJob.video_id !== accepted.video_id || nextJob.job_id !== accepted.job_id) {
          throw new ApiError('The job response does not match this upload.', 'INVALID_RESPONSE')
        }
        setJob(nextJob)
        setConnectionError(null)
        failures = 0
        if (nextJob.status === 'failed') return
        if (nextJob.status === 'completed') {
          if (!nextJob.manifest_url) throw new ApiError('The completed job has no manifest URL.', 'INVALID_RESPONSE')
          try {
            const manifest = await getManifest(nextJob.manifest_url, controller.signal)
            if (!controller.signal.aborted) {
              if (manifest.video.video_id !== accepted.video_id) {
                throw new ApiError('The manifest does not match this upload.', 'INVALID_RESPONSE')
              }
              onComplete(manifest)
            }
          } catch (error) {
            if (!controller.signal.aborted) setResultError(error instanceof Error ? error.message : 'Could not load the analysis result.')
          }
          return
        }
        timer = setTimeout(poll, retryAfter ?? 1500)
      } catch (error) {
        if (controller.signal.aborted) return
        failures += 1
        setConnectionError(error instanceof Error ? error.message : 'Could not reach the analysis service.')
        timer = setTimeout(poll, Math.min(30000, 1500 * 2 ** Math.min(failures, 4)))
      }
    }

    void poll()
    return () => { controller.abort(); if (timer) clearTimeout(timer) }
  }, [accepted.job_id, accepted.video_id, onComplete, retryKey])

  const status = job?.status ?? 'queued'
  const progress = job?.progress_percent
  const failed = status === 'failed'

  return (
    <main className="app-shell job-page">
      <section className="job-card" aria-labelledby="job-title">
        <span className={`job-icon${failed ? ' is-error' : ''}`}>
          {failed ? <AlertTriangle size={25} aria-hidden="true" /> : status === 'completed' ? <Check size={25} aria-hidden="true" /> : status === 'queued' ? <Clock3 size={25} aria-hidden="true" /> : <LoaderCircle size={25} aria-hidden="true" />}
        </span>
        <span className="eyebrow">Video analysis</span>
        <h1 id="job-title">{failed ? 'Analysis failed' : status === 'queued' ? 'Waiting to process' : status === 'processing' ? 'Analyzing your video' : 'Opening analysis'}</h1>
        <p role="status" aria-live="polite">
          {failed ? job?.error?.message ?? 'The video could not be processed.' : status === 'queued' ? 'The upload is complete. Your job is in the queue.' : status === 'processing' ? 'The worker is analyzing frames and scoring their semantic similarity.' : 'The result is ready.'}
        </p>
        {!failed && status !== 'completed' && (
          <div className="job-progress" role="progressbar" aria-label="Video analysis" aria-valuemin={0} aria-valuemax={100} aria-valuenow={typeof progress === 'number' ? progress : undefined}>
            <div className="upload-progress-track"><div className={typeof progress === 'number' ? 'upload-progress-fill' : 'upload-progress-fill indeterminate'} style={typeof progress === 'number' ? { width: `${progress}%` } : undefined} /></div>
            <small>{typeof progress === 'number' ? `${progress}% processed` : 'Processing progress unavailable'}</small>
          </div>
        )}
        {connectionError && !failed && <p className="job-warning" role="status">Connection issue: {connectionError} Retrying automatically…</p>}
        {resultError && <div className="job-warning" role="alert"><p>{resultError}</p><button type="button" onClick={() => { setResultError(null); setRetryKey((key) => key + 1) }}><RotateCcw size={15} /> Retry opening result</button></div>}
        <p className="job-id">Job {accepted.job_id}</p>
        {(failed || resultError) && <button className="job-new-button" type="button" onClick={onStartNew}>Start a new analysis</button>}
      </section>
    </main>
  )
}
