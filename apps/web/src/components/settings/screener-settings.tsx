"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, Send, Loader2 } from "lucide-react";
import type { ScreenerConfig } from "@/types";

interface Props {
  userId: string;
  initialConfigs: ScreenerConfig[];
}

const SCAN_TYPES = [
  { value: "premarket_gainers", label: "Pre-market Gainers" },
  { value: "premarket_losers", label: "Pre-market Losers" },
  { value: "gap_up", label: "Gap Up at Open" },
  { value: "gap_down", label: "Gap Down at Open" },
];
const MARKETS = ["america", "canada", "uk", "germany", "australia", "india"];

export default function ScreenerSettings({ userId, initialConfigs }: Props) {
  const [configs, setConfigs] = useState<ScreenerConfig[]>(initialConfigs);
  const [activeTab, setActiveTab] = useState<"menu" | "ai">("menu");

  // Menu form state
  const [form, setForm] = useState({
    name: "",
    scan_type: "premarket_gainers",
    market: "america",
    min_pm_change: 3,
    max_price: 50,
    min_price: 1,
    max_float_m: 50,
    min_rel_volume: 2,
    result_limit: 20,
    schedule_cron: "",
  });

  // AI chat state
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<{role: "user" | "ai"; text: string}[]>([]);
  const [pendingConfig, setPendingConfig] = useState<Partial<ScreenerConfig> | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  async function handleMenuSave() {
    const filters = [
      { left: "type", operation: "equal", right: "stock" },
      { left: "premarket_change", operation: scan_type_is_negative() ? "less" : "greater", right: scan_type_is_negative() ? -form.min_pm_change : form.min_pm_change },
      { left: "close", operation: "in_range", right: [form.min_price, form.max_price] },
      { left: "relative_volume", operation: "greater", right: form.min_rel_volume },
      { left: "float_shares_outstanding", operation: "less", right: form.max_float_m * 1_000_000 },
    ];
    const body = {
      name: form.name || `${form.scan_type} ${form.market}`,
      scan_type: form.scan_type,
      market: form.market,
      filters,
      columns: [],
      sort_by: "premarket_change",
      sort_order: scan_type_is_negative() ? "asc" : "desc",
      result_limit: form.result_limit,
      schedule_cron: form.schedule_cron || null,
    };
    const res = await fetch("/api/proxy/configs", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-User-Id": userId },
      body: JSON.stringify(body),
    });
    if (!res.ok) { toast.error("Failed to save config"); return; }
    const newConfig = await res.json();
    setConfigs(prev => [newConfig, ...prev]);
    toast.success("Config saved");
  }

  function scan_type_is_negative() {
    return form.scan_type === "premarket_losers" || form.scan_type === "gap_down";
  }

  async function handleAiSubmit() {
    if (!chatInput.trim()) return;
    const userMsg = chatInput;
    setChatInput("");
    setChatMessages(prev => [...prev, { role: "user", text: userMsg }]);
    setAiLoading(true);
    setPendingConfig(null);
    let aiText = "";
    try {
      const res = await fetch("/api/proxy/analyses/screener-nl", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-User-Id": userId },
        body: JSON.stringify({ user_input: userMsg }),
      });
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
          const evt = JSON.parse(raw);
          if (evt.type === "chunk") aiText += evt.text;
          if (evt.type === "final") {
            if (evt.success && evt.config) setPendingConfig(evt.config);
          }
        }
      }
    } catch {
      aiText = "Error generating config. Please try again.";
    }
    setChatMessages(prev => [...prev, { role: "ai", text: aiText }]);
    setAiLoading(false);
  }

  async function saveAiConfig() {
    if (!pendingConfig) return;
    const res = await fetch("/api/proxy/configs", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-User-Id": userId },
      body: JSON.stringify(pendingConfig),
    });
    if (!res.ok) { toast.error("Failed to save config"); return; }
    const newConfig = await res.json();
    setConfigs(prev => [newConfig, ...prev]);
    setPendingConfig(null);
    toast.success("Config saved from AI suggestion");
  }

  async function deleteConfig(id: string) {
    await fetch(`/api/proxy/configs/${id}`, { method: "DELETE", headers: { "X-User-Id": userId } });
    setConfigs(prev => prev.filter(c => c.id !== id));
    toast.success("Config deleted");
  }

  return (
    <div className="space-y-6">
      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {(["menu", "ai"] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm border-b-2 transition-colors ${
              activeTab === tab
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab === "menu" ? "Menu Builder" : "AI Assistant"}
          </button>
        ))}
      </div>

      {/* Menu builder */}
      {activeTab === "menu" && (
        <div className="grid grid-cols-2 gap-4 max-w-2xl">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Name</label>
            <input
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="My screener"
              className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Scan Type</label>
            <select
              value={form.scan_type}
              onChange={e => setForm(f => ({ ...f, scan_type: e.target.value }))}
              className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm"
            >
              {SCAN_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Market</label>
            <select
              value={form.market}
              onChange={e => setForm(f => ({ ...f, market: e.target.value }))}
              className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm capitalize"
            >
              {MARKETS.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Min PM Change (%)</label>
            <input
              type="number"
              value={form.min_pm_change}
              onChange={e => setForm(f => ({ ...f, min_pm_change: +e.target.value }))}
              className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Price Range ($)</label>
            <div className="flex gap-2">
              <input type="number" value={form.min_price} onChange={e => setForm(f => ({ ...f, min_price: +e.target.value }))} className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm" placeholder="Min" />
              <input type="number" value={form.max_price} onChange={e => setForm(f => ({ ...f, max_price: +e.target.value }))} className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm" placeholder="Max" />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Max Float (M shares)</label>
            <input type="number" value={form.max_float_m} onChange={e => setForm(f => ({ ...f, max_float_m: +e.target.value }))} className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm" />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Min Relative Volume</label>
            <input type="number" step="0.5" value={form.min_rel_volume} onChange={e => setForm(f => ({ ...f, min_rel_volume: +e.target.value }))} className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm" />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Max Results</label>
            <input type="number" min={1} max={50} value={form.result_limit} onChange={e => setForm(f => ({ ...f, result_limit: +e.target.value }))} className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm" />
          </div>
          <div className="col-span-2 space-y-1">
            <label className="text-xs text-muted-foreground">Schedule (cron, optional — e.g. <code>30 9 * * 1-5</code>)</label>
            <input value={form.schedule_cron} onChange={e => setForm(f => ({ ...f, schedule_cron: e.target.value }))} placeholder="Leave blank for manual only" className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm" />
          </div>
          <div className="col-span-2">
            <button onClick={handleMenuSave} className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded text-sm font-medium hover:opacity-90">
              <Plus size={14} /> Save Config
            </button>
          </div>
        </div>
      )}

      {/* AI assistant */}
      {activeTab === "ai" && (
        <div className="max-w-2xl space-y-4">
          <div className="border border-border rounded-lg min-h-48 max-h-96 overflow-y-auto p-4 space-y-3 bg-secondary/20">
            {chatMessages.length === 0 && (
              <p className="text-muted-foreground text-sm">
                Describe your screening criteria in plain English. Example: "scan pre-market gainers over 5% with float under 20M and price between $2-$20 on Nasdaq"
              </p>
            )}
            {chatMessages.map((m, i) => (
              <div key={i} className={`text-sm ${m.role === "user" ? "text-foreground" : "text-muted-foreground"}`}>
                <span className="font-bold mr-2">{m.role === "user" ? "You:" : "AI:"}</span>
                <span className="whitespace-pre-wrap">{m.text}</span>
              </div>
            ))}
            {aiLoading && <p className="text-muted-foreground text-sm animate-pulse">Analysing criteria...</p>}
          </div>
          {pendingConfig && (
            <div className="border border-green-700/50 bg-green-900/10 rounded p-3 flex items-center justify-between">
              <p className="text-sm text-green-400">Config ready: <strong>{pendingConfig.name}</strong></p>
              <button onClick={saveAiConfig} className="text-sm bg-green-700 text-white px-3 py-1 rounded hover:bg-green-600">
                Save Config
              </button>
            </div>
          )}
          <div className="flex gap-2">
            <input
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !e.shiftKey && handleAiSubmit()}
              placeholder="Describe your screening criteria..."
              className="flex-1 bg-secondary border border-border rounded px-3 py-2 text-sm"
            />
            <button
              onClick={handleAiSubmit}
              disabled={aiLoading || !chatInput.trim()}
              className="flex items-center gap-1 bg-primary text-primary-foreground px-3 py-2 rounded text-sm disabled:opacity-50"
            >
              {aiLoading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            </button>
          </div>
        </div>
      )}

      {/* Existing configs */}
      {configs.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-muted-foreground mb-2">Saved Configs</h2>
          <div className="space-y-2">
            {configs.map(c => (
              <div key={c.id} className="flex items-center justify-between border border-border rounded px-4 py-2">
                <div>
                  <p className="text-sm font-medium">{c.name}</p>
                  <p className="text-xs text-muted-foreground">{c.scan_type} · {c.market} · {c.result_limit} results{c.schedule_cron ? ` · ${c.schedule_cron}` : ""}</p>
                </div>
                <button onClick={() => deleteConfig(c.id)} className="text-muted-foreground hover:text-destructive transition-colors">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
