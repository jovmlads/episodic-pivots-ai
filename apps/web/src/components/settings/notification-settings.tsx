"use client";
import { useState } from "react";
import { toast } from "sonner";

interface Props {
  userId: string;
  userEmail: string;
  initialSettings: { email: string; notify_on_scan_complete: boolean; notify_on_budget_warning: boolean } | null;
  usage: { tokens_total: number; tokens_input: number; tokens_output: number; month_year: string } | null;
  profile: { monthly_token_budget: number; trial_ends_at: string; stripe_status: string | null } | null;
}

export default function NotificationSettings({ userId, userEmail, initialSettings, usage, profile }: Props) {
  const [email, setEmail] = useState(initialSettings?.email || userEmail);
  const [onScan, setOnScan] = useState(initialSettings?.notify_on_scan_complete ?? true);
  const [onBudget, setOnBudget] = useState(initialSettings?.notify_on_budget_warning ?? true);
  const [saving, setSaving] = useState(false);

  const budget = profile?.monthly_token_budget || 1_000_000;
  const used = usage?.tokens_total || 0;
  const pct = Math.min(100, Math.round((used / budget) * 100));
  const trialDaysLeft = profile ? Math.max(0, Math.ceil((new Date(profile.trial_ends_at).getTime() - Date.now()) / 86400000)) : 0;

  async function save() {
    setSaving(true);
    const res = await fetch("/api/proxy/notification-settings", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-User-Id": userId },
      body: JSON.stringify({ email, notify_on_scan_complete: onScan, notify_on_budget_warning: onBudget }),
    });
    setSaving(false);
    if (res.ok) toast.success("Settings saved");
    else toast.error("Failed to save settings");
  }

  return (
    <div className="space-y-6 max-w-lg">
      {/* Token usage */}
      <div className="border border-border rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-medium">Token Usage — {usage?.month_year || "current month"}</h2>
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{used.toLocaleString()} / {budget.toLocaleString()} tokens</span>
            <span>{pct}%</span>
          </div>
          <div className="h-2 bg-secondary rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${pct >= 80 ? "bg-red-500" : "bg-primary"}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
        {trialDaysLeft > 0 && (
          <p className="text-xs text-muted-foreground">Free trial: {trialDaysLeft} day(s) remaining</p>
        )}
      </div>

      {/* Notification settings */}
      <div className="border border-border rounded-lg p-4 space-y-4">
        <h2 className="text-sm font-medium">Email Notifications</h2>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Notification Email</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full bg-secondary border border-border rounded px-3 py-2 text-sm"
          />
        </div>
        <label className="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" checked={onScan} onChange={e => setOnScan(e.target.checked)} className="rounded" />
          <span className="text-sm">Email report after each completed scan</span>
        </label>
        <label className="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" checked={onBudget} onChange={e => setOnBudget(e.target.checked)} className="rounded" />
          <span className="text-sm">Email warning when token budget reaches 80%</span>
        </label>
        <button
          onClick={save}
          disabled={saving}
          className="bg-primary text-primary-foreground px-4 py-2 rounded text-sm font-medium hover:opacity-90 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </div>
    </div>
  );
}
