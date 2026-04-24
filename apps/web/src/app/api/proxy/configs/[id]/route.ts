import { createClient } from "@/lib/supabase/server";

const API_URL = process.env.API_URL || "http://localhost:8000";

export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return new Response("Unauthorized", { status: 401 });

  const { id } = await params;
  const body = await request.json();
  const upstream = await fetch(`${API_URL}/configs/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", "X-User-Id": user.id },
    body: JSON.stringify(body),
  });
  const data = await upstream.json();
  return Response.json(data, { status: upstream.status });
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return new Response("Unauthorized", { status: 401 });

  const { id } = await params;
  const upstream = await fetch(`${API_URL}/configs/${id}`, {
    method: "DELETE",
    headers: { "X-User-Id": user.id },
  });
  return new Response(null, { status: upstream.status });
}
