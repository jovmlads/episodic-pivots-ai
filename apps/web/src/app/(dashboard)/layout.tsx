import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import Sidebar from "@/components/layout/sidebar";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select(
      "email, is_admin, trial_ends_at, monthly_token_budget, stripe_status",
    )
    .eq("id", user.id)
    .single();

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar profile={profile} />
      <main className="flex-1 overflow-y-auto p-6">{children}</main>
    </div>
  );
}
