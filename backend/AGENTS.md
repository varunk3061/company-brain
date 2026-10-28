# Company Brain — Backend

FastAPI + MongoDB service that owns **authentication, authorisation, the document lifecycle, retrieval, answer generation and auditing**. It is the only component allowed to decide what a user may see.

See the [project AGENTS.md](../AGENTS.md) for the overall architecture and the MUST rules.

---

## 1. Tech stack

| Concern | Choice |
|---|---|
| Framework | FastAPI (ASGI), served by Uvicorn |
| Language | Python 3.11+ |
| Database | MongoDB (PyMongo). Atlas required for `$vectorSearch` |
| Validation | Pydantic v2 (`extra="forbid"` on all request models) |
| Auth | JWT (python-jose, HS256) via `Authorization: Bearer <token>` |
| Passwords | bcrypt (`bcrypt` package directly) — max 72 UTF-8 bytes, min 12 characters |
| Config | Environment variables loaded with python-dotenv |
| LLM / embeddings | Raw HTTP/SDK calls — **no LangChain / LlamaIndex in the baseline** |

---

## 2. Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # fill in real values
uvicorn main:app --reload --port 8000
```

- Swagger UI: http://127.0.0.1:8000/docs
- Health: `GET /` returns a running message

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `MONGODB_URI` | ✅ | MongoDB connection string |
| `DATABASE_NAME` | ✅ | Database name |
| `JWT_SECRET_KEY` | ✅ | ≥ 32 random characters (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) |
| `JWT_ALGORITHM` | | Default `HS256` |
| `CORS_ORIGINS` | | Comma-separated origins; default `http://localhost:3000,http://127.0.0.1:3000` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | | Default `60` |
| `ADMIN_NAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | ✅ (new installs) | Seed System Administrator (password ≥ 12 chars), created at startup only if no `users` admin **and** no legacy `admins` rows exist |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | ✅ for uploads | Private Cloudflare R2 bucket holding uploaded PDFs. API token: *Object Read & Write*, scoped to this bucket. Keys stay on the backend |
| `MAX_UPLOAD_MB` | | Per-PDF upload limit; default `25` (keep `MAX_UPLOAD_MB` in `frontend/src/services/documentService.js` in step) |
| `PRESIGNED_URL_TTL_SECONDS` | | Lifetime of "view PDF" links; default `300` (R2 max 7 days) |
| `DOCUMENTS_ROOT` | legacy | Absolute path; only for the old server-side folder scan |
| `GROQ_API_KEY`, `GROQ_MODEL` | ✅ for answers | Groq LLM used by `/api/rag/ask` (model defaults to `openai/gpt-oss-120b`) |

The app **fails fast** at import time if required values are missing or weak. Never commit `.env`; keep `.env.example` in sync whenever you add a variable.

### First start and migrating an existing database

On startup the app checks Mongo, creates indexes and seeds the departments/roles (insert-only, never overwrites edits). A brand-new install also creates the first System Administrator from `.env`.

If you already have data in the legacy `admins` / `employee` collections:

```bash
python -m scripts.migrate_users            # dry run: prints what would happen, writes nothing
python -m scripts.migrate_users --apply
```

Password hashes and UUIDs are preserved, so existing logins keep working. Users whose legacy department does not match their role's department (or in the dropped `Support` department) are **not imported** and are listed in the report — recreate them in the Users page. Migrated documents get `classification=internal`, no owner department and `needs_classification=true`; legacy `allowed_roles` are mapped into `access.roles` where possible and left in place otherwise.

---

## 3. Project structure

```
backend/
├── main.py              App: routers, CORS, lifespan (DB ping, indexes, org seed, first admin)
├── database/connection.py   Mongo client, collection handles, indexes
├── models/              Pydantic request/response models (the API contract)
├── routes/              HTTP layer: auth, org, users, documents, dashboard
├── services/
│   ├── access/policy.py     THE visibility rule: can_view / build_document_filter / UserContext
│   ├── org_seed.py          Departments + roles from Documents/orgChart.docx
│   ├── org_service.py, user_service.py, document_service.py, dashboard_service.py
│   └── audit_service.py     Append-only admin change log
├── utils/
│   ├── auth.py          Token creation, get_current_user, require_permission(...)
│   └── security.py      Settings, password hashing
├── scripts/migrate_users.py  Legacy admins/employee -> users (dry-run by default)
├── tests/               pytest (mongomock, no real database needed)
└── requirements.txt / requirements-dev.txt
```

### Layering rules

```
routes  ──▶  services  ──▶  database
   │            │
   └── models ◀─┘        utils (auth/security) used by routes via Depends()
```

- **Routes** contain no business logic and no direct DB queries. Every non-public route declares `get_current_user` or `require_permission("...")`.
- **Services** contain logic and DB access; they raise `HTTPException` with safe, generic messages.
- **Models** define every request and response. Responses use explicit models/projections — never return raw Mongo documents (no `_id`, `password_hash`, `file_path`).
- New subsystems get their own module per layer, e.g. `routes/chat_routes.py`, `services/retrieval/`, `services/ingestion/`, `services/graph/`, `services/audit_service.py`, `mcp/`.

Planned modules as the brief is implemented:

```
services/
├── ingestion/     parse → chunk → embed → extract entities/relations
├── validation/    automated checks, state machine, quarantine
├── access/        single policy engine: build_access_filter(user) → Mongo filter
├── retrieval/     dense, sparse (BM25), hybrid (RRF), rerank, graph traversal, router
├── answering/     prompt building, citation verification, output guard
└── audit_service.py
mcp/               MCP server exposing search/ask through the same access layer
eval/              (repo root) harness + red-team suite
```

---

## 4. API reference (current)

All routes except the two login endpoints and `/` require a Bearer token.

### Auth

| Method | Path | Who | Description |
|---|---|---|---|
| POST | `/auth/login` | public | Any user → `{access_token, token_type, expires_in, user{name, role_name, department_code, permissions[]}}`. Blocked accounts get 403 |
| GET | `/auth/me` | signed in | Current user (name, department, role, clearance, permissions), read fresh from the DB |

Tokens carry the user id only. Role, clearance and permissions are re-read on **every** request, so blocking a user or changing a role/grant applies on the next call.

### Organisation

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/departments`, `/roles?department_code=` | signed in | Read the org tree (for dropdowns and names) |
| POST / PUT | `/departments`, `/departments/{code}` | `org.manage` | Create / rename / (de)activate. Cannot deactivate with active users |
| POST / PUT | `/roles`, `/roles/{code}` | `org.manage` | Create / change clearance, permissions, status. Cannot remove the last user-management role |

### Question answering

| Method | Path | Permission | Description |
|---|---|---|---|
| POST | `/api/rag/ask` | signed in | `{question}` → `{answer, sources[{source, page, document_uuid}]}`. Retrieval is permission-filtered **inside** the `$vectorSearch` query; with no permitted evidence the LLM is not called and the answer is "I could not find this information in the accessible documents." |
| POST | `/api/documents/upload` | `documents.manage` | multipart `file` (one PDF ≤ `MAX_UPLOAD_MB`) → stored in R2 as `documents/<uuid>.pdf`, registered (`internal`, `needs_classification`), then chunked + embedded. 413 too large · 415 not a PDF · 422 unreadable/password-protected · 409 same content already uploaded. An ingestion failure is returned in `ingestion` (the file stays stored) |
| GET | `/api/documents/{uuid}/view-url` | signed in | `{url, expires_in}`: presigned R2 link to the original PDF. Uses `can_view` (admins included); **404** when not allowed, identical to "not found" |
| POST | `/api/documents/scan-and-ingest` | `documents.manage` | Legacy: register PDFs in a server folder, then chunk + embed them |
| POST | `/api/documents/{uuid}/ingest` | `documents.manage` | (Re)process one registered PDF; uploaded PDFs are re-read from R2 (no re-upload) |

**How it fits together.** `services/rag_service.py` (ingest) → `documents_chunk` (text, `embedding`, `classification`, `department_code`, `access`) → `services/retrieval_service.py` (`$vectorSearch` with `build_document_filter(ctx)`) → `services/llm_service.py` (Groq, cites `[Source: file, Page: N]`). Changing a document's access updates its chunks; deleting a document deletes them.

**One-time setup per Atlas cluster.** The vector index must be able to filter on the access fields:

```bash
python -m scripts.ensure_vector_index            # preview
python -m scripts.ensure_vector_index --apply    # create/update `vector_index` (wait for READY)
python -m scripts.sync_chunk_access --apply      # backfill access fields on chunks made before the org model
```

Heavy packages (LangChain, sentence-transformers, torch) are imported only when first used, so the API and the test-suite start without them; `pip install -r requirements.txt` installs them (use the CPU torch wheel: `pip install torch --index-url https://download.pytorch.org/whl/cpu` first).

### Audit (`audit.read`)

| Method | Path | Description |
|---|---|---|
| GET | `/audit-logs?page&page_size&action&actor` | Admin change history, newest first: time, actor name, action, target (before/after payloads are not exposed). Optional filters: `action` = exact action (e.g. `user.create`); `actor` = part of the actor's name or email, case-insensitive (`system` also matches system actions). `total` counts filtered rows; `actions` lists every recorded action (for the UI dropdown) |

### Users (`users.manage`)

| Method | Path | Description |
|---|---|---|
| POST | `/users` | Create (role must belong to the department; password 12–72 chars) |
| GET | `/users?page&page_size&department_code&role_code&status` | Paginated list (`page_size` ≤ 100) |
| GET / PUT / DELETE | `/users/{user_uuid}` | Read / change name, department, role, status / delete. Blocks self-lockout and removing the last administrator |
| GET | `/admin/dashboard` | Stats + recent activity |

### Documents

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/documents/` | signed in | Documents the caller may see (managers see all metadata, never content) |
| POST | `/api/documents/scan-folder` | `documents.manage` | Legacy: register PDFs under `DOCUMENTS_ROOT` as `internal`, `needs_classification` |
| PATCH | `/api/documents/{uuid}/access` | `documents.manage` | Set owner department, classification, explicit grants |
| DELETE | `/api/documents/{uuid}` | `documents.manage` | Delete the record |

**Convention for new endpoints:** prefix with `/api/v1/`, plural nouns, `kebab-case` paths, `snake_case` JSON. Current routes are unversioned; move them under `/api/v1` in one PR together with the frontend.

### Error format

FastAPI default: `{"detail": "<message>"}`. Rules:

- Login failures always say `Invalid email or password` (no user enumeration).
- Access-denied on content must not confirm the content exists — see §6.
- Never put stack traces, file paths, query text or Mongo errors in responses.

---

## 5. Data model

Implemented collections: `departments`, `roles`, `users`, `documents`, `audit_log` (legacy `admins`, `employee` are read only by the migration script). Still to build from the target model: `chunks`, `entities`, `edges`, `summaries`, `eval_runs`, query audit.

| Collection | Fields (implemented) |
|---|---|
| `departments` | `department_uuid`, `code` (unique), `name`, `status` |
| `roles` | `role_uuid`, `code` (unique), `name`, `department_code`, `clearance`, `permissions[]`, `status` |
| `users` | `user_uuid`, `name`, `email` (unique), `password_hash`, `department_code`, `role_code`, `status` |
| `documents` | `document_uuid`, `document_name`, `object_key` (internal, R2 key `documents/<uuid>.pdf`), `content_hash` (SHA-256, unique when present), `size_bytes`, `page_count`, `pdf_metadata{title, author, created_at}`, `uploaded_by`, `department_code` (owner), `classification`, `access{departments[], roles[], users[]}`, `needs_classification`, `status`, `chunk_count`, `last_update`. Legacy folder-scan rows have `file_path` (internal) instead of `object_key` |
| `audit_log` | `ts`, `actor_uuid`, `action`, `target`, `before`, `after` |

Target model for the remaining collections (change it, but record why):

| Collection | Key fields |
|---|---|
| `users` (later) | `project_ids[]`, `manager_id`, `level` |
| `documents` (later) | `doc_type`, `status`, `trust_tier`, `version`, `supersedes`, `owner_id`, `valid_from`, `valid_to`, `validation{checks[], approved_by, approved_at}`, `content_hash` |
| `chunks` | `doc_id`, `doc_version`, `text`, `context_prefix`, `position{page, section}`, `embedding[]`, **`access{…copied from document}`**, `status` |
| `entities` | `type`, `canonical_name`, `aliases[]`, `attributes{}`, `evidence[{doc_id, chunk_id}]` |
| `edges` | `from`, `to`, `type`, `evidence[{doc_id, chunk_id, confidence}]`, `valid_from`, `valid_to` |
| `summaries` | `level`, `entity_ids[]`, `text`, `source_doc_ids[]`, `access{…}` |
| `audit_log` (queries) | `ts`, `user_id`, `query`, `method`, `retrieved_chunk_ids[]`, `filtered_out_count`, `guard_flags[]`, `answer_id` |
| `eval_runs` | `config`, `question_id`, `answer`, `scores{}`, `latency_ms`, `cost` |

**Org model.** One user = one department + one job role; a role belongs to exactly one department. Cross-department access comes from document grants, not extra roles. The org tree is seeded from `Documents/orgChart.docx` (6 departments, 19 roles incl. an added IT Manager); each role has a `clearance` (highest classification readable by default) and `permissions[]` (`users.manage`, `org.manage`, `documents.manage`, `documents.approve`, `audit.read`).

**Visibility rule** (`services/access/policy.py`, used by every document query):

| Classification | Visible when |
|---|---|
| `public`, `internal` | any active user |
| `confidential` | explicit grant, **or** same department as the owner and role clearance ≥ confidential |
| `restricted` | explicit grant only (user, role or department in `access`) |

Missing or unknown classification is treated as `restricted`. Admin permissions grant management, not extra reading rights.

Conventions:

- Public identifiers are UUID strings (`*_uuid`); Mongo `_id` never leaves the backend.
- All timestamps are **UTC, timezone-aware**; fields `created_at`, `updated_at`.
- Every query path has an index; unique constraints live in `database/connection.py → create_indexes()`.
- Access fields on `chunks`/`summaries` must be in the vector index's **filter fields** so filtering happens inside `$vectorSearch`.

---

## 6. Security standards

### Access control

- Classification levels: `public`, `internal`, `confidential`, `restricted` (project membership for need-to-know comes later).
- **One function builds the access filter** from the user's *freshly loaded* record. Every retrieval (vector, BM25, graph `$graphLookup`, summaries) and every entry point (REST, chat, MCP) uses it. No other code decides visibility.
- **Pre-filter, never post-filter.** Filtering top-k afterwards both leaks (via counts/latency) and starves recall.
- **Tokens carry identity only**, not permissions. Permissions are re-read from the DB each request so revocation is immediate.
- Derived data (edges, community summaries) gets access rules no broader than its sources; the rule chosen is recorded in the decision log.

### Leak paths every feature must consider

Direct/rephrased questions · aggregates ("how many projects are over budget?") · inference from public + restricted · confirming existence · citations, titles, filenames · shared caches and chat history · graph neighbours/attributes/summaries · error messages · prompt-injection inside documents.

### Prompt injection

A system prompt is not a defence. Document text is **data**: scan at ingestion (validation pipeline), keep it delimited in prompts, and rely on the access filter — the model can only reveal what it was given.

### General

- Validate at the boundary with Pydantic (`extra="forbid"`, length limits, enums for roles/departments/status).
- Passwords: bcrypt, 72-byte cap enforced, never logged or returned.
- Original PDFs live in a **private** R2 bucket (no public r2.dev URL, no custom domain). Only the backend holds the keys; the browser gets 5-minute presigned links, issued after `can_view`. Object keys are built from the UUID, never from the uploaded file name.
- Uploads are validated on the server (size, `%PDF-` header, readable, not password-protected); the frontend check is UX only.
- Legacy folder scans: file system access confined to `DOCUMENTS_ROOT` with resolved-path checks (symlink-safe).
- CORS: explicit origin allow-list from config — no `*` with credentials.
- Rate-limit login and chat endpoints before production.
- The audit log contains user queries; treat it as **confidential** (restricted read access, retention policy).

---

## 7. Coding standards

- **Style:** PEP 8, formatted with `ruff format`, linted with `ruff check`. Type hints on all function signatures.
- **Naming:** `snake_case` functions/variables, `PascalCase` models, `UPPER_SNAKE` constants.
- **Docstrings:** one line saying *why/what*, not restating the code.
- **Config:** read env vars in one place (`utils/security.py` today → a `config.py` settings module); no `os.getenv` scattered through services.
- **Logging:** use `logging`, not `print`. Never log secrets, tokens, passwords or full document text.
- **No dead code:** remove debug scripts and commented-out blocks before merging.
- **Dependencies:** pin versions in `requirements.txt`; add a dependency only when the stdlib or an existing one can't do it.

---

## 8. Testing

```bash
pip install -r requirements-dev.txt
python -m pytest -q          # uses mongomock: no MongoDB needed
```

Current suites in `backend/tests/`:

- `test_policy.py` — access matrix (classification × owner dept × grant type × clearance); `can_view` and `build_document_filter` must agree on every case.
- `test_api.py` — login, permissions, role/department validation, blocked-user and role-change effect on the next request, last-admin protections, end-to-end document visibility and revocation.
- `test_migration.py` — dry run writes nothing, mapping, fail-closed rejects, old passwords still work, idempotent.

Rules:

- Tests never touch the dev/prod database (`MONGODB_URI=mongomock://…` is set in `conftest.py`).
- Every bug fix adds a regression test; every found leak adds a red-team case.
- Eval runs (correctness, faithfulness, recall@k, latency, cost) will be stored in `eval_runs` with their config so results are reproducible.

---

## 9. Known gaps

| Area | Issue |
|---|---|
| Auth | No login rate-limiting, no token revocation list (blocking a user does take effect immediately), HS256 shared secret |
| RAG | Baseline only: one retrieval method (dense), no rerank, hybrid search, router or graph; uses LangChain wrappers for the embedding model and Groq, which the brief asks to avoid in the baseline (log what they hide before keeping them) |
| Documents | No versioning, approval workflow or validation pipeline yet; scanned (image-only) PDFs are stored but not indexed (no OCR); `needs_classification` docs are visible as `internal` until an admin classifies them; deleting a document does not yet remove its Neo4j nodes |
| Audit | Only admin changes are logged (viewable via `/audit-logs`); no query audit yet |
| Org | Roles/departments cannot be deleted (deactivate only); `documents.approve` is stored but not enforced yet |
| API | Routes are not versioned under `/api/v1` yet |
| Ops | Dependencies are unpinned; no CI |
