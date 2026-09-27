# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

This repo is still close to a Vite + React 19 + TypeScript template (the README, written in Chinese, describes it as such). `src/pages/home.tsx` is a placeholder and `backend/` is empty (only `.gitkeep`) — the backend is meant to be built from scratch. There is no test framework configured.

The product is a web-based children's picture-book reader (Admin uploads PDFs; kids read on tablets with a page-curl effect; later AI read-aloud and page animation). Product requirements, decisions and open questions live in `docs/` (Chinese) — read `docs/01-product-overview.md` before building features. The planned backend (Python + FastAPI + SQLite + separate worker) is specified in `docs/05-tech-design.md`.

## Resuming work

When the user says "继续我们的任务" (or otherwise asks to continue), first read `docs/progress.md` — it holds the current milestone, what is blocked on the user, the step-by-step plan for the next session, and collaboration conventions (talk in Chinese, write only confirmed items into `docs/`, append decisions to `docs/decision-log.md`). Update `docs/progress.md` before ending any work session.

## Commands

```bash
npm install
npm run dev       # Vite dev server on http://localhost:5173
npm run lint      # oxlint (config: .oxlintrc.json)
npm run build     # tsc -b (type check) then vite build
npm run preview   # serve the production build
```

`npm run build` is the only type-check step; `tsconfig.app.json` enables `noUnusedLocals`/`noUnusedParameters`, `verbatimModuleSyntax` (use `import type` for type-only imports), and `erasableSyntaxOnly` (no `enum`, `namespace`, or constructor parameter properties).

## Architecture

- **Entry & routing**: `src/main.tsx` mounts `RouterProvider` with the router from `src/router/index.tsx` (`createBrowserRouter` from `react-router`, not `react-router-dom`). New pages go in `src/pages/` and must be registered there.
- **API / backend contract**: `src/lib/api.ts` exports an axios instance with `baseURL: "/api"`. In dev, Vite proxies `/api` to `http://127.0.0.1:8000` (`vite.config.ts`), so the backend in `backend/` is expected to listen on port 8000 and serve routes under `/api`. Frontend code calls `api.get("/users")`, not full URLs.
- **Path alias**: `@/` → `src/` (configured in both `vite.config.ts` and `tsconfig.app.json`).
- **UI components**: `src/components/ui/` contains shadcn/ui components generated with the `base-nova` style (`components.json`). They are built on **Base UI** (`@base-ui/react`), not Radix — use Base UI patterns (`render` prop / `useRender`, `mergeProps`) rather than Radix's `asChild`. Add new components with the shadcn CLI (`npx shadcn add <name>`) so they follow the same config. Icons come from `lucide-react`.
- **Styling**: Tailwind CSS v4 via `@tailwindcss/vite` — there is no `tailwind.config.js`. Theme tokens (oklch CSS variables for light and `.dark`) and `@theme inline` mappings live in `src/index.css`; dark mode is class-based (`.dark` on an ancestor). Use semantic token classes (`bg-background`, `text-muted-foreground`, etc.) rather than raw colors.
- **`cn` helper**: `src/lib/utils.ts` re-exports `cn` from the `cn` npm package (not the usual `clsx` + `tailwind-merge` combo). UI components import it directly from `"cn"`.
- Available libraries already installed for forms/data: `react-hook-form`, `zod`, `recharts`, `date-fns`/`dayjs`.
