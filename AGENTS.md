# The Company Brain

A permission-aware, trust-aware question-answering system over a company's internal documents.

Unlike a naive "company chatbot", the Company Brain:

- **connects facts across documents** (vector index + knowledge graph), including company-wide summary questions
- **never leaks** — answers are built only from evidence the asking user is allowed to see
- **trusts only validated content** — drafts, superseded versions and unapproved files are never used as truth
- **cites its sources** and says **"I don't know"** when it should

> Source of requirements: [`Documents/The Company Brain Assignment Brief.pdf`](Documents/) and
> [`Documents/The Company Brain Detailed Assignment.pdf`](Documents/). Read those first; this file
> describes how the repository implements them.

| Part | Doc |
|------|-----|
| Backend (FastAPI, MongoDB, retrieval, security) | [backend/AGENTS.md](backend/AGENTS.md) |
| Frontend (Next.js admin portal + employee chat) | [frontend/AGENTS.md](frontend/AGENTS.md) |

---

## 1. Architecture

```
┌──────────────────────┐      HTTPS / JSON + Bearer JWT      ┌──────────────────────────┐
│  Next.js frontend    │ ─────────────────────────────────▶  │  FastAPI backend         │
│  - Login             │                                     │  - Auth & RBAC/ABAC      │
│  - Admin portal      │                                     │  - Document lifecycle    │
│  - Employee chat     │                                     │  - Retrieval + answering │
└──────────────────────┘                                     │  - Audit log             │
                                                             └────────────┬─────────────┘
         ┌──────────────────────┐                                         │
         │  MCP client (other   │ ── MCP (same auth + same rules) ───────▶│
         │  AI assistants)      │                                         ▼
         └──────────────────────┘                             ┌──────────────────────────┐
                                                              │ MongoDB                  │
                                                              │ users, documents, chunks │
                                                              │ (vectors), entities,     │
                                                              │ edges, summaries,        │
                                                              │ audit_log, eval_runs     │
                                                              └──────────────────────────┘
                                                                          │
                                                              LLM + embedding API (raw calls)
```

### Write path — document → knowledge

1. Upload creates a **Draft**
2. Automated validation checks (parse quality, duplicates, PII/secrets, classification consistency, prompt-injection, metadata)
3. Authorised reviewer **approves** (e.g. department head for department docs, Legal for contracts)
4. **Indexing**: chunks + embeddings, entities + relations — each carrying a copy of the document's access rules and evidence
5. A later change creates a **new version**; the old one is **Superseded** and the index is updated

States: `Draft → Submitted → Auto-validated → Approved → Indexed → Superseded | Archived`. Failures go to `Quarantine` with reasons visible to the owner.

### Read path — question → answer

1. Authenticate, load the user's **current** permissions (no cached grants)
2. Query guard (injection, out-of-scope)
3. Router picks a retrieval method
4. Retrieve **with the permission filter inside the query** (pre-filter, never post-filter top-k)
5. Rerank / graph traversal
6. Generate from permitted evidence only, with citations
7. Output guard (claims supported, nothing restricted slipped in)
8. Audit: who asked, what was retrieved, what was returned

**Invariant:** no step on the read path may see a chunk, node, edge or summary the user is not allowed to see.

---

## 2. Non-negotiable rules (MUST)

These apply to every PR. A change that breaks one of them is rejected regardless of other merit.

1. **Deny by default**, enforced **server-side**, **before** the LLM sees anything.
2. **One authorisation path** for every entry point — UI, REST API and MCP.
3. **Revocation is immediate** — role change, department move, project removal or deactivation takes effect on the next request.
4. **Every query is audited.**
5. **No secrets in the repo.** Config comes from environment variables; commit only `.env.example`.
6. **No LangChain / LlamaIndex in the baseline.** Raw API calls + MongoDB first; a framework may be added later only with a decision-log entry explaining what it hides.
7. **Every design decision is backed by an experiment** recorded in the decision log.
8. **You can explain every line you commit.**

---

## 3. Repository layout

```
company_brain/
├── backend/            FastAPI service (see backend/AGENTS.md)
├── frontend/           Next.js app (see frontend/AGENTS.md)
├── Documents/          Assignment brief + detailed assignment (requirements)
├── reports/            Generated artefacts (org chart, eval reports, red-team reports)
├── README.md           Project overview, setup and admin-portal features
└── AGENTS.md           This file
```

Planned top-level folders as the project grows:

```
├── docs/
│   ├── research/       Research notes (1–2 pages each, own words, sources cited)
│   ├── decisions/      Decision log — one file per decision (ADR format, see §6)
│   ├── ai-usage-log.md Daily: what was asked, what was wrong, what was fixed
│   └── design.md       Design doc (architecture, schema, access model, top risks)
├── eval/               Question sets, eval harness, red-team matrix, results
└── experiments/        Throwaway notebooks/scripts — never imported by app code
```

---

## 4. Quick start (local development)

**Prerequisites:** Python 3.11+, Node.js 20+, MongoDB 7+ (local or Atlas; Atlas is required for `$vectorSearch`).

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in values — see backend/AGENTS.md
uvicorn main:app --reload --port 8000
```

```bash
# 2. Frontend (new terminal)
cd frontend
npm ci
npm run dev                 # http://localhost:3000
```

API docs: http://127.0.0.1:8000/docs (Swagger) · http://127.0.0.1:8000/redoc

---

## 5. Current status

| Part (from brief) | Status | Notes |
|---|---|---|
| 1. Platform — auth, users, departments, roles | 🟢 Done (v1) | Unified `users`, 6 departments + 19 roles from `Documents/orgChart.docx`, role-based permissions, one login |
| 1. Platform — documents CRUD, versions | 🟡 Partial | Folder scan registers PDFs; owner dept + classification + explicit grants enforced on listing; delete. No upload/versioning yet |
| 1. Platform — approval workflow | 🔴 Not started | |
| 1. Platform — audit trail | 🟡 Partial | Admin changes (users, org, document access, views) and `rag.ask` are written to `audit_log`; admin viewer at `/admin/audit-logs` with action/actor filters and per-action colour tags. Full query audit (retrieved chunks, guard flags) not yet |
| 2. Document validation pipeline | 🔴 Not started | |
| 3. Knowledge layer — vector index | 🟡 Baseline | PDFs are chunked and embedded (MiniLM, 384-d) into `documents_chunk` with a copy of their access fields; Atlas `vector_index` pre-filters on them |
| 3. Knowledge layer — knowledge graph | 🔴 Not started | |
| 4. Question answering + router | 🟡 Baseline | `POST /api/rag/ask`: permission-filtered vector retrieval + Groq answer with citations. Single method, no router/rerank/"I don't know" calibration yet |
| 5. Proof — eval harness, red-team suite | 🔴 Not started | |
| MCP server | 🔴 Not started | |

Keep this table up to date in the PR that changes it.

**Admin portal UI (latest changes).** Row actions in Users and Documents are icon buttons (`lucide-react`, with tooltips); Documents shows explicit access grouped as Departments / Roles / Users, has an eye icon to preview the stored PDF in a modal (short-lived presigned link from the backend), and filters by title, owner department, classification and access department; Users filters by name/email and department; Audit Logs filters by action and actor and colours each action differently; all dates use one compact format (`28 Oct 2026` / `08:08 PM`). Details: `frontend/AGENTS.md` §5b, `backend/AGENTS.md` §4 (Audit).

---

## 6. Engineering workflow

### Branching & PRs

- `development` is the integration branch. Never commit to it directly.
- Branch names: `feature/<short-desc>`, `fix/<short-desc>`, `chore/<short-desc>`, `exp/<short-desc>`.
- Every PR: one logical change, description of **what** and **why**, linked decision-log entry if it changes a design choice, and a reviewer **from another track**.
- A PR touching access control, retrieval filters or the MCP server must add/extend a red-team test.

### Commits

[Conventional Commits](https://www.conventionalcommits.org/): `feat(backend): add document versioning`, `fix(frontend): clear token on 401`, `test(eval): add multi-hop questions`.

### Decision log (ADR)

One file per decision in `docs/decisions/NNNN-title.md`:

```
Context → Options → Experiment → Numbers → Decision → What would change my mind
```

### Definition of done

- [ ] Code reviewed and approved
- [ ] Lint + tests pass locally (`ruff`/`pytest` for backend, `npm run lint`/`npm run build` for frontend)
- [ ] New behaviour covered by a test; access-sensitive behaviour covered by a red-team case
- [ ] No secrets, no `console.log`/`print` debugging left behind
- [ ] Docs (this file, backend/frontend AGENTS.md, status table) updated
- [ ] Eval numbers recorded if retrieval/answering changed

---

## 7. Evaluation & security proof

- **Question set:** 30 given + 30 written by the team, across six types — single-document, multi-hop, global/summary, time/version, unanswerable, access-sensitive. Each stores expected answer + supporting doc ids.
- **Metrics:** correctness, faithfulness, recall@k / precision, abstention accuracy, latency, cost per query, indexing cost, **leakage**.
- **Red-team matrix:** users × questions with expected `ALLOW` / `DENY`. Report **leak rate (target 0)** and **over-block rate**. Runs automatically on every change.
- **Method comparison matrix** → conclusions implemented as the router ("use method X for question type Y because of these numbers").

---

## 8. Milestones

| Date | Due |
|---|---|
| Tue 13 Oct | Research notes, design doc v0, repo ready |
| Fri 16 Oct | Checkpoint 1: secure CRUD + baseline RAG, first scores |
| Fri 23 Oct | Checkpoint 2 + midpoint viva: validation pipeline, improved retrieval, graph prototype |
| Thu 29 Oct | **Code freeze** — mentors run hidden questions and attacks |
| Fri 30 Oct | Final demo (10 min) + viva |

## 9. Deliverables

1. Working app (this repo)
2. Research notes, decision log, AI usage log
3. Evaluation results + retrieval-method comparison
4. Red-team report on access control
5. 10-minute demo + viva
