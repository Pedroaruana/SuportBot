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
}

export type IndexedSource = {
  source: string
  type: string
  chunks: number
}

export type StreamEvent =
  | { type: "sources"; sources: Source[] }
  | { type: "token"; text: string }
  | { type: "done"; fallback: boolean }
  | { type: "error"; message: string }
