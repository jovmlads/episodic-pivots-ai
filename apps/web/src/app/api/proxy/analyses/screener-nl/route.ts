import { createClient } from "@/lib/supabase/server";

const API_URL = process.env.API_URL || "http://localhost:8000";

export async function POST(request: Request) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return new Response("Unauthorized", { status: 401 });

  const body = await request.json();
  const upstream = await fetch(`${API_URL}/analyses/screener-nl`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-User-Id": user.id },
    body: JSON.stringify(body),
  });

  if (!upstream.ok) {
    const err = await upstream.json().catch(() => ({ detail: upstream.statusText }));
    return new Response(JSON.stringify(err), {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
