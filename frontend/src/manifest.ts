import fixture from '@fixture/manifest'
import type { VideoManifest } from './types'

function isNumberInRange(value: unknown, min: number, max: number) {
  return typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max
}

export function parseManifest(value: unknown): VideoManifest {
  if (!value || typeof value !== 'object') {
    throw new Error('The analysis result is not an object.')
  }

  const manifest = value as Partial<VideoManifest>
  if (manifest.schema_version !== '1.0') {
    throw new Error(`Unsupported manifest version: ${String(manifest.schema_version)}`)
  }
  if (
    manifest.score_label !== 'semantic_similarity' ||
    manifest.score_range?.[0] !== 0 ||
    manifest.score_range?.[1] !== 100
  ) {
    throw new Error('The analysis result uses an unsupported score contract.')
  }
  if (!manifest.video || !isNumberInRange(manifest.video.duration_seconds, 0.001, Infinity)) {
    throw new Error('The analysis result has invalid video metadata.')
  }
  if (!Array.isArray(manifest.samples)) {
    throw new Error('The analysis result has no score samples.')
  }
  const invalidSample = manifest.samples.some(
    (sample) =>
      !isNumberInRange(sample.timestamp_seconds, 0, manifest.video!.duration_seconds) ||
      !isNumberInRange(sample.score, 0, 100),
  )
  if (invalidSample) {
    throw new Error('The analysis result contains an invalid score sample.')
  }

  return {
    ...(manifest as VideoManifest),
    samples: [...manifest.samples].sort((a, b) => a.timestamp_seconds - b.timestamp_seconds),
  }
}

export const demoManifest = parseManifest(fixture)

export function resolvePreviewMedia(sourceUrl: string) {
  const fixtureRoute = `/api/v1/videos/${demoManifest.video.video_id}/source`
  return sourceUrl === fixtureRoute ? '/demo/warehouse-walkthrough.mp4' : sourceUrl
}

export function resolveEvidenceMedia(imageUrl: string, isFixture: boolean) {
  if (!isFixture) return imageUrl
  const fixturePeak = demoManifest.peaks.find((peak) => peak.frame.image_url === imageUrl)
  return fixturePeak ? `/demo/frames/${fixturePeak.frame.frame_id}.jpg` : imageUrl
}
