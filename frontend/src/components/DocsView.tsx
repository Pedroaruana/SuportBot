import { useEffect, useState } from "react"
import { deleteSource, fetchSources, ingestUrl, uploadPdf } from "../api"
import type { IndexedSource } from "../types"

type Status = { kind: "ok" | "error" | "info"; text: string }

const describe = (r: { status: string; source: string; chunks: number }): string => {
  if (r.status === "duplicate") return `${r.source} já estava indexado (${r.chunks} chunks), nada mudou.`
  if (r.status === "replaced") return `${r.source} atualizado, ${r.chunks} chunks.`
  return `${r.source} indexado, ${r.chunks} chunks.`
}

export const DocsView = () => {
  const [sources, setSources] = useState<IndexedSource[]>([])
  const [urlInput, setUrlInput] = useState("")
  const [status, setStatus] = useState<Status | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = () =>
    fetchSources()
      .then(setSources)
      .catch((e: Error) => setStatus({ kind: "error", text: e.message }))

  useEffect(() => {
    refresh()
  }, [])

  const run = async (label: string, action: () => Promise<string | void>) => {
    setBusy(true)
    setStatus({ kind: "info", text: label })
    try {
      const text = await action()
      setStatus(text ? { kind: "ok", text } : null)
      await refresh()
    } catch (e) {
      setStatus({ kind: "error", text: e instanceof Error ? e.message : "Erro inesperado." })
    } finally {
      setBusy(false)
    }
  }

  const onFile = (file: File | undefined) => file && run("Processando PDF...", async () => describe(await uploadPdf(file)))

  const onUrl = () => {
    const url = urlInput.trim()
    if (!url) return
    run("Indexando URL...", async () => {
      const result = await ingestUrl(url)
      setUrlInput("")
      return describe(result)
    })
  }

  return (
    <main className="docs-area">
      <section className="ingest-section">
        <h2>Adicionar PDF</h2>
        <label className={busy ? "upload-btn disabled" : "upload-btn"}>
          Escolher arquivo .pdf
          <input
            type="file"
            accept=".pdf,application/pdf"
            hidden
            disabled={busy}
            onChange={(e) => {
              onFile(e.target.files?.[0])
              e.target.value = ""
            }}
          />
        </label>
      </section>

      <section className="ingest-section">
        <h2>Adicionar URL</h2>
        <div className="url-row">
          <input
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="https://exemplo.com/pagina"
            onKeyDown={(e) => e.key === "Enter" && onUrl()}
          />
          <button onClick={onUrl} disabled={busy}>
            Indexar
          </button>
        </div>
      </section>

      {status && <p className={`ingest-status ${status.kind}`}>{status.text}</p>}

      <section className="ingest-section">
        <h2>Fontes indexadas</h2>
        {sources.length === 0 ? (
          <p className="empty">Nenhum documento indexado ainda.</p>
        ) : (
          <ul className="source-list">
            {sources.map((s) => (
              <li key={s.source}>
                <span className="source-type">{s.type}</span>
                <span className="source-name">{s.source}</span>
                <span className="source-chunks">{s.chunks} chunks</span>
                <button
                  className="danger"
                  disabled={busy}
                  onClick={() => run("Removendo...", async () => (await deleteSource(s.source), `${s.source} removido.`))}
                >
                  Remover
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}
