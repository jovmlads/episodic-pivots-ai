# Build Progress

## Phase 1A — Scaffold ✅
- [x] Monorepo directory structure (apps/api, apps/web, supabase, .claude)
- [x] PROGRESS.md, .gitignore, .env.example
- [x] docker-compose.yml (api + web services)
- [x] apps/api/Dockerfile
- [x] apps/web/Dockerfile

## Phase 1B — Database ✅
- [x] supabase/migrations/001_initial_schema.sql
  - profiles, token_usage, notification_settings, screener_configs, scan_runs, scan_results, ai_analyses
  - pgvector vector(1536) on ai_analyses.embedding
  - RLS policies on all tables
  - auto-create profile trigger on signup
- [x] supabase/migrations/002_rag_function.sql
  - match_analyses() RPC for cosine similarity search

## Phase 2A — FastAPI service ✅
- [x] main.py (lifespan, CORS, router registration)
- [x] app/config.py (pydantic-settings)
- [x] app/database.py (Supabase client)
- [x] app/models/ (scan.py, analysis.py)
- [x] app/routers/health.py (health + metrics)
- [x] app/routers/scans.py (configs CRUD + trigger + list)
- [x] app/routers/analyses.py (list + similar + NL screener)
- [x] app/routers/notifications.py (upsert + get + token-usage)
- [x] app/services/screener.py (tradingview-scraper wrapper)
- [x] app/services/scheduler.py (APScheduler, DB-loaded jobs)
- [x] app/services/token_tracker.py (budget check/record/warn)
- [x] app/services/email.py (Resend — scan report + budget warning)

## Phase 3 — AI Agents ✅
- [x] app/agents/news_analyser.py
  - URL fetcher + HTML stripper
  - Claude tool use for structured CatalystResult
  - Web search fallback (claude-sonnet-4-6 web_search tool)
- [x] app/agents/news_orchestrator.py
  - asyncio.gather parallel analysis
  - SSE streaming (start/result/complete/error events)
  - Persist scan_results + ai_analyses
  - Background embedding generation
  - Post-scan email + budget warning
- [x] app/agents/screener_config_producer.py
  - Embedded tradingview-scraper field reference
  - Streaming NL → validated JSON config
  - Returns success=true/false + missing_criteria
- [x] app/agents/rag_similarity.py
  - OpenAI text-embedding-3-small (1536 dims)
  - pgvector cosine similarity via match_analyses() RPC
  - Deduplication by ticker

## Phase 2B — Next.js ✅
- [x] package.json (next 15, react 19, supabase, stripe, radix, tailwind)
- [x] next.config.ts, tsconfig.json, tailwind.config.ts, postcss.config.js
- [x] src/middleware.ts (auth guard + Stripe trial check)
- [x] src/lib/supabase/{client,server}.ts
- [x] src/lib/api.ts (typed FastAPI client)
- [x] src/lib/utils.ts (formatters, signal colors)
- [x] src/types/index.ts (full type definitions)
- [x] src/app/globals.css (dark theme CSS vars)
- [x] src/app/layout.tsx + page.tsx (redirect)
- [x] src/app/(auth)/login + register
- [x] src/app/(dashboard)/layout.tsx (sidebar, auth check)
- [x] src/app/(dashboard)/dashboard — live scan + recent runs
- [x] src/app/(dashboard)/history — paginated run history with expandable results
- [x] src/app/(dashboard)/settings — menu builder + AI chat screener
- [x] src/app/(dashboard)/notifications — email prefs + token usage
- [x] src/app/billing — Stripe checkout for expired trials
- [x] src/app/api/auth/callback — Supabase code exchange
- [x] src/app/api/scans/stream — SSE proxy to FastAPI
- [x] src/app/api/checkout — Stripe session creation
- [x] src/app/api/webhooks/stripe — subscription status sync
- [x] src/components/layout/sidebar
- [x] src/components/dashboard/scan-dashboard (SSE consumer + results table)
- [x] src/components/dashboard/history-table (expandable rows)
- [x] src/components/settings/screener-settings (menu + AI tab)
- [x] src/components/settings/notification-settings (email + usage bar)

## Phase 5 — Polish ✅
- [x] .claude/commands/analyse.md (/analyse TICKER [pct])
- [x] .claude/commands/screen.md (/screen "NL criteria")
- [x] .claude/commands/similar.md (/similar result_id user_id)
- [x] apps/api/tests/ (test_health, test_screener, test_token_tracker, conftest)
- [x] apps/web/tests/e2e/auth.spec.ts (Playwright)
- [x] apps/web/playwright.config.ts
- [x] README.md

---

## To run

```bash
# 1. Copy and fill env
cp .env.example .env

# 2. Apply Supabase migrations
supabase db push

# 3. Start everything
docker compose up

# API: http://localhost:8000/docs
# Web: http://localhost:3000
```

## Next steps (not built)
- Supabase local dev setup (supabase init)
- Railway + Vercel CI/CD pipeline
- Admin panel for user budget management
- More Playwright test coverage (dashboard flows)
