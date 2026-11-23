import { useEffect, useState } from "react"
import { fetchDownvoted, fetchSummary, fetchUnanswered } from "../api"
import type { AnalyticsSummary, DownvotedAnswer, UnansweredQuestion } from "../types"

const pct = (value: number | null) => (value === null ? "sem votos" : `${Math.round(value * 100)}%`)

export const AnalyticsView = () => {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [unanswered, setUnanswered] = useState<UnansweredQuestion[]>([])
  const [downvoted, setDownvoted] = useState<DownvotedAnswer[]>([])
  const [error, setError] = useState("")

  useEffect(() => {
    Promise.all([fetchSummary(), fetchUnanswered(), fetchDownvoted()])
      .then(([s, u, d]) => {
        setSummary(s)
        setUnanswered(u)
        setDownvoted(d)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) return <main className="docs-area"><p className="ingest-status error">{error}</p></main>
  if (!summary) return <main className="docs-area"><p className="empty">Carregando...</p></main>

  return (
    <main className="docs-area">
      <dl className="stats">
        <div>
          <dt>Perguntas</dt>
          <dd>{summary.interactions}</dd>
        </div>
        <div>
          <dt>Sem resposta</dt>
          <dd>{pct(summary.fallback_rate)}</dd>
        </div>
        <div>
          <dt>Satisfação</dt>
          <dd>{pct(summary.satisfaction)}</dd>
        </div>
        <div>
          <dt>Votos</dt>
          <dd>
            {summary.feedback_up} / {summary.feedback_down}
          </dd>
        </div>
      </dl>

      <section className="ingest-section">
        <h2>Perguntas sem resposta</h2>
        <p className="hint">O que as pessoas perguntaram e os documentos não cobrem. Indexe o conteúdo que falta.</p>
        {unanswered.length === 0 ? (
          <p className="empty">Nenhuma até agora.</p>
        ) : (
          <ul className="source-list">
            {unanswered.map((q) => (
              <li key={q.question}>
                <span className="count">{q.count}x</span>
                <span className="source-name question">{q.question}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="ingest-section">
        <h2>Respostas que não ajudaram</h2>
        {downvoted.length === 0 ? (
          <p className="empty">Nenhuma avaliação negativa.</p>
        ) : (
          <ul className="downvoted">
            {downvoted.map((d) => (
              <li key={d.message_id}>
                <p className="q">{d.question}</p>
                <p className="a">{d.answer}</p>
                {d.comment && <p className="c">Comentário: {d.comment}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}
