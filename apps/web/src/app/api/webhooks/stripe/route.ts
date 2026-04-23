import { NextResponse } from "next/server";
import Stripe from "stripe";
import { createClient } from "@/lib/supabase/server";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function POST(request: Request) {
  const body = await request.text();
  const sig = request.headers.get("stripe-signature")!;

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET!);
  } catch {
    return new NextResponse("Webhook signature error", { status: 400 });
  }

  const supabase = await createClient();

  if (
    event.type === "customer.subscription.created" ||
    event.type === "customer.subscription.updated" ||
    event.type === "customer.subscription.deleted"
  ) {
    const sub = event.data.object as Stripe.Subscription;
    const customerId = sub.customer as string;

    // Find user by stripe_customer_id
    const { data: profile } = await supabase
      .from("profiles")
      .select("id")
      .eq("stripe_customer_id", customerId)
      .maybeSingle();

    if (profile) {
      await supabase.from("profiles").update({
        stripe_subscription_id: sub.id,
        stripe_status: sub.status,
      }).eq("id", profile.id);
    }
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object as Stripe.Checkout.Session;
    const userId = session.metadata?.user_id;
    const customerId = session.customer as string;
    if (userId && customerId) {
      await supabase.from("profiles").update({
        stripe_customer_id: customerId,
        stripe_status: "active",
      }).eq("id", userId);
    }
  }

  return NextResponse.json({ received: true });
}
