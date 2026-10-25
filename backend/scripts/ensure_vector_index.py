"""Make the Atlas vector index able to pre-filter on the access fields.

    python -m scripts.ensure_vector_index            # show what would change
    python -m scripts.ensure_vector_index --apply    # create / update the index

The index keeps its name (`vector_index`) and its existing vector settings; only missing filter
fields are added. Atlas rebuilds in the background; queries keep using the old definition until the
rebuild finishes, but the new access filter only works once the index is READY (a minute or two).
"""

import sys

from pymongo.operations import SearchIndexModel

from database.connection import documents_chunk_collection as chunks
from services.embedding_service import EMBEDDING_DIM
from services.retrieval_service import VECTOR_INDEX_NAME

FILTER_PATHS = [
    "classification",
    "department_code",
    "access.users",
    "access.roles",
    "access.departments",
    "document_uuid",
]

DEFAULT_VECTOR_FIELD = {"type": "vector", "path": "embedding", "numDimensions": EMBEDDING_DIM, "similarity": "cosine"}


def wanted_definition(existing: dict | None) -> dict:
    fields = list((existing or {}).get("fields") or [DEFAULT_VECTOR_FIELD])
    have = {f["path"] for f in fields if f.get("type") == "filter"}
    fields += [{"type": "filter", "path": p} for p in FILTER_PATHS if p not in have]
    return {"fields": fields}


def main(apply: bool) -> None:
    current = next((i for i in chunks.list_search_indexes() if i["name"] == VECTOR_INDEX_NAME), None)
    existing = (current or {}).get("latestDefinition")
    definition = wanted_definition(existing)

    missing = [f["path"] for f in definition["fields"] if f.get("type") == "filter"
               and f["path"] not in {x["path"] for x in (existing or {}).get("fields", []) if x.get("type") == "filter"}]

    if current and not missing:
        print(f"'{VECTOR_INDEX_NAME}' already filters on every access field (status: {current.get('status')}).")
        return

    print(f"'{VECTOR_INDEX_NAME}': {'update' if current else 'create'}; filter fields to add: {missing}")

    if not apply:
        print("Nothing changed. Re-run with --apply.")
        return

    if current:
        chunks.update_search_index(VECTOR_INDEX_NAME, definition)
    else:
        chunks.create_search_index(SearchIndexModel(definition=definition, name=VECTOR_INDEX_NAME, type="vectorSearch"))

    print("Submitted. Wait until the index status is READY, then ask a question.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
