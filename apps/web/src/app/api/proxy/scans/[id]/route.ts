import { createClient } from "@/lib/supabase/server";

const API_URL = process.env.API_URL || "http://localhost:8000";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return new Response("Unauthorized", { status: 401 });

  const { id } = await params;
  const upstream = await fetch(`${API_URL}/scans/${id}`, {
    headers: { "X-User-Id": user.id },
  });
  const data = await upstream.json();
  return Response.json(data, { status: upstream.status });
}
