# Copilot instructions for dance-page

## Product and source of truth

- The product is **萤火 (Firefly Tales)**, a private web-based picture-book reader. `dance-page` is only the repository/code name and must not appear in the UI. Reuse `APP_NAME`/`APP_NAME_EN` from `src/lib/app-info.ts` and set page titles with `useDocumentTitle()`.
- Product requirements and decisions are written in Chinese under `docs/`. Start at `docs/README.md` (it maps tasks to documents); read `docs/01-product-overview.md` before building features, `docs/05-tech-design.md` for the system design and `docs/06-ai-tech-design.md` for the AI parts.
- When resuming ongoing work, read `docs/progress.md` first. Keep user-facing collaboration and project documentation in Chinese. Keep unconfirmed questions in the "待决问题" section of `docs/progress.md`; append confirmed decisions to `docs/decision-log.md` with the next sequential decision number.

## Build, test, lint, and run

### Full local stack

```bash
scripts/dev.sh        # FastAPI + auto-reloading worker + Vite
scripts/dev.sh --lan  # expose Vite to LAN devices such as an iPad
```

The script creates `backend/.env` from its example when missing, installs dependencies, selects the next free backend port starting at 8000, and points the Vite `/api` proxy at it.

When running an isolated end-to-end environment alongside the user's development server, use separate data, ports, and Vite cache:

```bash
DATA_DIR=/tmp/firefly-test/data \
VITE_CACHE_DIR=/tmp/firefly-test/vite \
BACKEND_PORT=8010 FRONTEND_PORT=5180 \
scripts/dev.sh
```

Do not reuse `backend/data` or `node_modules/.vite` for parallel test servers.

### Frontend

```bash
npm install
npm run dev
npm run lint       # Oxlint
npm run build      # TypeScript project build/type-check, then Vite production build
npm run preview
```

There is currently no frontend test framework. `npm run build` is the frontend type-check.

### Backend

Run backend commands from `backend/` (Python 3.13, dependencies managed by `uv`):

```bash
uv sync
uv run uvicorn --factory app.main:create_app --reload --port 8000
uv run pytest
uv run pytest tests/test_auth.py::test_logout  # single test
uv run ruff check .
uv run ruff format .
uv run alembic revision --autogenerate -m "description"
uv run scripts/render_samples.py
```

After changing `app/models.py`, generate and inspect an Alembic migration. The API runs migrations at startup; the worker waits for the migrated database and must not run migrations itself.

### Deployment

```bash
cp .env.example .env
docker compose up -d --build
```

Compose runs separate `api` and `worker` services sharing `./data`. Production expects Nginx to serve the frontend `dist/` SPA and proxy `/api/` to the API.

## Architecture

- **Frontend:** React 19 + TypeScript + Vite SPA. `src/main.tsx` mounts the browser router defined in `src/router/index.tsx`. Reader routes (`/`, `/books/:id`, login/register) use the "small theater" presentation; `/admin/*` is a separately lazy-loaded shadcn-style admin area.
- **Routing and access:** Import router APIs from `react-router`, not `react-router-dom`. Register pages in `src/router/index.tsx`; route loaders in `src/router/guards.ts` enforce logged-in/admin access before rendering.
- **Frontend data flow:** Resource-specific React Query hooks live in `src/api/*.ts`, with shared API types in `src/api/types.ts`. All requests use the Axios instance in `src/lib/api.ts`, whose base URL is `/api`; Vite proxies that path to FastAPI. `src/lib/query-client.ts` centrally retries requests and redirects an expired logged-in session to `/login`.
- **Backend API:** `backend/app/main.py` exposes the `create_app()` factory, initializes SQLite/Alembic/admin state during lifespan, and mounts all routes below `/api`. Feature areas such as `auth/`, `invites/`, `readers/`, and `books/` keep routers and schemas together.
- **Persistence:** SQLAlchemy 2.0 uses synchronous sessions and SQLite with WAL, foreign keys, and a busy timeout (`backend/app/db.py`). Alembic owns schema evolution.
- **Background processing:** `python -m app.worker` polls the `jobs` table. PDF uploads create queued render jobs; the worker renders/crops pages to WebP, creates a cover, records page dimensions, and updates progress/status without blocking API requests.
- **File storage:** Book assets are derived paths under `DATA_DIR/books/{book_id}/`: `original.pdf`, `pages/NNNN.webp`, and `cover.webp`. Keep path construction in `backend/app/books/storage.py`, not in routers or services.

## Repository-specific conventions

### Frontend

- Use the `@/` alias for `src/`.
- Build page UI from existing components in `src/components/ui/`; do not hand-roll buttons, inputs, labels, progress bars, cards, or error messages. Add missing components with `npx shadcn add <name>`.
- The shadcn `base-nova` components use **Base UI**, not Radix. Use Base UI's `render`/`useRender`/`mergeProps` patterns, not `asChild`. Button-styled links use `nativeButton={false}` with `render={<Link ... />}`.
- Admin query pages reuse `LoadingState` and `ErrorState` from `src/pages/admin/query-state.tsx`.
- Tailwind CSS v4 is configured in `src/index.css`; there is no `tailwind.config.js`. Use semantic shadcn tokens such as `bg-background` and `text-muted-foreground` instead of raw colors.
- Reader-specific theater colors/fonts are separate `stage-*` tokens in `src/index.css`. Extend those tokens without changing the global shadcn theme.
- Use icons from `lucide-react`. The `cn` helper comes from the `cn` package; generated UI components import it from `"cn"`.
- Show backend errors through `getErrorMessage()` and user notifications through `toast.add()` from `@/components/ui/toast`.
- TypeScript enables `verbatimModuleSyntax`, `noUnusedLocals`, `noUnusedParameters`, and `erasableSyntaxOnly`: use `import type` for type-only imports and do not use TypeScript `enum`, `namespace`, or constructor parameter properties.

### Backend

- Reuse dependency aliases from `backend/app/deps.py`: `DbSession`, `AppSettings`, `CurrentUser`, and `CurrentAdmin`.
- All client-visible errors have the shape `{"detail": "<Chinese message>"}`. Schema validators should raise `ValueError` with a Chinese message so `backend/app/errors.py` can expose it consistently.
- All business timestamps must come from `app.clock.utcnow()` and use the `UTCDateTime` column type. Tests advance time through `clock.offset`; do not call `datetime.now()` directly in business logic.
- Preserve the service/worker separation: API handlers enqueue expensive PDF work rather than rendering inline. Only the API process performs migrations.
- Backend tests use isolated temporary `DATA_DIR` values and FastAPI `TestClient`; reuse helpers and fixtures in `backend/tests/conftest.py`.

### Reader page-flip implementation

- Before changing `src/pages/stage/flip-book.tsx`, read section 3.2 of `docs/05-tech-design.md`.
- The component intentionally uses `page-flip` HTML mode, manages its DOM imperatively, and does not use `showCover`. The library overwrites page inline styles and removes its root during `destroy()`, so preserve the wrapper/inner-element/dynamic-root structure.
- Portrait books use a two-page spread only in landscape; landscape books stay single-page. Rebuild on layout changes while preserving the current page.
- Keep the bounded image-loading window around the visible pages to avoid excessive memory use on tablets, and always retain the cover image for the close-book animation.
