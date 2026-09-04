"use client";

import { useState } from "react";
import { ChevronDown, FileText } from "lucide-react";

import { cn, formatDate } from "@/lib/format";
import { JURISDICTION_LABELS } from "@/lib/persona";
import type { Citation } from "@/types/api";

export function CitationCard({
  citation,
  highlighted,
}: {
  citation: Citation;
  highlighted: boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <article
      id={`citation-${citation.marker}`}
      className={cn(
        "scroll-mt-24 rounded-lg border bg-surface transition-all duration-300",
        highlighted
          ? "border-brand-400 ring-4 ring-brand-500/10"
          : "border-line hover:border-slate-300",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 px-3.5 py-3 text-left"
      >
        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border border-brand-200 bg-brand-50 text-[11px] font-semibold text-brand-700">
          {citation.marker}
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5 shrink-0 text-ink-subtle" aria-hidden />
            <span className="truncate text-[13px] font-semibold text-ink">
              {citation.document_title}
            </span>
          </span>

          <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-2xs text-ink-muted">
            {citation.section ? (
              <span className="font-medium text-ink-muted">{citation.section}</span>
            ) : (
              <span className="italic text-ink-subtle">Unlabelled section</span>
            )}
            {citation.page ? (
              <>
                <Dot />
                <span>Page {citation.page}</span>
              </>
            ) : null}
            <Dot />
            <span>{citation.version_label}</span>
            <Dot />
            <span
              className={cn(
                "rounded px-1 py-px font-medium",
                citation.jurisdiction === "global"
                  ? "bg-slate-100 text-ink-muted"
                  : "bg-brand-50 text-brand-700",
              )}
            >
              {JURISDICTION_LABELS[citation.jurisdiction]}
            </span>
            {citation.effective_date ? (
              <>
                <Dot />
                <span>Effective {formatDate(citation.effective_date)}</span>
              </>
            ) : null}
          </span>
        </span>

        <span className="flex shrink-0 items-center gap-2">
          <RelevanceMeter value={citation.relevance} />
          <ChevronDown
            className={cn(
              "h-4 w-4 text-ink-subtle transition-transform duration-200",
              open && "rotate-180",
            )}
            aria-hidden
          />
        </span>
      </button>

      {open ? (
        <div className="border-t border-line px-3.5 py-3">
          <p className="label-caps mb-1.5">Source text</p>
          <blockquote className="border-l-2 border-brand-200 pl-3 text-[13px] leading-relaxed text-ink-muted">
            {citation.excerpt}
          </blockquote>
          <p className="mt-2.5 font-mono text-[10px] text-ink-subtle">
            {citation.chunk_id} · owner: {citation.owner || "unassigned"}
          </p>
        </div>
      ) : null}
    </article>
  );
}

function Dot() {
  return <span className="text-ink-subtle/60">·</span>;
}

/** Compact visual for retrieval score, so relevance is scannable across sources. */
function RelevanceMeter({ value }: { value: number }) {
  const filled = Math.round(Math.min(1, Math.max(0, value)) * 4);
  return (
    <span
      className="flex items-end gap-[2px]"
      title={`Retrieval relevance ${value.toFixed(3)}`}
      aria-label={`Relevance ${(value * 100).toFixed(0)} percent`}
    >
      {[0, 1, 2, 3].map((index) => (
        <span
          key={index}
          className={cn(
            "w-[3px] rounded-sm transition-colors",
            index === 0 && "h-1.5",
            index === 1 && "h-2",
            index === 2 && "h-2.5",
            index === 3 && "h-3",
            index < filled ? "bg-brand-500" : "bg-slate-200",
          )}
        />
      ))}
    </span>
  );
}
