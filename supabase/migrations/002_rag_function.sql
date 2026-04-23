-- RPC function for pgvector cosine similarity search
create or replace function public.match_analyses(
  query_embedding      vector(1536),
  user_id_filter       uuid,
  exclude_analysis_id  uuid,
  match_count          int default 10
)
returns table (
  analysis_id    uuid,
  ticker         text,
  company_name   text,
  analysis_text  text,
  catalyst_type  text,
  trading_signal text,
  similarity     float,
  scanned_at     timestamptz
)
language sql stable
as $$
  select
    a.id              as analysis_id,
    sr.ticker,
    sr.company_name,
    a.analysis_text,
    a.catalyst_type,
    a.trading_signal,
    1 - (a.embedding <=> query_embedding) as similarity,
    sr.scanned_at
  from public.ai_analyses a
  join public.scan_results sr on sr.id = a.result_id
  where
    a.user_id = user_id_filter
    and a.id != exclude_analysis_id
    and a.embedding is not null
  order by a.embedding <=> query_embedding
  limit match_count;
$$;
