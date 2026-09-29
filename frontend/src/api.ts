export interface ApiErrorDetail {
  code: string
  message: string
  retryable: boolean
}

export interface UploadResponse {
  video_id: string
  job_id: string
  status: 'queued'
}

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed'

export interface JobResponse {
  job_id: string
  video_id: string
  status: JobStatus
  progress_percent: number | null
  error: ApiErrorDetail | null
  manifest_url: string | null
}

export class ApiError extends Error {
  constructor(message: string, public code: string, public uncertainUpload = false) {
    super(message)
    this.name = 'ApiError'
  }
}

function getErrorDetail(value: unknown): ApiErrorDetail | null {
  if (!value || typeof value !== 'object' || !('error' in value)) return null
  const detail = value.error
  if (!detail || typeof detail !== 'object' || !('message' in detail)) return null
  return {
    code: 'code' in detail ? String(detail.code) : 'UNKNOWN_ERROR',
    message: String(detail.message),
    retryable: 'retryable' in detail && detail.retryable === true,
  }
}

function parseJson(text: string): unknown {
  try { return JSON.parse(text) as unknown } catch { return null }
}

function readUploadResponse(value: unknown): UploadResponse {
  if (!value || typeof value !== 'object') throw new ApiError('The upload was accepted, but its response was invalid. Check before uploading again.', 'INVALID_RESPONSE', true)
  const response = value as Partial<UploadResponse>
  if (typeof response.video_id !== 'string' || typeof response.job_id !== 'string' || response.status !== 'queued') {
    throw new ApiError('The upload was accepted, but its response was invalid. Check before uploading again.', 'INVALID_RESPONSE', true)
  }
  return response as UploadResponse
}

export function uploadVideo(file: File, onProgress: (percent: number | null) => void): {
  promise: Promise<UploadResponse>
  abort: () => void
} {
  const request = new XMLHttpRequest()
  let aborted = false
  const promise = new Promise<UploadResponse>((resolve, reject) => {
    request.open('POST', '/api/v1/videos')
    request.responseType = 'text'
    request.upload.onprogress = (event) => {
      onProgress(event.lengthComputable ? Math.round((event.loaded / event.total) * 100) : null)
    }
    request.onload = () => {
      const body = parseJson(request.responseText)
      if (request.status === 202) {
        try { resolve(readUploadResponse(body)) } catch (error) { reject(error) }
        return
      }
      const detail = getErrorDetail(body)
      reject(new ApiError(detail?.message ?? `Upload failed (HTTP ${request.status}).`, detail?.code ?? 'UPLOAD_FAILED'))
    }
    request.onerror = () => reject(new ApiError(
      'The connection was interrupted. The server may have accepted this upload; check before uploading the file again.',
      'NETWORK_ERROR', true,
    ))
    request.onabort = () => reject(new ApiError('Upload canceled.', 'UPLOAD_CANCELED', !aborted))
    const form = new FormData()
    form.append('file', file, file.name)
    request.send(form)
  })
  return { promise, abort: () => { aborted = true; request.abort() } }
}

async function readJsonResponse(response: Response): Promise<unknown> {
  const value = await response.json().catch(() => null) as unknown
  if (!response.ok) {
    const detail = getErrorDetail(value)
    throw new ApiError(detail?.message ?? `Request failed (HTTP ${response.status}).`, detail?.code ?? 'REQUEST_FAILED')
  }
  return value
}

export async function getJob(jobId: string, signal?: AbortSignal): Promise<{ job: JobResponse; retryAfter: number | null }> {
  const response = await fetch(`/api/v1/jobs/${encodeURIComponent(jobId)}`, { signal })
  const value = await readJsonResponse(response)
  if (!value || typeof value !== 'object') throw new ApiError('The job response was invalid.', 'INVALID_RESPONSE')
  const job = value as Partial<JobResponse>
  if (typeof job.job_id !== 'string' || typeof job.video_id !== 'string' ||
      !['queued', 'processing', 'completed', 'failed'].includes(String(job.status))) {
    throw new ApiError('The job response was invalid.', 'INVALID_RESPONSE')
  }
  const retryHeader = Number(response.headers.get('Retry-After'))
  return { job: job as JobResponse, retryAfter: Number.isFinite(retryHeader) && retryHeader > 0 ? retryHeader * 1000 : null }
}

export async function getManifest(path: string, signal?: AbortSignal): Promise<VideoManifest> {
  if (!/^\/api\/v1\/videos\/[^/]+\/manifest$/.test(path)) {
    throw new ApiError('The manifest URL was invalid.', 'INVALID_RESPONSE')
  }
  const response = await fetch(path, { signal })
  return parseManifest(await readJsonResponse(response))
}

import { parseManifest } from './manifest'
import type { VideoManifest } from './types'

