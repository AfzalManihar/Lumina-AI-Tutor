"""File validation, text extraction, normalisation and chunking."""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass

from app.core.config import Settings
from app.core.errors import AppError

PDF_MAGIC = b"%PDF-"


class IngestError(AppError):
    status_code = 422
    code = "invalid_document"


@dataclass
class Page:
    number: int
    text: str
    section: str | None = None


@dataclass
class Chunk:
    index: int
    text: str
    page: int | None
    section: str | None


def detect_type(data: bytes, filename: str, declared_mime: str | None) -> str:
    """Decide the file type from content signature, not from the filename or declared MIME alone."""
    head = data[:1024]
    if head.startswith(PDF_MAGIC) or PDF_MAGIC in head[:1024]:
        if not head.lstrip().startswith(PDF_MAGIC):
            raise IngestError("Corrupted PDF header", code="corrupted_document")
        return "pdf"
    if b"\x00" in data[:8192]:
        raise IngestError("Unsupported binary file. Supported formats: PDF, TXT, MD", code="unsupported_type")
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in ("txt", "md", "markdown", "text"):
        return "md" if ext in ("md", "markdown") else "txt"
    raise IngestError("Unsupported file type. Supported formats: PDF, TXT, MD", code="unsupported_type")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    text = re.sub(r"-\n(?=[a-z])", "", text)  # de-hyphenate line wraps
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pages(data: bytes, kind: str, settings: Settings) -> list[Page]:
    if kind == "pdf":
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise IngestError("Encrypted PDFs are not supported", code="encrypted_document")
            if len(reader.pages) > settings.max_pdf_pages:
                raise IngestError(f"PDF exceeds {settings.max_pdf_pages} pages", code="too_many_pages")
            pages = []
            for i, pg in enumerate(reader.pages, start=1):
                pages.append(Page(i, normalize(pg.extract_text() or "")))
        except IngestError:
            raise
        except (PdfReadError, ValueError, KeyError, OSError, TypeError, AttributeError, RecursionError):
            raise IngestError("PDF is corrupted or unreadable", code="corrupted_document")
        if not any(p.text for p in pages):
            raise IngestError("No extractable text found (scanned PDFs need OCR, which is not supported)",
                              code="empty_document")
        return pages
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise IngestError("Text files must be UTF-8 encoded", code="corrupted_document")
    text = normalize(text)
    if not text:
        raise IngestError("Document is empty", code="empty_document")
    if kind == "md":
        return _split_markdown(text)
    return [Page(1, text)]


def _split_markdown(text: str) -> list[Page]:
    """Markdown has no pages; each top-level section becomes a pseudo-page tagged with its heading."""
    sections, cur, heading = [], [], None
    for line in text.split("\n"):
        m = re.match(r"^(#{1,2})\s+(.*)", line)
        if m and cur:
            sections.append((heading, "\n".join(cur)))
            cur = []
        if m:
            heading = m.group(2).strip()
        cur.append(line)
    if cur:
        sections.append((heading, "\n".join(cur)))
    return [Page(i, t.strip(), h) for i, (h, t) in enumerate(sections, 1) if t.strip()]


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    if size <= overlap:
        raise ValueError("chunk size must exceed overlap")
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    out, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"), window.rfind(" "))
            if cut > size * 0.5:
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return out


def chunk_pages(pages: list[Page], settings: Settings) -> list[Chunk]:
    chunks: list[Chunk] = []
    for p in pages:
        for piece in chunk_text(p.text, settings.rag_chunk_size, settings.rag_chunk_overlap):
            chunks.append(Chunk(len(chunks), piece, p.number, p.section))
    return chunks


def validate_upload(data: bytes, filename: str, mime: str | None, settings: Settings) -> str:
    if not data:
        raise IngestError("Uploaded file is empty", code="empty_document")
    if len(data) > settings.max_upload_bytes:
        raise AppError(f"File exceeds {settings.max_upload_bytes // (1024 * 1024)} MB limit",
                       code="file_too_large", status_code=413)
    return detect_type(data, filename, mime)
