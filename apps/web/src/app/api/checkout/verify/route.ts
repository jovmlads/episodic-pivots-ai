import { NextResponse } from "next/server";
import Stripe from "stripe";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { origin, searchParams } = new URL(request.url);
  const sessionId = searchParams.get("session_id");

  if (!sessionId) {
    return NextResponse.redirect(`${origin}/billing`);
  }

  const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

  let session: Stripe.Checkout.Session;
  try {
    session = await stripe.checkout.sessions.retrieve(sessionId);
  } catch {
    return NextResponse.redirect(`${origin}/billing`);
  }

  if (session.payment_status !== "paid") {
    return NextResponse.redirect(`${origin}/billing`);
  }

  const userId = session.metadata?.user_id;
  const customerId = session.customer as string;

  if (userId && customerId) {
    const supabase = await createClient();
    await supabase
      .from("profiles")
      .update({ stripe_customer_id: customerId, stripe_status: "active" })
      .eq("id", userId);
  }

  return NextResponse.redirect(`${origin}/dashboard`);
}
