# The Company Brain

A permission-aware question-answering system over a company's internal documents. An employee asks a question about the company; before answering, the system checks the employee's **department** and **role** against each document's classification and access grants, and answers only from documents that employee is allowed to read.

| Part | Stack | Details |
|---|---|---|
| Backend | FastAPI, MongoDB, Neo4j, Cloudflare R2 (PDF storage) | [backend/AGENTS.md](backend/AGENTS.md) |
| Frontend | Next.js 16, React 19, Tailwind CSS v4, `lucide-react` | [frontend/AGENTS.md](frontend/AGENTS.md) |
| Project guide | Architecture, rules, status | [AGENTS.md](AGENTS.md) |

## Quick start

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill in values — see backend/AGENTS.md
uvicorn main:app --reload --port 8000
```

```bash
# Frontend (new terminal)
cd frontend
npm ci
npm run dev                 # http://localhost:3000
```

API docs: http://127.0.0.1:8000/docs

## Admin portal

| Tab | What it does |
|---|---|
| Users | Create, edit, revoke/restore and delete users. Search by name or email, filter by department. Row actions are icons: edit (pencil), revoke (ban) / restore (rotate), delete (trash) |
| Organisation | Departments and roles, with clearance |
| Documents | Upload PDFs (stored privately in Cloudflare R2), set owner department, classification and explicit access. Explicit access is shown grouped as **Depts / Roles / Users**. Eye icon beside a title opens a **PDF preview** modal (close with X, Escape or the backdrop). Filters: title, owner department, classification, access department. Row actions: edit access (pencil), delete (trash) |
| Audit Logs | Admin change history, newest first. Each action has its own colour tag (create, upload, update, access update, view, delete, question). Filter by action and by actor name/email (server-side, works across pages) |

**Dates and times** use one compact format everywhere: `28 Oct 2026` with `08:08 PM` underneath (viewer's local time).

**PDF preview** asks the backend for a short-lived presigned link (`GET /api/documents/{uuid}/view-url`). The backend checks the caller may read the document and holds the storage credentials; the frontend never reads them.

## Checks

```bash
cd backend && pytest                  # backend tests
cd frontend && npm run lint && npm run build
```
