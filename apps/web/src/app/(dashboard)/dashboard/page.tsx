import { createClient } from "@/lib/supabase/server";
import ScanDashboard from "@/components/dashboard/scan-dashboard";

export default async function DashboardPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  const [runsResult, configsResult] = await Promise.all([
    supabase
      .from("scan_runs")
      .select("*, screener_configs(name)")
      .eq("user_id", user!.id)
      .order("created_at", { ascending: false })
      .limit(10),
    supabase
      .from("screener_configs")
      .select("id, name, scan_type, is_active")
      .eq("user_id", user!.id)
      .eq("is_active", true),
  ]);

  return (
    <ScanDashboard
      userId={user!.id}
      initialRuns={runsResult.data || []}
      configs={configsResult.data || []}
    />
  );
}
