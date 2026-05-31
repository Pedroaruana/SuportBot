import { useState, useRef, useEffect } from "react";
import "./index.css";

const API = "http://localhost:8000/api";
const SESSION_ID = crypto.randomUUID();

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: "bot",
      text: "Olá! Sou o SupportBot. Envie documentos PDF ou URLs para eu aprender, depois me faça perguntas sobre eles.",
      sources: [],
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sources, setSources] = useState([]);
  const [tab, setTab] = useState("chat"); // "chat" | "docs"
  const [urlInput, setUrlInput] = useState("");
  const [ingestStatus, setIngestStatus] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (tab === "docs") fetchSources();
  }, [tab]);

  async function fetchSources() {
    const res = await fetch(`${API}/ingest/sources`);
    const data = await res.json();
    setSources(data);
  }

  async function sendMessage() {
    if (!input.trim() || loading) return;
    const question = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setLoading(true);

    try {
      const res = await fetch(`${API}/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, session_id: SESSION_ID }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: data.answer, sources: data.sources },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: "Erro ao conectar com o servidor.", sources: [] },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handlePdfUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    setIngestStatus("Processando PDF...");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API}/ingest/pdf`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (data.status === "success") {
        setIngestStatus(`✓ ${data.source} indexado — ${data.chunks} chunks, ${data.pages} páginas`);
        fetchSources();
      } else {
        setIngestStatus(`Erro: ${data.detail}`);
      }
    } catch {
      setIngestStatus("Erro ao processar o arquivo.");
    }
  }

  async function handleUrlIngest() {
    if (!urlInput.trim()) return;
    setIngestStatus("Indexando URL...");
    try {
      const res = await fetch(`${API}/ingest/url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: urlInput.trim() }),
      });
      const data = await res.json();
      if (data.status === "success") {
        setIngestStatus(`✓ URL indexada — ${data.chunks} chunks extraídos`);
        setUrlInput("");
        fetchSources();
      } else {
        setIngestStatus(`Erro: ${data.detail}`);
      }
    } catch {
      setIngestStatus("Erro ao indexar a URL.");
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <span className="logo">SupportBot</span>
          <nav className="tabs">
            <button className={tab === "chat" ? "tab active" : "tab"} onClick={() => setTab("chat")}>Chat</button>
            <button className={tab === "docs" ? "tab active" : "tab"} onClick={() => setTab("docs")}>Documentos</button>
          </nav>
        </div>
      </header>

      {tab === "chat" && (
        <main className="chat-area">
          <div className="messages">
            {messages.map((msg, i) => (
              <div key={i} className={`msg msg-${msg.role}`}>
                <div className="bubble">{msg.text}</div>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="sources">
                    {msg.sources.map((s, j) => (
                      <span key={j} className="source-tag">
                        {s.type === "pdf" ? "📄" : "🌐"} {s.source}{s.page ? ` p.${s.page}` : ""}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="msg msg-bot">
                <div className="bubble typing">
                  <span /><span /><span />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
          <div className="input-bar">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Faça uma pergunta sobre os documentos..."
              disabled={loading}
            />
            <button onClick={sendMessage} disabled={loading || !input.trim()}>
              Enviar
            </button>
          </div>
        </main>
      )}

      {tab === "docs" && (
        <main className="docs-area">
          <section className="ingest-section">
            <h2>Adicionar PDF</h2>
            <label className="upload-btn">
              Escolher arquivo .pdf
              <input type="file" accept=".pdf" onChange={handlePdfUpload} hidden />
            </label>
          </section>

          <section className="ingest-section">
            <h2>Adicionar URL</h2>
            <div className="url-row">
              <input
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://exemplo.com/pagina"
                onKeyDown={(e) => e.key === "Enter" && handleUrlIngest()}
              />
              <button onClick={handleUrlIngest}>Indexar</button>
            </div>
          </section>

          {ingestStatus && <p className="ingest-status">{ingestStatus}</p>}

          <section className="ingest-section">
            <h2>Fontes indexadas</h2>
            {sources.length === 0 ? (
              <p className="empty">Nenhum documento indexado ainda.</p>
            ) : (
              <ul className="source-list">
                {sources.map((s, i) => (
                  <li key={i}>
                    <span>{s.type === "pdf" ? "📄" : "🌐"}</span>
                    <span className="source-name">{s.source}</span>
                    <span className="source-type">{s.type}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </main>
      )}
    </div>
  );
}
