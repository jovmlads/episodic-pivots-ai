"use client";
import { useState } from "react";
import { loadStripe } from "@stripe/stripe-js";

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!);

export default function CheckoutButton({ userId }: { userId: string }) {
  const [loading, setLoading] = useState(false);

  async function handleCheckout() {
    setLoading(true);
    const res = await fetch("/api/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
    });
    const { sessionId } = await res.json();
    const stripe = await stripePromise;
    await stripe?.redirectToCheckout({ sessionId });
    setLoading(false);
  }

  return (
    <button
      onClick={handleCheckout}
      disabled={loading}
      className="w-full bg-primary text-primary-foreground py-3 rounded font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
    >
      {loading ? "Redirecting..." : "Subscribe — $0.01/month"}
    </button>
  );
}
