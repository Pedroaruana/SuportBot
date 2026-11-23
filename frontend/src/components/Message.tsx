import { useState } from "react"
import ReactMarkdown from "react-markdown"
import type { ChatMessage, Rating } from "../types"

const SourceList = ({ sources }: { sources: ChatMessage["sources"] }) => {
  const [open, setOpen] = useState<number | null>(null)
  if (sources.length === 0) return null

  return (
    <div className="sources">
      <div className="source-chips">
        {sources.map((s) => (
          <button
            key={s.id}
            className={open === s.id ? "source-tag open" : "source-tag"}
            onClick={() => setOpen(open === s.id ? null : s.id)}
            title="Ver trecho usado"
          >
            [{s.id}] {s.source}
            {s.page ? ` p.${s.page}` : ""}
          </button>
        ))}
      </div>
      {sources.map(
        (s) =>
          open === s.id && (
            <blockquote key={s.id} className="snippet">
              {s.snippet}
              {s.snippet.length >= 220 ? "..." : ""}
              {s.score !== null && <span className="snippet-score">similaridade {s.score.toFixed(2)}</span>}
            </blockquote>
          )
      )}
    </div>
  )
}

const Thumb = ({ down }: { down?: boolean }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={down ? { transform: "rotate(180deg)" } : undefined}>
    <path d="M7 10v11H3V10h4zM7 10l4-8a2 2 0 0 1 2 2v4h6a2 2 0 0 1 2 2.3l-1.4 8A2 2 0 0 1 17.6 21H7" />
  </svg>
)

const Feedback = ({ rating, onRate }: { rating?: Rating; onRate: (r: Rating) => void }) => (
  <div className="feedback" role="group" aria-label="Avaliar resposta">
    <button className={rating === "up" ? "thumb active" : "thumb"} onClick={() => onRate("up")} title="Resposta útil" aria-pressed={rating === "up"}>
      <Thumb />
    </button>
    <button className={rating === "down" ? "thumb active down" : "thumb"} onClick={() => onRate("down")} title="Não ajudou" aria-pressed={rating === "down"}>
      <Thumb down />
    </button>
  </div>
)

type Props = { msg: ChatMessage; onRate?: (rating: Rating) => void }

export const Message = ({ msg, onRate }: Props) => (
  <div className={`msg msg-${msg.role}`}>
    <div className={msg.fallback ? "bubble fallback" : "bubble"}>
      {msg.role === "bot" ? (
        msg.text ? (
          <ReactMarkdown>{msg.text}</ReactMarkdown>
        ) : (
          <span className="typing">
            <span />
            <span />
            <span />
          </span>
        )
      ) : (
        msg.text
      )}
      {msg.streaming && msg.text && <span className="cursor" />}
    </div>
    {msg.role === "bot" && <SourceList sources={msg.sources} />}
    {msg.role === "bot" && msg.messageId && !msg.streaming && onRate && <Feedback rating={msg.rating} onRate={onRate} />}
  </div>
)
