"use client";
import { useState, useRef } from "react";
import { toast } from "sonner";
import { Play, Loader2 } from "lucide-react";
import { formatPct, formatVolume, signalColor, cn } from "@/lib/utils";
import type { ScanRun, ScanSSEEvent, ScreenerConfig } from "@/types";

interface Props {
  userId: string;
  initialRuns: ScanRun[];
  configs: Pick<ScreenerConfig, "id" | "name" | "scan_type" | "is_active">[];
}

export default function ScanDashboard({ userId, initialRuns, configs }: Props) {
  const [selectedConfig, setSelectedConfig] = useState(configs[0]?.id || "");
  const [scanning, setScanning] = useState(false);
  const [events, setEvents] = useState<ScanSSEEvent[]>([]);
  const [runs] = useState<ScanRun[]>(initialRuns);
  const abortRef = useRef<AbortController | null>(null);

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
            setEvents(prev => [...prev, event]);
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

  const results = events.filter(e => e.type === "result");
  const startEvent = events.find(e => e.type === "start");
  const completeEvent = events.find(e => e.type === "complete");
  const noResults = events.find(e => e.type === "no_results");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-bold">Dashboard</h1>
        <div className="flex items-center gap-2 ml-auto">
          <select
            value={selectedConfig}
            onChange={e => setSelectedConfig(e.target.value)}
            className="bg-secondary border border-border rounded px-3 py-1.5 text-sm text-foreground"
          >
            {configs.length === 0 && <option value="">No configs — create one in Screener</option>}
            {configs.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <button
            onClick={triggerScan}
            disabled={scanning || !selectedConfig}
            className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-1.5 rounded text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {scanning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {scanning ? "Scanning..." : "Run Scan"}
          </button>
        </div>
      </div>

      {/* Live scan results */}
      {(events.length > 0 || scanning) && (
        <div className="border border-border rounded-lg overflow-hidden">
          <div className="px-4 py-2 bg-secondary border-b border-border flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              {scanning ? "Scanning..." : `Scan complete`}
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

          {results.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground text-xs">
                  <th className="px-4 py-2 text-left">Ticker</th>
                  <th className="px-4 py-2 text-right">PM Chg</th>
                  <th className="px-4 py-2 text-left">Signal</th>
                  <th className="px-4 py-2 text-left">Catalyst</th>
                  <th className="px-4 py-2 text-left">Analysis</th>
                  <th className="px-4 py-2 text-left">News</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <tr key={i} className="border-b border-border/50 hover:bg-accent/30 transition-colors">
                    <td className="px-4 py-2 font-bold">{r.ticker}</td>
                    <td className={cn(
                      "px-4 py-2 text-right font-mono",
                      (r.premarket_change_pct ?? 0) >= 0 ? "text-bullish" : "text-bearish"
                    )}>
                      {formatPct(r.premarket_change_pct ?? 0)}
                    </td>
                    <td className={cn("px-4 py-2 uppercase text-xs font-bold", signalColor(r.trading_signal as never))}>
                      {r.trading_signal?.replace("_", " ")}
                    </td>
                    <td className="px-4 py-2 text-xs text-muted-foreground capitalize">
                      {r.catalyst_type?.replace(/_/g, " ") || "—"}
                    </td>
                    <td className="px-4 py-2 text-xs max-w-xs">{r.analysis_text}</td>
                    <td className="px-4 py-2">
                      {r.news_url && (
                        <a
                          href={r.news_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-muted-foreground underline hover:text-foreground"
                        >
                          {r.web_search_used ? "web" : "news"}
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Recent scan runs */}
      {runs.length > 0 && events.length === 0 && (
        <div className="border border-border rounded-lg overflow-hidden">
          <div className="px-4 py-2 bg-secondary border-b border-border">
            <span className="text-xs font-medium text-muted-foreground">Recent Scans</span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-muted-foreground text-xs">
                <th className="px-4 py-2 text-left">Config</th>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-right">Results</th>
                <th className="px-4 py-2 text-left">Triggered</th>
                <th className="px-4 py-2 text-left">Date</th>
              </tr>
            </thead>
            <tbody>
              {runs.map(run => (
                <tr key={run.id} className="border-b border-border/50 hover:bg-accent/30">
                  <td className="px-4 py-2">{(run as never as {screener_configs?: {name:string}}).screener_configs?.name || "—"}</td>
                  <td className="px-4 py-2">
                    <span className={cn(
                      "text-xs px-2 py-0.5 rounded",
                      run.status === "completed" ? "bg-green-900/30 text-green-400" :
                      run.status === "failed" ? "bg-red-900/30 text-red-400" :
                      "bg-secondary text-muted-foreground"
                    )}>
                      {run.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right">{run.result_count}</td>
                  <td className="px-4 py-2 text-xs text-muted-foreground capitalize">{run.triggered_by}</td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {new Date(run.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
