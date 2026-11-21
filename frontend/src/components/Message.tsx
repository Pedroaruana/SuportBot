import { useState } from "react"
import ReactMarkdown from "react-markdown"
import type { ChatMessage } from "../types"

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

export const Message = ({ msg }: { msg: ChatMessage }) => (
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
  </div>
)
