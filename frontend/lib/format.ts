import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { Confidence, PolicyCategory } from "@/types/api";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export const CATEGORY_LABELS: Record<PolicyCategory, string> = {
  leave_and_time_off: "Leave & Time Off",
  compensation: "Compensation",
  benefits: "Benefits",
  expenses_and_travel: "Expenses & Travel",
  security_and_it: "Security & IT",
  conduct_and_compliance: "Conduct & Compliance",
  workplace: "Workplace",
  other: "Other",
};

export const CATEGORY_OPTIONS = Object.entries(CATEGORY_LABELS) as [
  PolicyCategory,
  string,
][];

export const CONFIDENCE_LABELS: Record<Confidence, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
  none: "Not answered",
};

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatPercent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatRelativeTime(value: string): string {
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return "—";

  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 60) return "just now";

  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const divisions: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, "minute"],
    [3600, "hour"],
    [86400, "day"],
    [604800, "week"],
  ];

  for (const [divisor, unit] of divisions) {
    const scaled = seconds / divisor;
    if (scaled < (unit === "minute" ? 60 : unit === "hour" ? 24 : unit === "day" ? 7 : 5)) {
      return formatter.format(-Math.round(scaled), unit);
    }
  }
  return formatDate(value);
}

export function formatLatency(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}
