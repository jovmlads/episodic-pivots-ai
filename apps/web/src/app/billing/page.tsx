import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import CheckoutButton from "./checkout-button";

export default async function BillingPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("is_admin, stripe_status, trial_ends_at")
    .eq("id", user.id)
    .single();

  // Admin or active sub → go to dashboard
  if (profile?.is_admin || ["active", "trialing"].includes(profile?.stripe_status || "")) {
    redirect("/dashboard");
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="max-w-md w-full text-center space-y-6 p-8 border border-border rounded-lg">
        <h1 className="text-2xl font-bold">Your trial has ended</h1>
        <p className="text-muted-foreground">
          Subscribe to continue using Episodic Pivot AI scanning.
        </p>
        <CheckoutButton userId={user.id} />
      </div>
    </div>
  );
}
