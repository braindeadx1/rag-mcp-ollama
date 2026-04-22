import asyncio
import httpx
from .config import settings


class Embedder:
    def __init__(self, url: str | None = None, model: str | None = None, concurrency: int | None = None):
        self.url = (url or settings.ollama_url).rstrip("/") + "/api/embeddings"
        self.model = model or settings.ollama_embed_model
        self.sem = asyncio.Semaphore(concurrency or settings.max_concurrent_embeds)
        self.client = httpx.AsyncClient(timeout=60.0)

    async def embed_one(self, text: str) -> list[float]:
        async with self.sem:
            r = await self.client.post(self.url, json={"model": self.model, "prompt": text})
            r.raise_for_status()
            return r.json()["embedding"]

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.gather(*(self.embed_one(t) for t in texts))

    async def close(self):
        await self.client.aclose()
