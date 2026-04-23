import { createClient } from "@/lib/supabase/server";
import HistoryTable from "@/components/dashboard/history-table";

export default async function HistoryPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  const { data: runs } = await supabase
    .from("scan_runs")
    .select("*, screener_configs(name)")
    .eq("user_id", user!.id)
    .order("created_at", { ascending: false })
    .limit(100);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Scan History</h1>
      <HistoryTable runs={runs || []} userId={user!.id} />
    </div>
  );
}
