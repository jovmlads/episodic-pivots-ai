import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  if (code) {
    const supabase = await createClient();
    await supabase.auth.exchangeCodeForSession(code);

    // Create default notification settings for new users (ignore if already exists)
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (user) {
      const { data: existing } = await supabase
        .from("notification_settings")
        .select("id")
        .eq("user_id", user.id)
        .limit(1);
      if (!existing || existing.length === 0) {
        await supabase.from("notification_settings").insert({
          user_id: user.id,
          email: user.email,
          notify_on_scan_complete: true,
          notify_on_budget_warning: true,
        });
      }
    }
  }
  return NextResponse.redirect(`${origin}/dashboard`);
}
