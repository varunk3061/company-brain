"""Upload -> R2 -> ingest -> view -> delete, with R2, embeddings and Neo4j replaced by in-memory fakes."""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from database.connection import documents_chunk_collection, documents_collection
from services import document_service, pdf_service, rag_service, storage_service


def make_pdf(*page_texts: str) -> bytes:
    """Build a small, valid PDF with one text line per page (no extra dependencies)."""

    objects = []
    page_ids = []
    font_id = 3 + 2 * len(page_texts)

    for i, text in enumerate(page_texts):
        page_id, content_id = 3 + 2 * i, 4 + 2 * i
        page_ids.append(page_id)
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode() if text else b""
        objects.append((page_id, f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                                 f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()))
        objects.append((content_id, b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"))

    kids = " ".join(f"{p} 0 R" for p in page_ids)
    objects = [(1, b"<< /Type /Catalog /Pages 2 0 R >>"),
               (2, f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode())] + objects
    objects.append((font_id, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for number, body in sorted(objects):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for number in range(1, len(objects) + 1):
        out += f"{offsets[number]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


@pytest.fixture()
def bucket(monkeypatch):
    """In-memory stand-in for the private R2 bucket."""

    store = {}

    def get(key):
        if key not in store:
            raise HTTPException(status_code=404, detail="The stored file for this document was not found.")
        return store[key]

    monkeypatch.setattr(storage_service, "put_pdf", lambda key, data, content_hash: store.__setitem__(key, data))
    monkeypatch.setattr(storage_service, "get_pdf_bytes", get)
    monkeypatch.setattr(storage_service, "delete_object", lambda key: store.pop(key, None))
    monkeypatch.setattr(storage_service, "presigned_view_url",
                        lambda key, filename, ttl_seconds=300: f"https://r2.example/{key}?sig=1")

    class FakeEmbeddings:
        def embed_documents(self, texts):
            return [[0.1, 0.2, 0.3] for _ in texts]

    monkeypatch.setattr(rag_service, "get_embedding", lambda: FakeEmbeddings())
    monkeypatch.setattr(rag_service, "sync_document_to_graph", lambda document, chunks: None)
    return store


def upload(client, headers, data: bytes, name="Leave Policy.pdf", content_type="application/pdf"):
    return client.post("/api/documents/upload", headers=headers, files={"file": (name, data, content_type)})


def test_upload_requires_documents_manage(client, make_user, bucket):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    assert upload(client, dev, make_pdf("hello")).status_code == 403
    assert client.post("/api/documents/upload", files={"file": ("a.pdf", b"%PDF-", "application/pdf")}).status_code == 401
    assert bucket == {}


def test_upload_stores_in_bucket_registers_and_ingests(client, admin, bucket):
    r = upload(client, admin, make_pdf("Annual leave is 20 days.", "Sick leave is 10 days."))
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["ingestion"]["status"] == "completed"
    doc = body["document"]
    assert doc["document_name"] == "Leave Policy.pdf"
    assert doc["page_count"] == 2 and doc["status"] == "completed" and doc["chunk_count"] == 2
    assert doc["needs_classification"] is True and doc["classification"] == "internal"
    assert "object_key" not in doc and "content_hash" not in doc  # internal fields never leave the API

    stored = documents_collection.find_one({"document_uuid": doc["document_uuid"]})
    assert stored["object_key"] == f"documents/{doc['document_uuid']}.pdf"
    assert set(bucket) == {stored["object_key"]}
    assert stored["size_bytes"] == len(bucket[stored["object_key"]])
    assert len(stored["content_hash"]) == 64 and "file_path" not in stored

    chunks = list(documents_chunk_collection.find({"document_uuid": doc["document_uuid"]}).sort("page", 1))
    assert [c["page"] for c in chunks] == [1, 2]
    assert "Annual leave" in chunks[0]["text"]
    # Chunks carry the access fields the vector-search permission filter needs.
    assert all(c["classification"] == "internal" and "department_code" in c and "access" in c for c in chunks)
    assert all("file_path" not in c for c in chunks)


def test_upload_rejects_non_pdf_bad_and_oversized_files(client, admin, bucket, monkeypatch):
    assert upload(client, admin, b"hello", name="notes.txt", content_type="text/plain").status_code == 415
    assert upload(client, admin, b"not really a pdf", name="fake.pdf").status_code == 415
    assert upload(client, admin, b"%PDF-1.4 garbage", name="broken.pdf").status_code == 422
    assert upload(client, admin, b"", name="empty.pdf").status_code == 422

    monkeypatch.setattr(document_service, "MAX_UPLOAD_BYTES", 100)
    assert upload(client, admin, make_pdf("x" * 50)).status_code == 413

    assert bucket == {} and documents_collection.count_documents({}) == 0


def test_same_content_cannot_be_uploaded_twice(client, admin, bucket):
    data = make_pdf("Dress code is business casual.")
    assert upload(client, admin, data).status_code == 201
    r = upload(client, admin, data, name="Copy of policy.pdf")
    assert r.status_code == 409 and "Leave Policy.pdf" in r.json()["detail"]
    assert len(bucket) == 1 and documents_collection.count_documents({}) == 1


def test_reingest_reads_from_the_bucket_without_reupload(client, admin, bucket):
    uuid = upload(client, admin, make_pdf("Travel costs need approval.")).json()["document"]["document_uuid"]

    r = client.post(f"/api/documents/{uuid}/ingest", headers=admin)
    assert r.status_code == 200 and r.json()["message"] == "Document is already up to date."

    # Force a rebuild (e.g. after changing chunk settings): the PDF comes from the bucket again.
    documents_collection.update_one({"document_uuid": uuid}, {"$set": {"file_hash": None}})
    documents_chunk_collection.delete_many({"document_uuid": uuid})
    r = client.post(f"/api/documents/{uuid}/ingest", headers=admin)
    assert r.status_code == 200 and r.json()["chunk_count"] == 1
    assert documents_chunk_collection.count_documents({"document_uuid": uuid}) == 1


def test_pdf_without_text_is_stored_but_marked_failed(client, admin, bucket):
    r = upload(client, admin, make_pdf(""), name="scan.pdf")
    assert r.status_code == 201
    assert r.json()["ingestion"]["status"] == "failed"
    assert r.json()["document"]["status"] == "failed"
    assert len(bucket) == 1  # kept, so it can be re-ingested later without uploading again


def test_delete_removes_bucket_object_record_and_chunks(client, admin, bucket):
    uuid = upload(client, admin, make_pdf("Hazard reporting.")).json()["document"]["document_uuid"]
    assert client.delete(f"/api/documents/{uuid}", headers=admin).status_code == 200
    assert bucket == {}
    assert documents_collection.count_documents({"document_uuid": uuid}) == 0
    assert documents_chunk_collection.count_documents({"document_uuid": uuid}) == 0


def test_view_url_follows_the_visibility_rule(client, admin, make_user, bucket):
    _, dev = make_user("dev@nexora.com", "IT", "DEVELOPER")
    uuid = upload(client, admin, make_pdf("Holiday calendar.")).json()["document"]["document_uuid"]

    r = client.get(f"/api/documents/{uuid}/view-url", headers=dev)  # internal: any signed-in user
    assert r.status_code == 200
    assert r.json() == {"url": f"https://r2.example/documents/{uuid}.pdf?sig=1", "expires_in": 300}

    client.patch(f"/api/documents/{uuid}/access", headers=admin,
                 json={"department_code": "FIN", "classification": "restricted", "access": {"roles": ["CEO"]}})

    # Not allowed looks exactly like "does not exist"; admin rights manage documents but don't grant reading.
    for headers in (dev, admin):
        r = client.get(f"/api/documents/{uuid}/view-url", headers=headers)
        assert r.status_code == 404 and r.json() == {"detail": "Document not found."}
    assert client.get("/api/documents/missing/view-url", headers=dev).status_code == 404
    assert client.get(f"/api/documents/{uuid}/view-url").status_code == 401


def test_document_without_r2_object_still_lists_and_deletes(client, admin, bucket):
    documents_collection.insert_one({
        "document_uuid": "legacy", "document_name": "old.pdf", "file_path": "/x/old.pdf",
        "classification": "internal", "access": {"departments": [], "roles": [], "users": []},
        "last_update": datetime.now(timezone.utc),
    })
    names = {d["document_name"] for d in client.get("/api/documents/", headers=admin).json()}
    assert "old.pdf" in names
    assert client.get("/api/documents/legacy/view-url", headers=admin).status_code == 409
    assert client.delete("/api/documents/legacy", headers=admin).status_code == 200


def test_presigned_url_is_short_lived_inline_and_scoped_to_the_key(monkeypatch):
    monkeypatch.setattr(storage_service, "R2_ACCOUNT_ID", "acct123")
    monkeypatch.setattr(storage_service, "R2_ACCESS_KEY_ID", "AKIDEXAMPLE")
    monkeypatch.setattr(storage_service, "R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(storage_service, "R2_BUCKET", "company-brain-docs")
    monkeypatch.setattr(storage_service, "_client", None)

    url = storage_service.presigned_view_url("documents/abc.pdf", "Leave Policy.pdf", ttl_seconds=300)
    assert url.startswith("https://acct123.r2.cloudflarestorage.com/company-brain-docs/documents/abc.pdf?")
    assert "X-Amz-Expires=300" in url and "response-content-disposition=inline" in url
    assert "secret" not in url
    monkeypatch.setattr(storage_service, "_client", None)


def test_missing_r2_settings_fail_with_a_safe_message(monkeypatch):
    monkeypatch.setattr(storage_service, "R2_BUCKET", "")
    monkeypatch.setattr(storage_service, "_client", None)
    with pytest.raises(HTTPException) as exc:
        storage_service.get_pdf_bytes("documents/x.pdf")
    assert exc.value.status_code == 500 and exc.value.detail == "Document storage is not configured."


def test_pdf_reader_extracts_pages_and_metadata():
    content = pdf_service.read_pdf(make_pdf("one", "two", "three"))
    assert content.page_count == 3 and [p.strip() for p in content.pages] == ["one", "two", "three"]
    assert set(content.metadata) == {"title", "author", "created_at"}
