from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from .config import settings
from .indexer import Indexer


indexer: Indexer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global indexer
    indexer = Indexer()
    yield
    await indexer.close()


app = FastAPI(title="rag-mcp-ollama API", lifespan=lifespan)


def auth(authorization: Annotated[str | None, Header()] = None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    if authorization.removeprefix("Bearer ").strip() != settings.rag_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


class IndexTextRequest(BaseModel):
    source: str
    content: str
    content_type: str = "text"
    metadata: dict | None = None


class IndexWebRequest(BaseModel):
    url: str
    content: str
    title: str | None = None
    metadata: dict | None = None


class SearchRequest(BaseModel):
    queries: list[str]
    limit: int = 5
    source: str | None = None
    content_type: str | None = None
    include_history: bool = False


@app.get("/health")
async def health():
    s = indexer.store.stats()
    return {"status": "ok", **s}


@app.post("/index/text")
async def index_text(req: IndexTextRequest, authorization: Annotated[str | None, Header()] = None):
    auth(authorization)
    return await indexer.index_text(req.source, req.content, req.content_type, req.metadata)


@app.post("/index/web")
async def index_web(req: IndexWebRequest, authorization: Annotated[str | None, Header()] = None):
    auth(authorization)
    md = dict(req.metadata or {})
    if req.title:
        md["title"] = req.title
    return await indexer.index_text(req.url, req.content, "html", md)


@app.post("/index/file")
async def index_file(file: UploadFile = File(...), source: str = Form(...), content_type: str = Form("text"), authorization: Annotated[str | None, Header()] = None):
    auth(authorization)
    data = await file.read()
    if content_type == "pdf":
        return await indexer.index_text(source, data, "pdf", {"filename": file.filename})
    return await indexer.index_text(source, data.decode("utf-8", errors="replace"), content_type, {"filename": file.filename})


@app.post("/search")
async def search(req: SearchRequest, authorization: Annotated[str | None, Header()] = None):
    auth(authorization)
    return await indexer.search(req.queries, req.limit, req.source, req.content_type, req.include_history)


@app.get("/stats")
async def stats(authorization: Annotated[str | None, Header()] = None):
    auth(authorization)
    return indexer.store.stats()


@app.get("/sources")
async def sources(authorization: Annotated[str | None, Header()] = None):
    auth(authorization)
    return indexer.store.list_sources()


@app.delete("/source")
async def delete_source(source: str, authorization: Annotated[str | None, Header()] = None):
    auth(authorization)
    indexer.store.delete_source(source)
    return {"deleted_source": source}
