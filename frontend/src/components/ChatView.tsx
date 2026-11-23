import { useEffect, useRef, useState } from "react"
import { clearSession, sendFeedback, streamChat } from "../api"
import type { ChatMessage, Rating, StreamEvent } from "../types"
import { Message } from "./Message"

const WELCOME: ChatMessage = {
  role: "bot",
  text: "Olá! Sou o SupportBot. Envie PDFs ou URLs na aba Documentos e me pergunte sobre eles.",
  sources: [],
}

const newSessionId = () => crypto.randomUUID()

export const ChatView = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const sessionId = useRef(newSessionId())
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const patchLast = (patch: (m: ChatMessage) => ChatMessage) =>
    setMessages((prev) => [...prev.slice(0, -1), patch(prev[prev.length - 1])])

  const handleEvent = (event: StreamEvent) => {
    if (event.type === "sources") patchLast((m) => ({ ...m, sources: event.sources }))
    else if (event.type === "token") patchLast((m) => ({ ...m, text: m.text + event.text }))
    else if (event.type === "done") patchLast((m) => ({ ...m, streaming: false, fallback: event.fallback, messageId: event.message_id }))
    else if (event.type === "error") patchLast((m) => ({ ...m, streaming: false, text: event.message }))
  }

  const send = async () => {
    const question = input.trim()
    if (!question || loading) return
    setInput("")
    setLoading(true)
    setMessages((prev) => [
      ...prev,
      { role: "user", text: question, sources: [] },
      { role: "bot", text: "", sources: [], streaming: true },
    ])

    try {
      await streamChat(question, sessionId.current, handleEvent)
    } catch (e) {
      const message = e instanceof Error ? e.message : "Erro ao conectar com o servidor."
      patchLast((m) => ({ ...m, streaming: false, text: m.text || message }))
    } finally {
      patchLast((m) => ({ ...m, streaming: false }))
      setLoading(false)
    }
  }

  const rate = async (index: number, rating: Rating) => {
    const target = messages[index]
    if (!target.messageId) return
    const previous = target.rating
    const setRating = (value?: Rating) =>
      setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, rating: value } : m)))
    setRating(rating)
    try {
      await sendFeedback(target.messageId, rating)
    } catch {
      setRating(previous)
    }
  }

  const reset = async () => {
    await clearSession(sessionId.current).catch(() => undefined)
    sessionId.current = newSessionId()
    setMessages([WELCOME])
  }

  return (
    <main className="chat-area">
      <div className="messages">
        {messages.map((msg, i) => (
          <Message key={i} msg={msg} onRate={(r) => rate(i, r)} />
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="input-bar">
        <button className="ghost" onClick={reset} disabled={loading || messages.length === 1}>
          Nova conversa
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Faça uma pergunta sobre os documentos..."
          disabled={loading}
          maxLength={2000}
        />
        <button onClick={send} disabled={loading || !input.trim()}>
          Enviar
        </button>
      </div>
    </main>
  )
}
