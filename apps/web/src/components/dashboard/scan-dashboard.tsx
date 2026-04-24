"use client";
import { useState, useRef } from "react";
import { toast } from "sonner";
import { Play, Loader2, ChevronDown, ChevronRight } from "lucide-react";
import { formatPct, signalColor, cn } from "@/lib/utils";
import ResultsTable, { type ResultRow } from "./results-table";
import type {
  ScanRun,
  ScanSSEEvent,
  ScanResult,
  ScreenerConfig,
} from "@/types";

interface Props {
  userId: string;
  initialRuns: ScanRun[];
  configs: Pick<ScreenerConfig, "id" | "name" | "scan_type" | "is_active">[];
}

function eventsToRowMap(events: ScanSSEEvent[]): Map<string, ResultRow> {
  const map = new Map<string, ResultRow>();
  for (const e of events) {
    if (e.type === "ticker" && e.ticker) {
      map.set(e.ticker, {
        ticker: e.ticker,
        pct: e.premarket_change_pct ?? 0,
        analysing: true,
      });
    } else if (e.type === "result" && e.ticker) {
      map.set(e.ticker, {
        ticker: e.ticker,
        pct: e.premarket_change_pct ?? 0,
        signal: e.trading_signal,
        catalyst: e.catalyst_type,
        analysis: e.analysis_text,
        newsUrl: e.news_url,
        webSearch: e.web_search_used,
        analysing: false,
        resultId: e.result_id,
      });
    } else if (e.type === "error" && e.ticker) {
      const existing = map.get(e.ticker);
      map.set(e.ticker, {
        ticker: e.ticker,
        pct: existing?.pct ?? 0,
        analysis: e.message || "Analysis failed",
        analysing: false,
      });
    }
  }
  return map;
}

function storedResultsToRows(results: ScanResult[]): ResultRow[] {
  return results.map((r) => {
    const a = r.ai_analyses?.[0];
    return {
      ticker: r.ticker,
      pct: r.premarket_change_pct,
      signal: a?.trading_signal,
      catalyst: a?.catalyst_type,
      analysis: a?.analysis_text,
      newsUrl: a?.news_url,
      webSearch: a?.web_search_used,
      resultId: r.id,
    };
  });
}

export default function ScanDashboard({ userId, initialRuns, configs }: Props) {
  const [selectedConfig, setSelectedConfig] = useState(configs[0]?.id || "");
  const [scanning, setScanning] = useState(false);
  const [events, setEvents] = useState<ScanSSEEvent[]>([]);
  const [runs] = useState<ScanRun[]>(initialRuns);
  const abortRef = useRef<AbortController | null>(null);

  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [runResults, setRunResults] = useState<Record<string, ResultRow[]>>({});
  const [loadingRunId, setLoadingRunId] = useState<string | null>(null);

  async function triggerScan() {
    if (!selectedConfig) return toast.error("Select a screener config first");
    setScanning(true);
    setEvents([]);
    abortRef.current = new AbortController();

    try {
      const res = await fetch("/api/scans/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config_id: selectedConfig }),
        signal: abortRef.current.signal,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Scan failed");
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (raw === "[DONE]") break;
          try {
            const event: ScanSSEEvent = JSON.parse(raw);
            setEvents((prev) => [...prev, event]);
            if (event.type === "complete") {
              toast.success(`Scan complete — ${event.total_results} result(s)`);
            }
          } catch {}
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name !== "AbortError") {
        toast.error((err as Error).message || "Scan error");
      }
    } finally {
      setScanning(false);
    }
  }

  async function toggleRun(runId: string) {
    if (expandedRunId === runId) {
      setExpandedRunId(null);
      return;
    }
    setExpandedRunId(runId);
    if (runResults[runId]) return;

    setLoadingRunId(runId);
    try {
      const res = await fetch(`/api/proxy/scans/${runId}`);
      if (!res.ok) throw new Error("Failed to load results");
      const data = await res.json();
      setRunResults((prev) => ({
        ...prev,
        [runId]: storedResultsToRows(data.results || []),
      }));
    } catch {
      toast.error("Could not load scan results");
    } finally {
      setLoadingRunId(null);
    }
  }

  const rowMap = eventsToRowMap(events);
  const liveResults = Array.from(rowMap.values());
  const startEvent = events.find((e) => e.type === "start");
  const completeEvent = events.find((e) => e.type === "complete");
  const noResults = events.find((e) => e.type === "no_results");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-bold">Dashboard</h1>
        <div className="flex items-center gap-2 ml-auto">
          <select
            value={selectedConfig}
            onChange={(e) => setSelectedConfig(e.target.value)}
            className="bg-secondary border border-border rounded px-3 py-1.5 text-sm text-foreground"
          >
            {configs.length === 0 && (
              <option value="">No configs — create one in Screener</option>
            )}
            {configs.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <button
            onClick={triggerScan}
            disabled={scanning || !selectedConfig}
            className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-1.5 rounded text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {scanning ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Play size={14} />
            )}
            {scanning ? "Scanning..." : "Run Scan"}
          </button>
        </div>
      </div>

      {/* Empty state */}
      {runs.length === 0 && events.length === 0 && !scanning && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <p className="text-muted-foreground">
            No screeners have been run yet.
          </p>
          <p className="text-sm text-muted-foreground/60 mt-1">
            Select a screener from the dropdown above and click Run Scan to get
            started.
          </p>
        </div>
      )}

      {/* Live scan results */}
      {(events.length > 0 || scanning) && (
        <div className="border border-border rounded-lg overflow-hidden">
          <div className="px-4 py-2 bg-secondary border-b border-border flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              {scanning ? "Scanning..." : "Scan complete"}
              {startEvent && ` — ${startEvent.total} ticker(s)`}
            </span>
            {completeEvent && (
              <span className="text-xs text-muted-foreground">
                {completeEvent.total_tokens?.toLocaleString()} tokens
              </span>
            )}
          </div>
          {noResults && (
            <div className="px-4 py-6 text-center text-muted-foreground text-sm">
              {noResults.message}
            </div>
          )}
          {liveResults.length > 0 && <ResultsTable rows={liveResults} />}
        </div>
      )}

      {/* Recent scan runs */}
      {runs.length > 0 && events.length === 0 && (
        <div className="border border-border rounded-lg overflow-hidden">
          <div className="px-4 py-2 bg-secondary border-b border-border">
            <span className="text-xs font-medium text-muted-foreground">
              Recent Scans
            </span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-muted-foreground text-xs">
                <th className="px-4 py-2 text-left w-6"></th>
                <th className="px-4 py-2 text-left">Screener</th>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-right">Results</th>
                <th className="px-4 py-2 text-left">Triggered</th>
                <th className="px-4 py-2 text-left">Date</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <>
                  <tr
                    key={run.id}
                    onClick={() =>
                      run.status === "completed" && toggleRun(run.id)
                    }
                    className={cn(
                      "border-b border-border/50 hover:bg-accent/30",
                      run.status === "completed" && "cursor-pointer",
                    )}
                  >
                    <td className="px-4 py-2 text-muted-foreground">
                      {run.status === "completed" &&
                        (loadingRunId === run.id ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : expandedRunId === run.id ? (
                          <ChevronDown size={12} />
                        ) : (
                          <ChevronRight size={12} />
                        ))}
                    </td>
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
                    <td className="px-4 py-2 text-xs text-muted-foreground capitalize">
                      {run.triggered_by}
                    </td>
                    <td className="px-4 py-2 text-xs text-muted-foreground">
                      {new Date(run.created_at).toLocaleString()}
                    </td>
                  </tr>
                  {expandedRunId === run.id && (
                    <tr
                      key={`${run.id}-expanded`}
                      className="border-b border-border/50 bg-secondary/20"
                    >
                      <td colSpan={6} className="p-0">
                        <ResultsTable rows={runResults[run.id] || []} />
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
