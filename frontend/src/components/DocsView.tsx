import { useEffect, useState } from "react"
import { deleteSource, fetchSources, ingestSitemap, ingestUrl, uploadFile } from "../api"
import type { IndexedSource, IngestResult } from "../types"

type Status = { kind: "ok" | "error" | "info"; text: string }

const guardrailNotes = (r: IngestResult): string => {
  const notes: string[] = []
  const pii = r.guardrails?.pii_masked
  if (pii) notes.push(`dados pessoais mascarados (${Object.entries(pii).map(([k, v]) => `${k}: ${v}`).join(", ")})`)
  const inj = r.guardrails?.injection
  if (inj) notes.push(`${inj.chunks.length} trecho(s) com padrão de prompt injection (${inj.mode})`)
  return notes.length ? ` Atenção: ${notes.join("; ")}.` : ""
}

const describe = (r: IngestResult): string => {
  if (r.pages !== undefined && r.duplicates !== undefined) {
    const failed = r.failed?.length ? `, ${r.failed.length} falharam` : ""
    return `Sitemap: ${r.pages} páginas indexadas, ${r.duplicates} já existentes${failed}.`
  }
  if (r.status === "duplicate") return `${r.source} já estava indexado (${r.chunks} chunks), nada mudou.`
  if (r.status === "replaced") return `${r.source} atualizado, ${r.chunks} chunks.${guardrailNotes(r)}`
  return `${r.source} indexado, ${r.chunks} chunks.${guardrailNotes(r)}`
}

export const DocsView = () => {
  const [sources, setSources] = useState<IndexedSource[]>([])
  const [urlInput, setUrlInput] = useState("")
  const [sitemapInput, setSitemapInput] = useState("")
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

  const onFile = (file: File | undefined) => file && run("Processando arquivo...", async () => describe(await uploadFile(file)))

  const onUrl = () => {
    const url = urlInput.trim()
    if (!url) return
    run("Indexando URL...", async () => {
      const result = await ingestUrl(url)
      setUrlInput("")
      return describe(result)
    })
  }

  const onSitemap = () => {
    const url = sitemapInput.trim()
    if (!url) return
    run("Lendo sitemap (pode levar um tempo)...", async () => {
      const result = await ingestSitemap(url)
      setSitemapInput("")
      return describe(result)
    })
  }

  return (
    <main className="docs-area">
      <section className="ingest-section">
        <h2>Adicionar arquivo</h2>
        <label className={busy ? "upload-btn disabled" : "upload-btn"}>
          Escolher PDF, DOCX, MD ou TXT
          <input
            type="file"
            accept=".pdf,.docx,.md,.markdown,.txt"
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

      <section className="ingest-section">
        <h2>Adicionar sitemap</h2>
        <div className="url-row">
          <input
            value={sitemapInput}
            onChange={(e) => setSitemapInput(e.target.value)}
            placeholder="https://exemplo.com/sitemap.xml"
            onKeyDown={(e) => e.key === "Enter" && onSitemap()}
          />
          <button onClick={onSitemap} disabled={busy}>
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
