import { NextResponse } from "next/server";
import Stripe from "stripe";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);
  const { user_id } = await request.json();
  const origin = new URL(request.url).origin;

  const session = await stripe.checkout.sessions.create({
    mode: "subscription",
    payment_method_types: ["card"],
    line_items: [{ price: process.env.STRIPE_PRICE_ID!, quantity: 1 }],
    success_url: `${origin}/api/checkout/verify?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${origin}/billing`,
    metadata: { user_id },
  });

  return NextResponse.json({ sessionId: session.id });
}
