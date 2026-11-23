from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str
    # Vazio desliga a autenticacao (modo dev). Em producao, defina um valor forte.
    api_key: str = ""
    allowed_origins: str = "http://localhost:5173"

    chroma_persist_dir: str = "./data/chroma"
    sqlite_path: str = "./data/supportbot.db"

    embedding_model: str = "models/gemini-embedding-001"
    # gemini | openai | ollama. Os embeddings continuam no Gemini (trocar exige reindexar).
    llm_provider: str = "gemini"
    # Vazio usa o padrao do provedor (ver services/llm.py)
    llm_model: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    company_name: str = "SupportBot"

    chunk_size: int = 1000
    chunk_overlap: int = 200
    retriever_k: int = 4
    fetch_k: int = 20
    # Similaridade (cosseno) minima do melhor chunk para tentar responder
    min_relevance: float = 0.70
    history_turns: int = 5

    # Guardrails de ingestao. pii_mode: off | mask | block. injection_mode: off | flag | drop | block
    pii_mode: str = "mask"
    pii_types: str = "cpf,email"
    pii_allow_emails: str = ""
    injection_mode: str = "drop"

    max_sitemap_urls: int = 20
    max_upload_mb: int = 10
    max_url_kb: int = 2048
    rate_limit_chat_per_min: int = 20
    rate_limit_ingest_per_min: int = 10

    @property
    def pii_type_list(self) -> list[str]:
        return [t.strip() for t in self.pii_types.split(",") if t.strip()]

    @property
    def pii_allowlist(self) -> list[str]:
        return [e.strip().lower() for e in self.pii_allow_emails.split(",") if e.strip()]

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
