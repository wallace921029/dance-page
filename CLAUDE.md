# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Phase-1 features are built: accounts/invites/readers (M1), PDF upload + rendering worker + admin UI (M2), and the reader side — register page, "small theater" shelf and page-flip reading page (M3). Add-to-home-screen is done (`public/manifest.webmanifest`, `public/icons/`, safe-area insets via `env(safe-area-inset-*)`). Remaining for phase 1: M4 deployment docs (Nginx reference config, deployment README, backups) and on-device iPad testing. The AI phase (read-aloud "Voice Ready" and page animation "Dance Ready!") is designed in `docs/06-ai-tech-design.md`; milestone A1 (AI provider settings at `/admin/ai`), A0 (trial calls against 百炼 / 火山), and A2 (Story & Draft Workbench) are done, then A3 (Voice Ready) is next. Work happens directly on the `main` branch (no separate branches). Backend tests use pytest (`backend/tests/`); the frontend has no test framework.

The product is called **萤火 (Firefly Tales)** — `dance-page` is only the repo/code name and must not appear in the UI (name constants live in `src/lib/app-info.ts`; set per-page tab titles with `useDocumentTitle()`). It is a web-based children's picture-book reader (Admin uploads PDFs; kids read on tablets with a page-curl effect; later AI read-aloud and page animation). Product requirements, decisions and open questions live in `docs/` (Chinese) — read `docs/01-product-overview.md` before building features. The planned backend (Python + FastAPI + SQLite + separate worker) is specified in `docs/05-tech-design.md`.

## Resuming work

When the user says "继续我们的任务" (or otherwise asks to continue), first read `docs/progress.md` — it holds the current milestone, what is blocked on the user, the step-by-step plan for the next session, and collaboration conventions (talk in Chinese, write only confirmed items into `docs/`, append decisions to `docs/decision-log.md`). Update `docs/progress.md` before ending any work session.

## Commands

```bash
scripts/dev.sh        # one-shot local dev: backend (auto-reload) + Vite; --lan exposes the frontend to LAN devices (iPad).
                      # Picks the next free backend port if 8000 is busy and points the Vite /api proxy at it (API_PROXY_TARGET).

npm install
npm run dev       # Vite dev server on http://localhost:5173
npm run lint      # oxlint (config: .oxlintrc.json)
npm run build     # tsc -b (type check) then vite build
npm run preview   # serve the production build

# backend (run inside backend/, managed by uv, Python 3.13)
cp .env.example .env               # ADMIN_USERNAME / ADMIN_PASSWORD / COOKIE_SECURE=false
uv run uvicorn --factory app.main:create_app --reload --port 8000   # runs migrations + admin sync on startup
uv run pytest                      # single test: uv run pytest tests/test_auth.py::test_logout
uv run ruff check . && uv run ruff format .
uv run alembic revision --autogenerate -m "..."   # after changing app/models.py
uv run scripts/render_samples.py   # render samples/*.pdf → samples/rendered/ to compare render settings

# home-screen icons (repo root; renders the SVG in scripts/make-icons.py with local Chrome → public/icons/*.png)
uv run scripts/make-icons.py

# deploy (repo root): cp .env.example .env && docker compose up -d --build
```

`npm run build` is the only type-check step; `tsconfig.app.json` enables `noUnusedLocals`/`noUnusedParameters`, `verbatimModuleSyntax` (use `import type` for type-only imports), and `erasableSyntaxOnly` (no `enum`, `namespace`, or constructor parameter properties).

## Architecture

- **Entry & routing**: `src/main.tsx` mounts `RouterProvider` with the router from `src/router/index.tsx` (`createBrowserRouter` from `react-router`, not `react-router-dom`). New pages go in `src/pages/` and must be registered there.
- **API / backend contract**: `src/lib/api.ts` exports an axios instance with `baseURL: "/api"`. In dev, Vite proxies `/api` to `http://127.0.0.1:8000`, overridable via the `API_PROXY_TARGET` env var (`vite.config.ts`), so the backend in `backend/` is expected to listen on port 8000 and serve routes under `/api`. Frontend code calls `api.get("/users")`, not full URLs.
- **Path alias**: `@/` → `src/` (configured in both `vite.config.ts` and `tsconfig.app.json`).
- **Always build page UI from `src/components/ui/`** (Button, Input, Field*, Card, Progress, Badge, Avatar, Alert, Empty, Item, DropdownMenu, NavigationMenu, Table, Skeleton…). Don't hand-roll equivalents with raw `<button>`/`<input>`/`<label>`, `div` progress bars, card shells or red `<p>` error text — restyle shadcn components via `className`/`variant` instead (the reader's theater look is just classes on them). Links styled as buttons use `<Button nativeButton={false} render={<Link to=… />}>`. Admin pages share `LoadingState`/`ErrorState` from `src/pages/admin/query-state.tsx`, and wrap modules/table rows in the entrance-animation helpers from `src/pages/admin/motion.tsx` (`Reveal`, `AnimatedTableRow`, `RevealItem`; D86). Only the imperative page-flip DOM in `flip-book.tsx` is exempt. Add missing components with `npx shadcn add <name>`.
- **UI components**: `src/components/ui/` contains shadcn/ui components generated with the `base-nova` style (`components.json`). They are built on **Base UI** (`@base-ui/react`), not Radix — use Base UI patterns (`render` prop / `useRender`, `mergeProps`) rather than Radix's `asChild`. Add new components with the shadcn CLI (`npx shadcn add <name>`) so they follow the same config. Icons come from `lucide-react`.
- **Styling**: Tailwind CSS v4 via `@tailwindcss/vite` — there is no `tailwind.config.js`. Theme tokens (oklch CSS variables for light and `.dark`) and `@theme inline` mappings live in `src/index.css`; dark mode is class-based (`.dark` on an ancestor). Use semantic token classes (`bg-background`, `text-muted-foreground`, etc.) rather than raw colors.
- **`cn` helper**: `src/lib/utils.ts` re-exports `cn` from the `cn` npm package (not the usual `clsx` + `tailwind-merge` combo). UI components import it directly from `"cn"`.
- Available libraries already installed for forms/data: `react-hook-form`, `zod`, `recharts`, `date-fns`/`dayjs`.
- **Backend structure** (`backend/app/`): `create_app()` in `main.py` is an app factory (uvicorn `--factory`); config via pydantic-settings (`config.py`); SQLAlchemy 2.0 sync sessions on SQLite (WAL) with Alembic migrations run automatically at API startup. Shared dependencies (`DbSession`, `CurrentUser`, `CurrentAdmin`) live in `deps.py`. All datetimes go through `app.clock.utcnow()` (tests fast-forward via `clock.offset`) and are stored with the `UTCDateTime` column type. Error responses are always `{"detail": "<Chinese message>"}` — validators raise `ValueError` with a Chinese message and `errors.py` unwraps it. Feature modules (`auth/`, `invites/`, `readers/`) each have `router.py` + `schemas.py`.
- **AI (`backend/app/ai/`)**: design in `docs/06-ai-tech-design.md`. `catalog.py` lists providers (百炼 `dashscope`, 火山 `volcengine`), capabilities (`vision`/`tts`/`video`) and their defaults; `settings.py` reads/writes config. Provider credentials come from `.env` (`DASHSCOPE_API_KEY`, `VOLCENGINE_ARK_API_KEY`, `VOLCENGINE_SPEECH_API_KEY` → `Settings` fields, D82); `/admin/ai` only shows whether each is set (last 4 chars) — never return full keys from the API. Provider/model/base URL per capability are chosen in `/admin/ai` and stored in SQLite. Provider adapters live in `app/ai/providers/`; their HTTP client ignores proxy env vars (`trust_env=False`) and tests swap it via `monkeypatch` on `providers.http_client`.
- **Worker**: `python -m app.worker` (`app/worker/runner.py`) polls the `jobs` table and renders PDFs with `app/books/render.py` (trim white margins, detect spread pairing, WebP pages). Only the API process runs migrations; the worker waits for them. `scripts/dev.sh` and `docker-compose.yml` start it alongside the API. Book files live under `DATA_DIR/books/{book_id}/` (`app/books/storage.py`).
- **Frontend data layer**: react-query hooks per resource in `src/api/*.ts` with API types in `src/api/types.ts`; the shared `queryClient` is in `src/lib/query-client.ts` (redirects to `/login` when a logged-in session gets a 401). Route access is enforced by react-router loaders in `src/router/guards.ts` (`requireUser`, `requireAdmin`). Show API errors with `getErrorMessage()` from `src/lib/api.ts` and notifications with `toast.add()` from `@/components/ui/toast`.
- **Reader side ("small theater" style, D37)**: pages in `src/pages/stage/` (`shelf.tsx`, `reader.tsx`, `flip-book.tsx`, shared `common.tsx`) plus `src/pages/login.tsx` / `register.tsx`. Theme colors and fonts are Tailwind tokens in `src/index.css` `@theme` (`bg-stage-night`, `text-stage-light`, `font-stage-title`, …) — don't touch the shadcn tokens for this. `flip-book.tsx` wraps the `page-flip` library imperatively; read the "阅读页实现要点" section of `docs/progress.md` before changing it (the library overwrites inline styles, deletes its root on destroy, and we avoid `showCover` on purpose).
