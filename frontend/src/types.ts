export type Source = {
  id: number
  source: string
  type: string
  page: number | null
  snippet: string
  score: number | null
}

export type ChatMessage = {
  role: "user" | "bot"
  text: string
  sources: Source[]
  streaming?: boolean
  fallback?: boolean
  messageId?: number
  rating?: Rating
}

export type Rating = "up" | "down"

export type IndexedSource = {
  source: string
  type: string
  chunks: number
}

export type StreamEvent =
  | { type: "sources"; sources: Source[] }
  | { type: "token"; text: string }
  | { type: "done"; fallback: boolean; message_id: number }
  | { type: "error"; message: string }

export type IngestResult = {
  status: "success" | "replaced" | "duplicate"
  source: string
  chunks: number
  pages?: number
  duplicates?: number
  failed?: { url: string; message: string }[]
  guardrails?: {
    pii_masked?: Record<string, number>
    injection?: { mode: string; chunks: unknown[] }
  }
}

export type AnalyticsSummary = {
  interactions: number
  fallbacks: number
  fallback_rate: number
  feedback_up: number
  feedback_down: number
  satisfaction: number | null
}

export type UnansweredQuestion = { question: string; count: number; last_seen: string }

export type DownvotedAnswer = {
  message_id: number
  question: string
  answer: string
  comment: string | null
  created_at: string
}
