<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Company Brain — Frontend

Next.js web app with three surfaces:

- **Login** — one form for everyone; the backend returns the user's permissions and the app routes admins to `/admin`, others to `/dashboard`
- **Admin portal** (`/admin`) — dashboard, users, organisation (departments/roles), documents (classification + access), audit logs. Sidebar items appear per permission
- **Employee chat** (`/dashboard`) — ask questions, see cited answers

The frontend is a **presentation layer only**. It never decides what a user may see — the backend enforces all access control. Hiding a button is UX, not security.

See the [project AGENTS.md](../AGENTS.md) for architecture and the [backend AGENTS.md](../backend/AGENTS.md) for the API.

> ⚠️ This project runs **Next.js 16** (App Router, React 19, React Compiler, Turbopack). APIs differ from older versions — read the Next.js block at the top of this file and the docs in `node_modules/next/dist/docs/` before changing framework-level code.

---

## 1. Tech stack

| Concern | Choice |
|---|---|
| Framework | Next.js 16 (App Router) |
| UI | React 19 with React Compiler |
| Styling | Tailwind CSS v4 (via `@tailwindcss/turbopack`); every styling value comes from semantic tokens in `src/app/globals.css` |
| Icons | Local SVG components (`components/*/icons.js`) and `lucide-react` (row actions, preview, filters, modal close) |
| Font | Inter (`@fontsource-variable/inter`, imported in `layout.js`, family declared in `globals.css`) |
| Language | JavaScript (ES modules); path alias `@/*` → `src/*` |
| Lint | ESLint 9 + `eslint-config-next` |

---

## 2. Setup

```bash
cd frontend
npm ci              # use the lockfile; don't run `npm install` unless changing deps
npm run dev         # http://localhost:3000
```

| Script | Purpose |
|---|---|
| `npm run dev` | Dev server (Turbopack) |
| `npm run build` | Production build — must pass before merging |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint — must pass before merging |

### Configuration

The backend URL comes from `NEXT_PUBLIC_API_BASE_URL` (default `http://127.0.0.1:8000`, see `src/lib/api.js`):

```bash
# frontend/.env.local  (never committed)
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

`NEXT_PUBLIC_DEFAULT_THEME` (`light` | `dark` | `system`, default `light`) sets the colour scheme for first-time visitors. Copy `.env.example` to `.env.local`.

Only `NEXT_PUBLIC_*` variables reach the browser — never put secrets in them.

---

## 3. Project structure

```
src/
├── app/                      Routes (App Router). Pages stay thin: metadata + one component
│   ├── layout.js             Root layout, fonts, global CSS
│   ├── page.js               Redirects to /login
│   ├── login/page.js
│   ├── dashboard/page.js     Employee chat
│   └── admin/
│       ├── layout.js         Wraps all admin pages in <AdminShell>
│       ├── page.js           Overview
│       ├── users/page.js
│       ├── organisation/page.js
│       ├── documents/page.js
│       └── audit-logs/page.js
├── components/               Feature-grouped UI
│   ├── LoginCard/
│   ├── EmployeeChat/         ChatApp, Message, Sidebar, icons, data (sample)
│   └── admin/                AdminShell, AdminSidebar, DashboardOverview, StatCard,
│       ├── users/            UsersManager, UserModal
│       ├── organisation/     OrganisationManager (departments, roles, clearance)
│       ├── documents/        DocumentsManager
│       └── auditLogs/        AuditLogs
├── services/                 All backend calls, one file per domain
│   ├── http.js           `api()` — the only place that knows URL, token, 401 handling
│   ├── authService.js    login, current user
│   ├── orgService.js     departments, roles
│   ├── userService.js    users CRUD
│   ├── documentService.js  upload, list, access, delete, view URL (PDF preview)
│   ├── auditService.js   audit log page + filters (action, actor)
│   └── dashboardService.js
└── lib/                      Framework-agnostic helpers (api base URL, utils, format.js display formatters)
```

### Rules

- **Pages** (`app/**/page.js`) export `metadata` and render one feature component. No fetching or state there.
- **Components** never call `fetch` directly — they call a function in `services/`.
- **Services** are the only place that knows URLs, headers and tokens. Each function returns parsed data or throws an `Error` with a user-safe message.
- **`data.js` files** hold sample/static data. Anything that represents real company data must come from the API before a demo.
- Put `"use client"` only on components that need state, effects or browser APIs; keep everything else server-rendered.

---

## 4. Talking to the backend

Every service function is a one-liner on top of `services/http.js`:

```js
export const getDocuments = () => api("/api/documents/");
export const updateDocumentAccess = (id, access) =>
  api(`/api/documents/${id}/access`, { method: "PATCH", body: access });
```

`api()` adds the Bearer token, parses JSON, and turns FastAPI errors (`detail` as string or validation list) into an `Error` with a user-safe message. A **401 clears the session and redirects to `/login`**; a 403 just throws, and the screen shows the message. Never read the token anywhere else.

The UI hides things by permission (`NAV_ITEMS` in `components/admin/data.js`), but that is navigation only — the server enforces every rule.

## 5. Security standards

- **The server is the authority.** Role checks in the UI are for navigation only; every protected screen must also handle a 401/403 from the API.
- **Never render citations, titles or filenames the API didn't return** — the chat must display exactly what the backend authorised, nothing cached from another user.
- **Clear all user state on logout** — tokens, chat history, cached lists — so a shared machine can't leak the previous user's data.
- **No `dangerouslySetInnerHTML`** for model output or document text. Render answers as text/markdown with a sanitising renderer.
- **No secrets in the bundle.** Anything in `NEXT_PUBLIC_*` or source code is public.
- **No `console.log` of tokens, responses or user data** in committed code.
- Token storage: Web Storage is readable by any script on the page (XSS risk). Target for production is an **HttpOnly, Secure, SameSite cookie** set by the backend.

---

## 5b. Theming, styling and UI conventions

**All styling values live in `src/app/globals.css` — nothing is defined in components.** That covers colours, fonts, radii, shadows and type sizes. Components use the semantic utilities the tokens generate:

| Need | Use |
|---|---|
| Backgrounds | `bg-canvas` (page), `bg-surface` (cards, modals), `bg-surface-2` / `bg-surface-3` (headers, hovers, chips) |
| Text | `text-ink`, `text-ink-2`, `text-ink-3` |
| Borders | `border-line`, `border-line-strong`, `divide-line` |
| Brand | `bg-brand` + `text-on-brand`, `hover:bg-brand-hover`, `bg-brand-tint`, `text-brand-text` |
| Status | `text-success` / `bg-success-soft`, same for `warning`, `danger` (button: `bg-danger text-on-danger`), `info` |
| Shape | `rounded-card`, `rounded-control`, `shadow-card`, `shadow-pop`, `text-micro`, `text-chat` |

Never use raw palette classes (`slate-*`, `indigo-*`, `red-*`, `white`, `black`…), arbitrary values (`text-[11px]`), hex/rgb colours, font names or `style={{…}}` in a component. `npm run lint` runs `scripts/check-styles.mjs`, which fails on all of these. To add a colour or size, add a token to `globals.css` (light **and** dark) and use its utility.

**Light / dark.** `<html data-theme>` is `light`, `dark` or `system`. The default is `NEXT_PUBLIC_DEFAULT_THEME`; each user picks Light / Dark / System under *Appearance* in the profile menu (`components/ui/ThemeSelect.js`). The choice is stored in this browser only (`localStorage`) — saving it to the user's account is a later backend step. `public/theme-init.js` (an external script, not inline) applies the saved choice before first paint. The dark values appear twice in `globals.css` (`[data-theme="dark"]` and the `system` media query) — keep them identical.

**Cursors.** One global rule gives every enabled button, link, select, checkbox, radio and `label[for]` a pointer and every disabled control `not-allowed`. Do not add `cursor-*` classes.

**Capitalisation.** Title Case for page titles, nav items, buttons, column headers and badges; sentence case for helper text, placeholders, errors and empty states. Data is formatted on display with `lib/format.js` (`displayName`, `titleCase`, `actionLabel`, `formatDate`, `formatTime`, `formatDateTime`).

**Dates and times.** Always use the `lib/format.js` helpers, never `toLocaleString()`: `formatDate` → `28 Oct 2026`, `formatTime` → `08:08 PM`, `formatDateTime` → `28 Oct 2026, 08:08 PM` (viewer's local time zone). A timestamp without a zone (MongoDB returns naive UTC datetimes) is read as UTC. In tables, show the date with the time on a smaller second line (`whitespace-nowrap`) and the full value in `title`.

**Row actions.** Table row actions are icon-only `IconButton`s (`components/ui/IconButton.js`) with a `lucide-react` icon; the required `label` is both the `aria-label` and the hover tooltip. Icons in use: `Pencil` edit / edit access, `Trash2` delete, `Ban` revoke access, `RotateCcw` restore access, `Eye` preview, `X` close.

**Audit action colours.** `AuditLogs` maps each action to an existing `Badge` tone (no new colours): create → `success`, upload → `brand`, update → `info`, delete → `danger`, `document.access.update` → `warning`, `document.view` → `neutral`, `rag.ask` → `cat-2`. Add new actions to `ACTION_TONE` / `VERB_TONE` there.

**Table filters.** Users: name search + email search + department + role. Documents: title search + owner department + classification + access department (client-side over the loaded list). Audit logs: actor search (debounced 300 ms) + action dropdown, filtered on the server (`/audit-logs?action=&actor=`) so pagination stays correct. Each filtered view has a "Clear filters" button and a "no matches" empty state. The "Clear filters" button is always rendered (`invisible` when no filter is set) so the filter area never changes size.

**Pagination & stable tables.** Every admin table shows `PAGE_SIZE` (8) rows per page with the shared `components/ui/Pagination.js` footer: Users and Documents paginate client-side over the filtered list (any filter change resets to page 1), Audit logs paginate on the server. Tables use `table-fixed` with widths on the `<th>`s so columns never resize when filters change the rows, and the admin `<main>` uses the `scrollbar-stable` utility (`scrollbar-gutter: stable`) so content does not shift sideways when the scrollbar appears or disappears.

**Document preview.** The eye icon beside a document title opens a modal that asks the backend for a short-lived link (`getDocumentViewUrl` → `GET /api/documents/{uuid}/view-url`) and shows the PDF in an `<iframe>`, with an open-in-new-tab link and a close (X) button; Escape and a backdrop click also close it. The frontend never reads storage credentials — the backend checks access and presigns the R2 (Cloudflare) URL.

**Unfinished features.** No fake data. Flags in `src/config/features.js` mark what is planned; while a flag is `false` the UI shows `ComingSoonBadge` / `ComingSoonNotice` (`components/ui/ComingSoon.js`) and disables the control. Turn a flag on only when the backend exists.

Shared UI pieces: `components/ui/{Badge,DepartmentBadge,IconButton,Pagination,ComingSoon,ThemeSelect}.js`.

## 6. UI & accessibility standards

- Every interactive element is keyboard-reachable with a visible focus state.
- Inputs have associated `<label>`s; icon-only buttons have `aria-label`.
- Colour is never the only signal (pair status colours with text/icons); meet WCAG AA contrast.
- Every async view has **loading**, **empty** and **error** states.
- Destructive actions (delete user/document) require confirmation.
- Chat answers always show their **source documents**, and an explicit "I don't know" state when the backend abstains.
- Layout works down to 360 px width.

---

## 7. Coding standards

- **Naming:** components `PascalCase.js`, hooks `useThing`, services/helpers `camelCase`, constants `UPPER_SNAKE`.
- **Components:** one exported component per file; split when a file passes ~300 lines (e.g. `ChatApp.js`, `DocumentsManager.js`, `UsersManager.js` are candidates).
- **Imports:** use the `@/` alias, not long relative paths.
- **State:** keep it local; lift only when two siblings need it. No global store until a real need appears.
- **Styling:** Tailwind utility classes; shared colours/spacing as theme tokens in `globals.css`, not hard-coded hex values scattered across files.
- **Dependencies:** add one only when the platform or an existing package can't do the job.

---

## 8. Testing

Not set up yet. Recommended, in order of value:

1. **Playwright** end-to-end: login as each role, the same question asked by a junior vs. finance head gives different outcomes, logout clears state.
2. **Vitest + React Testing Library** for components with logic (forms, modals, message rendering).

`npm run lint` and `npm run build` must pass on every PR.

---

## 9. Known gaps

| Area | Issue |
|---|---|
| `app/layout.js` | Root metadata still "Create Next App" |
| `EmployeeChat` | Real profile, accessible documents and live question answering (`/api/rag/ask`, `FEATURES.questionAnswering = true`). Chat history is kept in memory only (lost on refresh) |
| `admin/auditLogs` | Shows admin changes only; query history needs the retrieval service |
| Document preview | Uses `can_view`, so an admin can only preview documents they may read (others show "Document not found."); documents registered without a stored file show the backend's "no stored file" message |
| Auth | Tokens in Web Storage; Edit user modal cannot change email/password; theme preference is browser-only |
| UI kit | Colours/shapes are tokenised, but screens still repeat button/card class strings; `ui/Button`, `Card` and `PageHeader` primitives are not extracted yet |
| Tests | None |
