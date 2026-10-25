"""Copy each document's access fields onto its chunks (needed once for chunks created before the org model).

    python -m scripts.sync_chunk_access            # dry run
    python -m scripts.sync_chunk_access --apply

Embeddings are not touched, so nothing is re-processed. Chunks of documents that no longer exist are reported.
"""

import sys

from database.connection import documents_chunk_collection, documents_collection
from services.rag_service import chunk_access_fields


def main(apply: bool) -> None:
    documents = {d["document_uuid"]: d for d in documents_collection.find({}, {"_id": 0})}
    orphans = []
    updated = 0

    for document_uuid in documents_chunk_collection.distinct("document_uuid"):
        document = documents.get(document_uuid)

        if not document:
            orphans.append(document_uuid)
            continue

        fields = chunk_access_fields(document)
        stale = documents_chunk_collection.count_documents({
            "document_uuid": document_uuid,
            "$or": [{k: {"$ne": v}} for k, v in fields.items()],
        })

        print(f"{document['document_name']}: {stale} chunk(s) to update -> {fields['classification']}")

        if apply and stale:
            documents_chunk_collection.update_many({"document_uuid": document_uuid}, {"$set": fields})
        updated += stale

    for document_uuid in orphans:
        print(f"! chunks for missing document {document_uuid} (not changed)")

    print(f"{'Updated' if apply else 'Would update'} {updated} chunk(s).{'' if apply else ' Re-run with --apply.'}")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
