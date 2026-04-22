from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "rag"
    ollama_url: str = "http://localhost:11434"
    ollama_embed_model: str = "bge-m3"
    embed_dim: int = 1024
    rag_api_key: str = "change-me"
    inbox_dir: str = "/data/rag-inbox"
    archive_dir: str = "/data/rag-archiv"
    failed_dir: str = "/data/rag-failed"
    chunk_size: int = 512
    chunk_overlap: int = 64
    max_concurrent_embeds: int = 8


settings = Settings()
