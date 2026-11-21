import { useEffect, useState } from "react"
import "./index.css"
import { ChatView } from "./components/ChatView"
import { DocsView } from "./components/DocsView"

type Tab = "chat" | "docs"
type Theme = "light" | "dark"

const initialTheme = (): Theme => {
  try {
    const saved = localStorage.getItem("theme")
    if (saved === "light" || saved === "dark") return saved
  } catch {
    // localStorage indisponível
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export default function App() {
  const [tab, setTab] = useState<Tab>("chat")
  const [theme, setTheme] = useState<Theme>(initialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem("theme", theme)
    } catch {
      // ignora
    }
  }, [theme])

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <span className="logo">SupportBot</span>
          <nav className="tabs">
            <button className={tab === "chat" ? "tab active" : "tab"} onClick={() => setTab("chat")}>
              Chat
            </button>
            <button className={tab === "docs" ? "tab active" : "tab"} onClick={() => setTab("docs")}>
              Documentos
            </button>
            <button className="tab" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? "Claro" : "Escuro"}
            </button>
          </nav>
        </div>
      </header>
      {tab === "chat" ? <ChatView /> : <DocsView />}
    </div>
  )
}
