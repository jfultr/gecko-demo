export type ScoreLevel = 'low' | 'medium' | 'high'

export interface RiskSample {
  timestamp_seconds: number
  score: number
}

export interface VideoManifest {
  schema_version: '1.0'
  video: {
    video_id: string
    filename: string
    source_url: string
    duration_seconds: number
    width: number
    height: number
  }
  generated_at: string
  score_label: 'semantic_similarity'
  score_range: [0, 100]
  preset: {
    preset_id: string
    label: string
    positive_prompts: string[]
    negative_prompts: string[]
  }
  samples: RiskSample[]
  peaks: Array<{
    event_id: string
    timestamp_seconds: number
    score: number
    level: ScoreLevel
    frame: {
      frame_id: string
      timestamp_seconds: number
      image_url: string
    }
    prompt: string
  }>
}
