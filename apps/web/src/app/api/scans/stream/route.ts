/**
 * SSE proxy: browser → Next.js → FastAPI.
 * Attaches authenticated user_id server-side.
 */
import { createClient } from "@/lib/supabase/server";

export async function POST(request: Request) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return new Response("Unauthorized", { status: 401 });

  const body = await request.json();
  const apiUrl = process.env.API_URL || "http://localhost:8000";

  const upstream = await fetch(`${apiUrl}/scans/trigger`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": user.id,
    },
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
