export interface Profile {
  id: string;
  email: string;
  is_admin: boolean;
  stripe_status: string | null;
  trial_ends_at: string;
  monthly_token_budget: number;
  created_at: string;
}

export interface FilterRule {
  left: string;
  operation: string;
  right: string | number | (string | number)[];
}

export interface ScreenerConfig {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  market: string;
  scan_type: string;
  filters: FilterRule[];
  columns: string[];
  sort_by: string;
  sort_order: string;
  result_limit: number;
  is_active: boolean;
  schedule_cron: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScanRun {
  id: string;
  user_id: string;
  config_id: string | null;
  status: "pending" | "running" | "completed" | "failed";
  result_count: number;
  tokens_used: number;
  triggered_by: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  screener_configs?: { name: string } | null;
}

export interface ScanResult {
  id: string;
  run_id: string;
  ticker: string;
  company_name: string | null;
  exchange: string | null;
  sector: string | null;
  premarket_change_pct: number;
  premarket_price: number;
  premarket_volume: number;
  relative_volume: number;
  market_cap: number | null;
  float_shares: number | null;
  scanned_at: string;
  ai_analyses?: AIAnalysis[];
}

export interface AIAnalysis {
  id: string;
  result_id: string;
  news_url: string | null;
  news_title: string | null;
  catalyst_type: string | null;
  sentiment: "bullish" | "bearish" | "neutral" | null;
  trading_signal: "strong_buy" | "buy" | "watch" | "skip" | "short" | "strong_short" | null;
  analysis_text: string;
  web_search_used: boolean;
  tokens_input: number;
  tokens_output: number;
  created_at: string;
}

export interface ScanSSEEvent {
  type: "start" | "ticker" | "result" | "no_results" | "complete" | "error";
  total?: number;
  run_id?: string;
  ticker?: string;
  company_name?: string;
  premarket_change_pct?: number;
  news_url?: string;
  news_title?: string;
  catalyst_type?: string;
  sentiment?: string;
  trading_signal?: string;
  analysis_text?: string;
  web_search_used?: boolean;
  total_results?: number;
  total_tokens?: number;
  message?: string;
}

export interface TokenUsage {
  tokens_total: number;
  tokens_input: number;
  tokens_output: number;
  month_year: string;
}

export type TradingSignal = "strong_buy" | "buy" | "watch" | "skip" | "short" | "strong_short";
