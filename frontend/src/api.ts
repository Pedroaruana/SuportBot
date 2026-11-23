import type {
  AnalyticsSummary,
  DownvotedAnswer,
  IndexedSource,
  IngestResult,
  Rating,
  StreamEvent,
  UnansweredQuestion,
} from "./types"

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api"
// Atenção: variáveis VITE_* vão para o bundle. Use só em demo; em produção, proxy no servidor.
const API_KEY = import.meta.env.VITE_API_KEY ?? ""

const authHeaders = (): Record<string, string> => (API_KEY ? { "X-API-Key": API_KEY } : {})

const errorMessage = async (res: Response): Promise<string> => {
  try {
    const body = await res.json()
    if (typeof body.detail === "string") return body.detail
  } catch {
    // corpo sem JSON
  }
  return `Erro ${res.status}`
}

export const streamChat = async (
  question: string,
  sessionId: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> => {
  const res = await fetch(`${API}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ question, session_id: sessionId }),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(await errorMessage(res))

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split("\n\n")
    buffer = frames.pop() ?? ""
    for (const frame of frames) {
      if (frame.startsWith("data: ")) onEvent(JSON.parse(frame.slice(6)) as StreamEvent)
    }
  }
}

export const clearSession = (sessionId: string) =>
  fetch(`${API}/chat/${sessionId}`, { method: "DELETE", headers: authHeaders() })

export const fetchSources = async (): Promise<IndexedSource[]> => {
  const res = await fetch(`${API}/ingest/sources`, { headers: authHeaders() })
  if (!res.ok) throw new Error(await errorMessage(res))
  return res.json()
}

export const uploadFile = async (file: File): Promise<IngestResult> => {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${API}/ingest/file`, { method: "POST", headers: authHeaders(), body: form })
  if (!res.ok) throw new Error(await errorMessage(res))
  return res.json()
}

export const ingestUrl = async (url: string): Promise<IngestResult> => {
  const res = await fetch(`${API}/ingest/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) throw new Error(await errorMessage(res))
  return res.json()
}

export const deleteSource = async (source: string): Promise<void> => {
  const res = await fetch(`${API}/ingest/sources?source=${encodeURIComponent(source)}`, {
    method: "DELETE",
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(await errorMessage(res))
}

export const ingestSitemap = async (url: string): Promise<IngestResult> => {
  const res = await fetch(`${API}/ingest/sitemap`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) throw new Error(await errorMessage(res))
  return res.json()
}

export const sendFeedback = async (messageId: number, rating: Rating, comment?: string): Promise<void> => {
  const res = await fetch(`${API}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ message_id: messageId, rating, comment: comment || null }),
  })
  if (!res.ok) throw new Error(await errorMessage(res))
}

const getJson = async <T>(path: string): Promise<T> => {
  const res = await fetch(`${API}${path}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(await errorMessage(res))
  return res.json()
}

export const fetchSummary = () => getJson<AnalyticsSummary>("/analytics/summary")
export const fetchUnanswered = () => getJson<UnansweredQuestion[]>("/analytics/unanswered")
export const fetchDownvoted = () => getJson<DownvotedAnswer[]>("/analytics/downvoted")
