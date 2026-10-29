"""Rebuild this machine's Neo4j graph from the documents and chunks already stored in MongoDB.

Use it when your local Neo4j is out of date (for example, a teammate uploaded or deleted
documents from their own backend, which only updated *their* local Neo4j).

    python -m scripts.resync_graph                 # dry run: shows what would happen
    python -m scripts.resync_graph --apply         # sync every MongoDB document into Neo4j
    python -m scripts.resync_graph --apply --clean # ...and remove Neo4j documents no longer in MongoDB

Nothing is re-uploaded, re-chunked or re-embedded: PDFs are not downloaded and MongoDB is not
changed, except each document's graph_sync_status / graph_sync_error (same as a normal ingest).
If GROQ_API_KEY is not set, entity extraction is skipped and only Document, Chunk and Topic
links are created.
"""

import os
import sys
import time

from database.connection import documents_chunk_collection, documents_collection
from database.neo4j_connection import NEO4J_DATABASE, close_neo4j_connection, get_neo4j_driver
from services import graph_service
from services.rag_service import sync_document_graph


def _neo4j_document_uuids() -> dict:
    """document_uuid -> document_name for every Document node in Neo4j."""

    with get_neo4j_driver().session(database=NEO4J_DATABASE) as session:
        records = session.run(
            "MATCH (d:Document) RETURN d.document_uuid AS uuid, d.document_name AS name"
        )
        return {record["uuid"]: record["name"] for record in records}


def main(apply: bool, clean: bool) -> None:
    if not os.getenv("GROQ_API_KEY"):
        # Without a key every Groq call fails after retries; skip it to save time.
        graph_service.extract_from_chunks = lambda chunks: {"entities": [], "relations": []}
        print("GROQ_API_KEY not set: entity extraction skipped (topic links only).\n")

    if apply:
        graph_service.initialize_graph()  # constraints and indexes; safe to run again

    documents = list(documents_collection.find({}, {"_id": 0}))
    mongo_uuids = {d["document_uuid"] for d in documents if d.get("document_uuid")}
    neo4j_docs = _neo4j_document_uuids()

    synced, failed, skipped = 0, 0, 0

    for document in documents:
        name = document.get("document_name") or document.get("document_uuid")
        chunks = list(documents_chunk_collection.find(
            {"document_uuid": document.get("document_uuid")},
            {"_id": 0, "embedding": 0},
        ))

        if not chunks:
            print(f"- skip   {name}: no chunks in MongoDB (not ingested yet)")
            skipped += 1
            continue

        if not apply:
            print(f"- sync   {name}: {len(chunks)} chunk(s)")
            continue

        started = time.time()
        result = sync_document_graph(document, chunks)

        if result.get("graph_sync_status") == "indexed":
            synced += 1
            print(f"OK       {name}: {len(chunks)} chunk(s) in {time.time() - started:.1f}s")
        else:
            failed += 1
            print(f"FAILED   {name}: {result.get('graph_sync_error')}")

    stale = {uuid: name for uuid, name in neo4j_docs.items() if uuid not in mongo_uuids}

    for uuid, name in stale.items():
        if apply and clean:
            graph_service.delete_document_from_graph(uuid)
            print(f"REMOVED  {name} (not in MongoDB)")
        else:
            print(f"- stale  {name} (in Neo4j, not in MongoDB){'' if clean else ' -> use --clean to remove'}")

    print()
    if apply:
        print(f"Done: {synced} synced, {failed} failed, {skipped} skipped, "
              f"{len(stale) if clean else 0} stale removed.")
    else:
        print(f"Dry run: {len(documents) - skipped} to sync, {skipped} skipped, {len(stale)} stale in Neo4j. "
              "Re-run with --apply (add --clean to remove stale ones).")

    close_neo4j_connection()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv, clean="--clean" in sys.argv)
