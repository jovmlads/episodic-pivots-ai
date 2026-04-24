import { createClient } from "@/lib/supabase/server";
import NotificationSettings from "@/components/settings/notification-settings";

export default async function NotificationsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { data: settings } = await supabase
    .from("notification_settings")
    .select("*")
    .eq("user_id", user!.id)
    .maybeSingle();

  // Seed defaults for users who registered before this was added
  if (!settings) {
    await supabase.from("notification_settings").insert({
      user_id: user!.id,
      email: user!.email,
      notify_on_scan_complete: true,
      notify_on_budget_warning: true,
    });
  }

  const { data: usage } = await supabase
    .from("token_usage")
    .select("tokens_total, tokens_input, tokens_output, month_year")
    .eq("user_id", user!.id)
    .order("month_year", { ascending: false })
    .limit(1)
    .maybeSingle();

  const { data: profile } = await supabase
    .from("profiles")
    .select("monthly_token_budget, trial_ends_at, stripe_status")
    .eq("id", user!.id)
    .single();

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Notifications & Usage</h1>
      <NotificationSettings
        userId={user!.id}
        userEmail={user!.email || ""}
        initialSettings={settings}
        usage={usage}
        profile={profile}
      />
    </div>
  );
}
