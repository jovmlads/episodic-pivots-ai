import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { TradingSignal } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPct(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatVolume(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toString();
}

export function formatMarketCap(value: number | null): string {
  if (!value) return "N/A";
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
}

export function signalColor(signal: TradingSignal | null | undefined): string {
  switch (signal) {
    case "strong_buy": return "text-green-500 font-bold";
    case "buy": return "text-green-400";
    case "watch": return "text-yellow-400";
    case "skip": return "text-gray-400";
    case "short": return "text-red-400";
    case "strong_short": return "text-red-500 font-bold";
    default: return "text-gray-400";
  }
}

export function signalBadgeVariant(signal: TradingSignal | null | undefined) {
  switch (signal) {
    case "strong_buy":
    case "buy":
      return "bullish";
    case "short":
    case "strong_short":
      return "bearish";
    default:
      return "neutral";
  }
}

export function isTrialActive(trialEndsAt: string): boolean {
  return new Date(trialEndsAt) > new Date();
}
