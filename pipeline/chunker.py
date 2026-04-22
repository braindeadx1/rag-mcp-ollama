from __future__ import annotations
import re
import io
from pathlib import Path
from typing import Iterable
from bs4 import BeautifulSoup
from pypdf import PdfReader
from .config import settings


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _split_window(text: str, max_tokens: int, overlap: int) -> list[str]:
    if not text.strip():
        return []
    max_chars = max_tokens * 4
    overlap_chars = overlap * 4
    if len(text) <= max_chars:
        return [text]
    out, start = [], 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        slice_ = text[start:end]
        cut = max(slice_.rfind("\n\n"), slice_.rfind(". "), slice_.rfind(" "))
        if cut > max_chars * 0.5 and end < len(text):
            slice_ = slice_[:cut]
            end = start + cut
        out.append(slice_.strip())
        start = max(end - overlap_chars, end) if end < len(text) else end
    return [s for s in out if s]


def chunk_markdown(text: str) -> list[dict]:
    sections, current_h, buf = [], "", []
    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+", line):
            if buf:
                sections.append((current_h, "\n".join(buf).strip()))
                buf = []
            current_h = line.strip()
        else:
            buf.append(line)
    if buf:
        sections.append((current_h, "\n".join(buf).strip()))
    chunks = []
    for heading, body in sections:
        if not body:
            continue
        prefix = f"{heading}\n\n" if heading else ""
        for window in _split_window(body, settings.chunk_size, settings.chunk_overlap):
            chunks.append({"content": prefix + window, "meta": {"heading": heading}})
    return chunks or [{"content": text.strip(), "meta": {}}] if text.strip() else []


def chunk_text(text: str) -> list[dict]:
    return [{"content": w, "meta": {}} for w in _split_window(text, settings.chunk_size, settings.chunk_overlap)]


def chunk_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    title = (soup.title.string.strip() if soup.title and soup.title.string else "") or ""
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    chunks = chunk_text(text)
    if title:
        for c in chunks:
            c["meta"]["title"] = title
    return chunks


def chunk_pdf(data: bytes) -> list[dict]:
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            pages.append((i + 1, t))
    chunks = []
    for page_no, page_text in pages:
        for window in _split_window(page_text, settings.chunk_size, settings.chunk_overlap):
            chunks.append({"content": window, "meta": {"page": page_no}})
    return chunks


def chunk_code(text: str, lang_hint: str | None = None) -> list[dict]:
    lines = text.splitlines()
    if not lines:
        return []
    blocks: list[list[str]] = []
    current: list[str] = []
    boundary = re.compile(r"^(def |class |func |function |public |private |export |async |interface |type |const |let |var )")
    for ln in lines:
        if boundary.match(ln) and current:
            blocks.append(current)
            current = []
        current.append(ln)
    if current:
        blocks.append(current)
    chunks = []
    for blk in blocks:
        body = "\n".join(blk)
        for window in _split_window(body, settings.chunk_size, settings.chunk_overlap):
            chunks.append({"content": window, "meta": {"lang": lang_hint or "code"}})
    return chunks


CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".php", ".sh", ".bash", ".cpp", ".c", ".h", ".hpp", ".cs", ".kt", ".swift"}
MARKDOWN_EXTS = {".md", ".markdown"}
HTML_EXTS = {".html", ".htm"}
PDF_EXTS = {".pdf"}
TEXT_EXTS = {".txt", ".log", ".csv", ".tsv", ".yaml", ".yml", ".toml", ".ini", ".conf", ".json", ".xml"}


def detect_content_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in CODE_EXTS:
        return "code"
    if ext in MARKDOWN_EXTS:
        return "markdown"
    if ext in HTML_EXTS:
        return "html"
    if ext in PDF_EXTS:
        return "pdf"
    if ext in TEXT_EXTS:
        return "text"
    return "text"


def chunk_file(path: Path) -> tuple[list[dict], str]:
    ct = detect_content_type(path)
    if ct == "pdf":
        return chunk_pdf(path.read_bytes()), ct
    raw = path.read_text(encoding="utf-8", errors="replace")
    if ct == "markdown":
        return chunk_markdown(raw), ct
    if ct == "html":
        return chunk_html(raw), ct
    if ct == "code":
        return chunk_code(raw, lang_hint=path.suffix.lstrip(".")), ct
    return chunk_text(raw), ct


def chunk_payload(content: str | bytes, content_type: str) -> list[dict]:
    if content_type == "pdf":
        if not isinstance(content, (bytes, bytearray)):
            raise ValueError("pdf content must be bytes")
        return chunk_pdf(content)
    if isinstance(content, (bytes, bytearray)):
        content = content.decode("utf-8", errors="replace")
    if content_type == "markdown":
        return chunk_markdown(content)
    if content_type == "html":
        return chunk_html(content)
    if content_type == "code":
        return chunk_code(content)
    return chunk_text(content)
