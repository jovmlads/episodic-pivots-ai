"use client";
import { useState } from "react";
import { Loader2 } from "lucide-react";
import { formatPct, signalColor, cn } from "@/lib/utils";
import SimilarModal from "./similar-modal";
import ChartModal from "./chart-modal";

export interface ResultRow {
  ticker: string;
  pct: number;
  signal?: string | null;
  catalyst?: string | null;
  analysis?: string | null;
  newsUrl?: string | null;
  webSearch?: boolean;
  analysing?: boolean;
  resultId?: string | null;
}

export default function ResultsTable({ rows }: { rows: ResultRow[] }) {
  const [modal, setModal] = useState<{
    resultId: string;
    ticker: string;
  } | null>(null);
  const [chartTicker, setChartTicker] = useState<string | null>(null);

  if (!rows.length)
    return (
      <p className="text-sm text-muted-foreground px-4 py-3">
        No results for this scan.
      </p>
    );
  return (
    <>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-xs">
            <th className="px-4 py-2 text-left">Ticker</th>
            <th className="px-4 py-2 text-right">PM Chg</th>
            <th className="px-4 py-2 text-left">Signal</th>
            <th className="px-4 py-2 text-left">Catalyst</th>
            <th className="px-4 py-2 text-left">Analysis</th>
            <th className="px-4 py-2 text-left">News</th>
            <th className="px-4 py-2 text-left">Chart</th>
            <th className="px-4 py-2 text-left">Similar</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={i}
              className="border-b border-border/50 hover:bg-accent/30 transition-colors"
            >
              <td className="px-4 py-2 font-bold">{r.ticker}</td>
              <td
                className={cn(
                  "px-4 py-2 text-right font-mono",
                  r.pct >= 0 ? "text-bullish" : "text-bearish",
                )}
              >
                {formatPct(r.pct)}
              </td>
              <td
                className={cn(
                  "px-4 py-2 uppercase text-xs font-bold",
                  r.analysing
                    ? "text-muted-foreground"
                    : signalColor(r.signal as never),
                )}
              >
                {r.analysing ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  r.signal?.replace(/_/g, " ") || "—"
                )}
              </td>
              <td className="px-4 py-2 text-xs text-muted-foreground capitalize">
                {r.analysing ? "…" : r.catalyst?.replace(/_/g, " ") || "—"}
              </td>
              <td className="px-4 py-2 text-xs max-w-xs text-muted-foreground">
                {r.analysing ? "Analysing…" : r.analysis || "—"}
              </td>
              <td className="px-4 py-2">
                {r.newsUrl && (
                  <a
                    href={r.newsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-muted-foreground underline hover:text-foreground"
                  >
                    {r.webSearch ? "web" : "news"}
                  </a>
                )}
              </td>
              <td className="px-4 py-2">
                {!r.analysing && (
                  <button
                    onClick={() => setChartTicker(r.ticker)}
                    className="text-xs text-muted-foreground underline hover:text-foreground"
                  >
                    Chart
                  </button>
                )}
              </td>
              <td className="px-4 py-2">
                {r.resultId && !r.analysing && r.signal && (
                  <button
                    onClick={() =>
                      setModal({ resultId: r.resultId!, ticker: r.ticker })
                    }
                    className="text-xs text-primary underline hover:opacity-80"
                  >
                    Find similar
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {chartTicker && (
        <ChartModal ticker={chartTicker} onClose={() => setChartTicker(null)} />
      )}
      {modal && (
        <SimilarModal
          resultId={modal.resultId}
          ticker={modal.ticker}
          onClose={() => setModal(null)}
        />
      )}
    </>
  );
}
