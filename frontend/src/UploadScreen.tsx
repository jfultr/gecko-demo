import { useRef, useState } from 'react'
import { ArrowUpFromLine, FileVideo2, RotateCcw, Sparkles, X } from 'lucide-react'
import type { ApiError } from './api'

const DEFAULT_MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
const configuredLimit = Number(import.meta.env.VITE_MAX_UPLOAD_BYTES)
export const MAX_UPLOAD_BYTES = Number.isFinite(configuredLimit) && configuredLimit > 0
  ? configuredLimit
  : DEFAULT_MAX_UPLOAD_BYTES

const VIDEO_TYPES: Record<string, string> = {
  '.mp4': 'video/mp4',
  '.mov': 'video/quicktime',
  '.webm': 'video/webm',
}

export function validateVideoFile(file: File): string | null {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  const expectedType = VIDEO_TYPES[extension]
  if (!expectedType || (file.type && file.type !== expectedType && file.type !== 'application/octet-stream')) {
    return 'Choose an MP4, MOV, or WebM video.'
  }
  if (file.size === 0) return 'This file is empty. Choose a video with content.'
  if (file.size > MAX_UPLOAD_BYTES) {
    return `The video exceeds the ${Math.round(MAX_UPLOAD_BYTES / (1024 * 1024))} MB upload limit.`
  }
  return null
}

export function UploadScreen({ onSubmit, onViewFixture, onSelectionChange, disabled = false, uploadProgress, uploadError }: {
  onSubmit: (file: File) => void
  onViewFixture: () => void
  onSelectionChange: () => void
  disabled?: boolean
  uploadProgress: number | null
  uploadError: ApiError | null
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  function chooseFile(candidate: File | null) {
    onSelectionChange()
    setError(null)
    setFile(null)
    if (!candidate) return
    const validationError = validateVideoFile(candidate)
    if (validationError) {
      setError(validationError)
      return
    }
    setFile(candidate)
  }

  function clearFile() {
    onSelectionChange()
    setFile(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
    inputRef.current?.focus()
  }

  return (
    <main className="app-shell">
      <header className="topbar upload-topbar">
        <a className="brand" href="#top" aria-label="Gecko Vision upload">
          <span className="brand-mark"><FileVideo2 size={19} aria-hidden="true" /></span>
          <span>Gecko<span>Vision</span></span>
        </a>
        <button className="fixture-pill fixture-link" type="button" onClick={onViewFixture} disabled={disabled}><Sparkles size={13} aria-hidden="true" /> View demo analysis</button>
      </header>
      <div className="upload-page" id="top">
        <div className="upload-intro">
          <span className="eyebrow">Video analysis</span>
          <h1>Understand each moment.</h1>
          <p>Upload a video to see how strongly its frames match the configured semantic prompts over time.</p>
        </div>
        <section className="upload-card" aria-labelledby="upload-title">
          <div className="upload-card-heading">
            <span className="upload-step">01 / Upload</span>
            <h2 id="upload-title">Choose a video</h2>
            <p>MP4, MOV, or WebM · up to {Math.round(MAX_UPLOAD_BYTES / (1024 * 1024))} MB</p>
          </div>
          <input
            ref={inputRef}
            className="upload-input"
            id="video-file"
            type="file"
            accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm"
            aria-describedby={error ? 'upload-error' : uploadError ? 'upload-api-error' : 'upload-hint'}
            aria-invalid={Boolean(error || uploadError)}
            disabled={disabled}
            onChange={(event) => {
              chooseFile(event.currentTarget.files?.[0] ?? null)
              event.currentTarget.value = ''
            }}
          />
          <label
            className={`upload-dropzone${isDragging ? ' is-dragging' : ''}${error ? ' has-error' : ''}${disabled ? ' is-disabled' : ''}`}
            htmlFor="video-file"
            onDragOver={(event) => { event.preventDefault(); if (!disabled) setIsDragging(true) }}
            onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setIsDragging(false) }}
            onDrop={(event) => {
              event.preventDefault()
              setIsDragging(false)
              if (disabled) return
              if (event.dataTransfer.files.length !== 1) {
                setFile(null)
                setError('Choose one video at a time.')
                return
              }
              chooseFile(event.dataTransfer.files[0])
            }}
          >
            <span className="upload-icon"><ArrowUpFromLine size={26} aria-hidden="true" /></span>
            <strong>Drop your video here</strong>
            <span>or click to browse files</span>
          </label>
          <p className="upload-hint" id="upload-hint">Your video is stored locally for analysis. Semantic scores are not a safety assessment.</p>
          {error && <p className="upload-error" id="upload-error" role="alert">{error}</p>}
          {uploadError && <p className="upload-error" id="upload-api-error" role="alert">{uploadError.message}{uploadError.uncertainUpload ? ' Select Analyze video only if you want to upload it again.' : ''}</p>}
          {file && (
            <div className="selected-file">
              <FileVideo2 size={20} aria-hidden="true" />
              <span><strong>{file.name}</strong><small>{(file.size / (1024 * 1024)).toFixed(1)} MB · Ready to upload</small></span>
              <button type="button" onClick={clearFile} aria-label="Remove selected video"><X size={18} /></button>
            </div>
          )}
          {disabled && (
            <div className="upload-progress" role="progressbar" aria-label="Video upload" aria-valuemin={0} aria-valuemax={100} aria-valuenow={uploadProgress ?? undefined}>
              <span><strong>Uploading video</strong><small>{uploadProgress === null ? 'Preparing transfer…' : `${uploadProgress}%`}</small></span>
              <div className="upload-progress-track"><div className={uploadProgress === null ? 'upload-progress-fill indeterminate' : 'upload-progress-fill'} style={uploadProgress === null ? undefined : { width: `${uploadProgress}%` }} /></div>
            </div>
          )}
          <button className="upload-submit" type="button" disabled={!file || disabled} onClick={() => file && onSubmit(file)}>
            {disabled ? 'Uploading…' : uploadError?.uncertainUpload ? 'Upload again' : 'Analyze video'} <RotateCcw size={16} aria-hidden="true" />
          </button>
        </section>
      </div>
    </main>
  )
}
