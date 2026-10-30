import pytest

from app.core.config import Settings
from app.rag.ingest import IngestError, chunk_text, extract_pages, normalize, validate_upload
from tests.conftest import make_settings, register
from tests.pdfs import HISTORY_PAGES, PHOTO_PAGES, make_pdf


def test_chunking_overlap_and_bounds():
    text = " ".join(f"word{i}" for i in range(400))
    chunks = chunk_text(text, 200, 40)
    assert len(chunks) > 5 and all(len(c) <= 200 for c in chunks)
    # consecutive chunks overlap
    assert any(w in chunks[1] for w in chunks[0].split()[-3:])
    assert chunk_text("short", 200, 40) == ["short"]
    assert chunk_text("   ", 200, 40) == []
    with pytest.raises(ValueError):
        chunk_text("x", 10, 10)


def test_normalize():
    assert normalize("Hello  world\x00 \n\n\n\nnext-\nword") == "Hello world \n\nnextword".replace(" \n", "\n")


def test_validate_upload_signature_not_filename():
    s = make_settings()
    with pytest.raises(IngestError):
        validate_upload(b"", "a.pdf", "application/pdf", s)
    with pytest.raises(IngestError):  # PNG bytes named .pdf
        validate_upload(b"\x89PNG\r\n\x1a\n\x00\x00", "fake.pdf", "application/pdf", s)
    with pytest.raises(IngestError):
        validate_upload(b"MZ\x90\x00\x03\x00", "x.txt", "text/plain", s)
    assert validate_upload(make_pdf(["hi"]), "renamed.txt", "text/plain", s) == "pdf"  # signature wins
    assert validate_upload(b"# T\nbody", "n.md", None, s) == "md"
    with pytest.raises(Exception) as e:
        validate_upload(b"a" * 100, "a.txt", None, make_settings(max_upload_bytes=50))
    assert getattr(e.value, "status_code", None) == 413


def test_corrupted_empty_and_encrypted_pdfs():
    s = make_settings()
    with pytest.raises(IngestError) as e:
        extract_pages(b"%PDF-1.4\nnot really a pdf at all", "pdf", s)
    assert e.value.code == "corrupted_document"
    with pytest.raises(IngestError) as e:
        extract_pages(make_pdf([""]), "pdf", s)
    assert e.value.code == "empty_document"
    from pypdf import PdfReader, PdfWriter
    import io
    w = PdfWriter()
    for p in PdfReader(io.BytesIO(make_pdf(["secret text"]))).pages:
        w.add_page(p)
    w.encrypt("pw")
    buf = io.BytesIO()
    w.write(buf)
    with pytest.raises(IngestError) as e:
        extract_pages(buf.getvalue(), "pdf", s)
    assert e.value.code == "encrypted_document"


def test_pdf_page_metadata():
    pages = extract_pages(make_pdf(PHOTO_PAGES), "pdf", make_settings())
    assert [p.number for p in pages] == [1, 2] and "Calvin" in pages[1].text


async def _upload(c, name, data, mime="application/pdf"):
    return await c.post("/api/v1/documents", files={"file": (name, data, mime)})


async def test_upload_list_get_delete_flow(client):
    await register(client)
    r = await _upload(client, "bio.pdf", make_pdf(PHOTO_PAGES))
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["status"] == "ready" and d["pages"] == 2 and d["chunk_count"] >= 2
    assert '"embedding"' not in r.text and "vector" not in r.text
    lst = (await client.get("/api/v1/documents")).json()
    assert lst["total"] == 1
    p = (await client.get(f"/api/v1/documents/{d['id']}/passages", params={"page": 2})).json()["items"]
    assert p and all(x["page"] == 2 for x in p)
    assert (await client.delete(f"/api/v1/documents/{d['id']}")).status_code == 204
    assert (await client.get(f"/api/v1/documents/{d['id']}")).status_code == 404
    assert (await client.get("/api/v1/documents")).json()["total"] == 0


async def test_upload_rejections(client, db):
    await register(client)
    assert (await _upload(client, "x.pdf", b"")).status_code == 422
    assert (await _upload(client, "x.exe", b"MZ\x00\x00binary")).status_code == 422
    assert (await _upload(client, "bad.pdf", b"%PDF-1.4 garbage")).status_code == 422
    assert (await _upload(client, "ok.txt", "plain notes about gravity".encode(), "text/plain")).status_code == 201
    assert await db.documents.count_documents({}) == 1  # rejected uploads leave no records


async def test_free_plan_document_limit(client):
    await register(client)
    for i in range(3):
        assert (await _upload(client, f"n{i}.txt", f"notes number {i} about topic".encode(), "text/plain")).status_code == 201
    r = await _upload(client, "n4.txt", b"one too many documents here", "text/plain")
    assert r.status_code == 402 and r.json()["error"]["code"] == "document_limit"


async def test_cross_user_document_isolation(make_client):
    a, b = await make_client(), await make_client()
    await register(a)
    await register(b)
    d = (await _upload(a, "private.pdf", make_pdf(PHOTO_PAGES))).json()
    assert (await b.get(f"/api/v1/documents/{d['id']}")).status_code == 404
    assert (await b.get(f"/api/v1/documents/{d['id']}/passages")).status_code == 404
    assert (await b.delete(f"/api/v1/documents/{d['id']}")).status_code == 404
    assert (await b.post(f"/api/v1/documents/{d['id']}/reindex")).status_code == 404
    assert (await b.get("/api/v1/documents")).json()["total"] == 0
    assert (await a.get(f"/api/v1/documents/{d['id']}")).status_code == 200  # owner unaffected
    assert (await b.get("/api/v1/documents/not-an-id")).status_code in (404, 422)


async def test_unauthenticated_document_access(client):
    assert (await client.get("/api/v1/documents")).status_code == 401
    assert (await _upload(client, "a.txt", b"hello world text", "text/plain")).status_code == 401


async def test_reindex_keeps_chunks(client, db):
    await register(client)
    d = (await _upload(client, "h.pdf", make_pdf(HISTORY_PAGES))).json()
    r = await client.post(f"/api/v1/documents/{d['id']}/reindex")
    assert r.status_code == 200 and r.json()["chunk_count"] == d["chunk_count"]


async def test_missing_embedding_config_returns_clear_error(db, razorpay, llm):
    import httpx
    from app.main import create_app
    app = create_app(make_settings(embedding_provider=""), db=db, razorpay=razorpay, llm=llm)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        await register(c)
        r = await c.post("/api/v1/documents", files={"file": ("a.txt", b"some real text content", "text/plain")})
        assert r.status_code == 503 and r.json()["error"]["code"] == "not_configured"
        assert await db.documents.count_documents({}) == 0
