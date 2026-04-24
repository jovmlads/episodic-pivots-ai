"use client";
import { useEffect, useState } from "react";
import ChartModal from "./chart-modal";

type SimilarRow = {
  ticker: string;
  company_name: string;
  analysis_text: string;
  catalyst_type: string | null;
  trading_signal: string | null;
  news_url: string | null;
  scanned_at: string | null;
};

interface Props {
  resultId: string;
  ticker: string;
  onClose: () => void;
}

export default function SimilarModal({ resultId, ticker, onClose }: Props) {
  const [rows, setRows] = useState<SimilarRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [chartTicker, setChartTicker] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/proxy/analyses/similar?result_id=${resultId}&limit=5`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [resultId]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="bg-background border border-border rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-semibold text-sm">
            Similar past setups — <span className="text-primary">{ticker}</span>
          </h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground text-xl leading-none"
          >
            ×
          </button>
        </div>

        {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!loading && rows?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No similar past setups found.
          </p>
        )}
        {!loading && rows && rows.length > 0 && (
          <div className="space-y-4">
            {rows.map((r, i) => (
              <div
                key={i}
                className="border-b border-border/50 pb-4 last:border-0 last:pb-0"
              >
                <div className="flex gap-3 items-baseline mb-1 flex-wrap">
                  <span className="font-bold text-sm">{r.ticker}</span>
                  {r.trading_signal && (
                    <span className="text-xs uppercase text-muted-foreground">
                      {r.trading_signal.replace(/_/g, " ")}
                    </span>
                  )}
                  {r.scanned_at && (
                    <span className="text-xs text-muted-foreground opacity-60">
                      {new Date(r.scanned_at).toLocaleDateString()}
                    </span>
                  )}
                  <button
                    onClick={() => setChartTicker(r.ticker)}
                    className="text-xs text-muted-foreground underline hover:text-foreground"
                  >
                    Chart
                  </button>
                  {r.news_url && (
                    <a
                      href={r.news_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-primary underline ml-auto"
                    >
                      news ↗
                    </a>
                  )}
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {r.analysis_text}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
      {chartTicker && (
        <ChartModal ticker={chartTicker} onClose={() => setChartTicker(null)} />
      )}
    </div>
  );
}
