import { createClient } from "@/lib/supabase/server";
import ScreenerSettings from "@/components/settings/screener-settings";

export default async function SettingsPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  const { data: configs } = await supabase
    .from("screener_configs")
    .select("*")
    .eq("user_id", user!.id)
    .order("created_at", { ascending: false });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Screener Settings</h1>
      <ScreenerSettings userId={user!.id} initialConfigs={configs || []} />
    </div>
  );
}
