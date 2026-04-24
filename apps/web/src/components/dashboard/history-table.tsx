"use client";
import { useState } from "react";
import { cn } from "@/lib/utils";
import type { ScanRun } from "@/types";
import SimilarModal from "./similar-modal";

interface Props {
  runs: ScanRun[];
  userId: string;
}

export default function HistoryTable({ runs }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, unknown>>({});

  async function loadDetails(runId: string) {
    if (details[runId]) {
      setExpanded(expanded === runId ? null : runId);
      return;
    }
    const res = await fetch(`/api/proxy/scans/${runId}`);
    if (res.ok) {
      const data = await res.json();
      setDetails((prev) => ({ ...prev, [runId]: data }));
    }
    setExpanded(runId);
  }

  if (runs.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        No scan history yet. Run a scan from the Dashboard.
      </p>
    );
  }

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-xs bg-secondary">
            <th className="px-4 py-2 text-left">Screener</th>
            <th className="px-4 py-2 text-left">Status</th>
            <th className="px-4 py-2 text-right">Results</th>
            <th className="px-4 py-2 text-right">Tokens</th>
            <th className="px-4 py-2 text-left">Triggered</th>
            <th className="px-4 py-2 text-left">Date</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <>
              <tr
                key={run.id}
                className="border-b border-border/50 hover:bg-accent/30 cursor-pointer"
                onClick={() => loadDetails(run.id)}
              >
                <td className="px-4 py-2">
                  {(run as never as { screener_configs?: { name: string } })
                    .screener_configs?.name || "—"}
                </td>
                <td className="px-4 py-2">
                  <span
                    className={cn(
                      "text-xs px-2 py-0.5 rounded",
                      run.status === "completed"
                        ? "bg-green-900/30 text-green-400"
                        : run.status === "failed"
                          ? "bg-red-900/30 text-red-400"
                          : "bg-secondary text-muted-foreground",
                    )}
                  >
                    {run.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-right">{run.result_count}</td>
                <td className="px-4 py-2 text-right text-muted-foreground">
                  {run.tokens_used.toLocaleString()}
                </td>
                <td className="px-4 py-2 text-xs text-muted-foreground capitalize">
                  {run.triggered_by}
                </td>
                <td className="px-4 py-2 text-xs text-muted-foreground">
                  {new Date(run.created_at).toLocaleString()}
                </td>
              </tr>
              {expanded === run.id && details[run.id] && (
                <tr key={`${run.id}-detail`} className="bg-secondary/30">
                  <td colSpan={6} className="px-4 py-3">
                    <ResultsDetail
                      data={details[run.id] as { results: unknown[] }}
                    />
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResultsDetail({ data }: { data: { results: unknown[] } }) {
  const results = data?.results || [];
  if (!results.length)
    return (
      <p className="text-xs text-muted-foreground">No results for this scan.</p>
    );
  return (
    <div className="space-y-2">
      {results.map((r: unknown) => {
        const result = r as {
          id: string;
          ticker: string;
          company_name: string;
          premarket_change_pct: number;
          ai_analyses?: {
            trading_signal: string;
            catalyst_type: string;
            analysis_text: string;
            news_url: string;
          }[];
        };
        const analysis = result.ai_analyses?.[0];
        return (
          <ResultRow key={result.id} result={result} analysis={analysis} />
        );
      })}
    </div>
  );
}

type AnalysisRow = {
  trading_signal: string;
  catalyst_type: string;
  analysis_text: string;
  news_url: string;
};

function ResultRow({
  result,
  analysis,
}: {
  result: {
    id: string;
    ticker: string;
    company_name: string;
    premarket_change_pct: number;
  };
  analysis?: AnalysisRow;
}) {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="space-y-1">
      <div className="flex gap-4 text-xs items-start">
        <span className="font-bold w-16">{result.ticker}</span>
        <span
          className={
            result.premarket_change_pct >= 0 ? "text-bullish" : "text-bearish"
          }
        >
          {result.premarket_change_pct >= 0 ? "+" : ""}
          {result.premarket_change_pct?.toFixed(1)}%
        </span>
        {analysis && (
          <>
            <span className="text-muted-foreground uppercase">
              {analysis.trading_signal?.replace(/_/g, " ")}
            </span>
            <span className="text-muted-foreground flex-1">
              {analysis.analysis_text}
            </span>
            {analysis.news_url && (
              <a
                href={analysis.news_url}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 text-xs text-muted-foreground underline hover:text-foreground"
              >
                news ↗
              </a>
            )}
          </>
        )}
        {analysis && (
          <button
            onClick={() => setModalOpen(true)}
            className="shrink-0 text-xs text-primary underline hover:opacity-80"
          >
            Find similar
          </button>
        )}
      </div>
      {modalOpen && (
        <SimilarModal
          resultId={result.id}
          ticker={result.ticker}
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  );
}
