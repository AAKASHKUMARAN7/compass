import type { ReactNode } from "react";

import { cn } from "@/lib/format";
import type { Confidence, DocumentStatus } from "@/types/api";

type Tone = "neutral" | "brand" | "positive" | "caution" | "critical";

const TONES: Record<Tone, string> = {
  neutral: "border-line bg-canvas text-ink-muted",
  brand: "border-brand-200 bg-brand-50 text-brand-700",
  positive: "border-emerald-200 bg-emerald-50 text-emerald-700",
  caution: "border-amber-200 bg-amber-50 text-amber-800",
  critical: "border-rose-200 bg-rose-50 text-rose-700",
};

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-2xs font-semibold",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const STATUS_TONE: Record<DocumentStatus, Tone> = {
  published: "positive",
  processing: "brand",
  archived: "neutral",
  failed: "critical",
};

const STATUS_LABEL: Record<DocumentStatus, string> = {
  published: "Published",
  processing: "Processing",
  archived: "Archived",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <Badge tone={STATUS_TONE[status]}>
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          status === "published" && "bg-emerald-500",
          status === "processing" && "bg-brand-500",
          status === "archived" && "bg-slate-400",
          status === "failed" && "bg-rose-500",
        )}
      />
      {STATUS_LABEL[status]}
    </Badge>
  );
}

const CONFIDENCE_TONE: Record<Confidence, Tone> = {
  high: "positive",
  medium: "caution",
  low: "caution",
  none: "critical",
};

export function ConfidenceBadge({
  confidence,
  score,
}: {
  confidence: Confidence;
  score?: number;
}) {
  const label =
    confidence === "none"
      ? "No supporting policy"
      : `${confidence[0]?.toUpperCase()}${confidence.slice(1)} confidence`;

  return (
    <Badge tone={CONFIDENCE_TONE[confidence]}>
      {label}
      {typeof score === "number" && confidence !== "none" ? (
        <span className="numeric font-normal opacity-70">{score.toFixed(2)}</span>
      ) : null}
    </Badge>
  );
}
