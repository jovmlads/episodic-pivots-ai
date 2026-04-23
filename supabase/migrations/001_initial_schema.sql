-- Enable pgvector extension
create extension if not exists vector;

-- ============================================================
-- PROFILES (extends auth.users)
-- ============================================================
create table public.profiles (
  id              uuid references auth.users(id) on delete cascade primary key,
  email           text not null,
  is_admin        boolean not null default false,
  stripe_customer_id      text,
  stripe_subscription_id  text,
  stripe_status           text,               -- active | trialing | canceled | past_due
  trial_ends_at           timestamptz not null default (now() + interval '14 days'),
  monthly_token_budget    integer not null default 1000000,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "Users can view own profile"
  on public.profiles for select using (auth.uid() = id);

create policy "Users can update own profile"
  on public.profiles for update using (auth.uid() = id);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ============================================================
-- TOKEN USAGE (monthly, per user)
-- ============================================================
create table public.token_usage (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid references public.profiles(id) on delete cascade not null,
  month_year      text not null,              -- e.g. '2024-01'
  tokens_input    bigint not null default 0,
  tokens_output   bigint not null default 0,
  tokens_total    bigint not null default 0,
  updated_at      timestamptz not null default now(),
  unique (user_id, month_year)
);

alter table public.token_usage enable row level security;

create policy "Users can view own token usage"
  on public.token_usage for select using (auth.uid() = user_id);

-- ============================================================
-- NOTIFICATION SETTINGS
-- ============================================================
create table public.notification_settings (
  id                      uuid primary key default gen_random_uuid(),
  user_id                 uuid references public.profiles(id) on delete cascade not null unique,
  email                   text not null,
  notify_on_scan_complete boolean not null default true,
  notify_on_budget_warning boolean not null default true,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now()
);

alter table public.notification_settings enable row level security;

create policy "Users can manage own notification settings"
  on public.notification_settings for all using (auth.uid() = user_id);

-- ============================================================
-- SCREENER CONFIGS
-- ============================================================
create table public.screener_configs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid references public.profiles(id) on delete cascade not null,
  name            text not null,
  description     text,
  market          text not null default 'america',
  scan_type       text not null,              -- premarket_gainers | premarket_losers | gap_up | gap_down
  filters         jsonb not null default '[]',
  columns         jsonb not null default '[]',
  sort_by         text not null default 'premarket_change',
  sort_order      text not null default 'desc',
  result_limit    integer not null default 20 check (result_limit between 1 and 50),
  is_active       boolean not null default true,
  schedule_cron   text,                       -- null = manual only
  next_run_at     timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

alter table public.screener_configs enable row level security;

create policy "Users can manage own screener configs"
  on public.screener_configs for all using (auth.uid() = user_id);

create index idx_screener_configs_user_active
  on public.screener_configs (user_id, is_active);

-- ============================================================
-- SCAN RUNS
-- ============================================================
create table public.scan_runs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid references public.profiles(id) on delete cascade not null,
  config_id       uuid references public.screener_configs(id) on delete set null,
  status          text not null default 'pending'
                  check (status in ('pending','running','completed','failed')),
  result_count    integer not null default 0,
  tokens_used     integer not null default 0,
  error_message   text,
  triggered_by    text not null default 'manual',   -- manual | scheduled
  started_at      timestamptz,
  completed_at    timestamptz,
  created_at      timestamptz not null default now()
);

alter table public.scan_runs enable row level security;

create policy "Users can view own scan runs"
  on public.scan_runs for select using (auth.uid() = user_id);

create index idx_scan_runs_user_created
  on public.scan_runs (user_id, created_at desc);

-- ============================================================
-- SCAN RESULTS
-- ============================================================
create table public.scan_results (
  id                    uuid primary key default gen_random_uuid(),
  run_id                uuid references public.scan_runs(id) on delete cascade not null,
  user_id               uuid references public.profiles(id) on delete cascade not null,
  ticker                text not null,
  company_name          text,
  exchange              text,
  sector                text,
  prev_close            numeric,
  premarket_price       numeric,
  premarket_change_pct  numeric,
  premarket_change_abs  numeric,
  premarket_volume      bigint,
  avg_volume            bigint,
  relative_volume       numeric,
  float_shares          bigint,
  market_cap            numeric,
  raw_data              jsonb,
  scanned_at            timestamptz not null default now()
);

alter table public.scan_results enable row level security;

create policy "Users can view own scan results"
  on public.scan_results for select using (auth.uid() = user_id);

create index idx_scan_results_run on public.scan_results (run_id);
create index idx_scan_results_user_date on public.scan_results (user_id, scanned_at desc);
create index idx_scan_results_ticker on public.scan_results (ticker);

-- ============================================================
-- AI ANALYSES
-- ============================================================
create table public.ai_analyses (
  id                uuid primary key default gen_random_uuid(),
  result_id         uuid references public.scan_results(id) on delete cascade not null,
  user_id           uuid references public.profiles(id) on delete cascade not null,
  news_url          text,
  news_title        text,
  catalyst_type     text,
  sentiment         text check (sentiment in ('bullish','bearish','neutral')),
  trading_signal    text check (trading_signal in ('strong_buy','buy','watch','skip','short','strong_short')),
  analysis_text     text not null,
  web_search_used   boolean not null default false,
  tokens_input      integer not null default 0,
  tokens_output     integer not null default 0,
  embedding         vector(1536),             -- text-embedding-3-small
  created_at        timestamptz not null default now()
);

alter table public.ai_analyses enable row level security;

create policy "Users can view own AI analyses"
  on public.ai_analyses for select using (auth.uid() = user_id);

create index idx_ai_analyses_result on public.ai_analyses (result_id);
create index idx_ai_analyses_user on public.ai_analyses (user_id, created_at desc);

-- pgvector cosine similarity index (IVFFlat, good for <1M rows)
create index idx_ai_analyses_embedding
  on public.ai_analyses
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- ============================================================
-- UPDATED_AT triggers
-- ============================================================
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger set_updated_at_profiles
  before update on public.profiles
  for each row execute procedure public.set_updated_at();

create trigger set_updated_at_screener_configs
  before update on public.screener_configs
  for each row execute procedure public.set_updated_at();

create trigger set_updated_at_notification_settings
  before update on public.notification_settings
  for each row execute procedure public.set_updated_at();
