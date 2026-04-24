import { createClient } from "@/lib/supabase/server";

const API_URL = process.env.API_URL || "http://localhost:8000";

export async function GET(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return new Response("Unauthorized", { status: 401 });

  const { searchParams } = new URL(request.url);
  const resultId = searchParams.get("result_id");
  const limit = searchParams.get("limit") || "5";
  if (!resultId) return new Response("Missing result_id", { status: 400 });

  const upstream = await fetch(
    `${API_URL}/analyses/similar?result_id=${resultId}&limit=${limit}`,
    { headers: { "X-User-Id": user.id } },
  );
  const data = await upstream.json();
  return Response.json(data, { status: upstream.status });
}
