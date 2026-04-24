import { createClient } from "@/lib/supabase/server";

const API_URL = process.env.API_URL || "http://localhost:8000";

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return new Response("Unauthorized", { status: 401 });

  const upstream = await fetch(`${API_URL}/notification-settings`, {
    headers: { "X-User-Id": user.id },
  });
  const data = await upstream.json();
  return Response.json(data, { status: upstream.status });
}

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return new Response("Unauthorized", { status: 401 });

  const body = await request.json();
  const upstream = await fetch(`${API_URL}/notification-settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-User-Id": user.id },
    body: JSON.stringify(body),
  });
  const data = await upstream.json();
  return Response.json(data, { status: upstream.status });
}
