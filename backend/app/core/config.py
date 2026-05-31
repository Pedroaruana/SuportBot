from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str
    chroma_persist_dir: str = "./chroma_db"
    embedding_model: str = "models/gemini-embedding-001"
    llm_model: str = "gemini-2.5-flash-lite"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retriever_k: int = 4
    company_name: str = "SupportBot"

    class Config:
        env_file = ".env"


settings = Settings()
