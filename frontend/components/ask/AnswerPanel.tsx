"use client";

import { useCallback, useState } from "react";
import {
  ArrowRight,
  Clock3,
  Cpu,
  Quote,
  SearchX,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";

import { AnswerBody } from "@/components/ask/AnswerBody";
import { CitationCard } from "@/components/ask/CitationCard";
import { ConfidenceBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError } from "@/lib/api";
import { cn, formatLatency } from "@/lib/format";
import type { AskResponse, FeedbackRating } from "@/types/api";

export function AnswerPanel({
  answer,
  onFollowUp,
}: {
  answer: AskResponse;
  onFollowUp: (question: string) => void;
}) {
  const { notify } = useToast();
  const [rating, setRating] = useState<FeedbackRating | null>(null);
  const [pending, setPending] = useState(false);
  const [highlighted, setHighlighted] = useState<number | null>(null);

  const validMarkers = new Set(answer.citations.map((citation) => citation.marker));

  const jumpToCitation = useCallback((marker: number) => {
    setHighlighted(marker);
    document
      .getElementById(`citation-${marker}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => setHighlighted(null), 2200);
  }, []);

  const submitFeedback = async (value: FeedbackRating) => {
    if (rating || pending) return;
    setPending(true);
    setRating(value);
    try {
      await api.sendFeedback(answer.query_id, value);
      notify({
        tone: "success",
        title: "Feedback recorded",
        description:
          value === "helpful"
            ? "Thanks — this helps rank what the policy team writes next."
            : "Logged for review by the policy owner.",
      });
    } catch (error) {
      setRating(null);
      notify({
        tone: "error",
        title: "Could not save feedback",
        description: error instanceof ApiError ? error.message : "Unexpected error.",
      });
    } finally {
      setPending(false);
    }
  };

  const refused = answer.status === "no_coverage";

  return (
    <div className="animate-fade-up space-y-4">
      <article
        className={cn(
          "overflow-hidden rounded-xl border bg-surface shadow-card",
          refused ? "border-amber-200" : "border-line",
        )}
      >
        <header
          className={cn(
            "flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3",
            refused ? "border-amber-200 bg-amber-50/60" : "border-line bg-raised",
          )}
        >
          <div className="flex items-center gap-2">
            {refused ? (
              <SearchX className="h-4 w-4 text-amber-700" aria-hidden />
            ) : (
              <Quote className="h-4 w-4 text-brand-600" aria-hidden />
            )}
            <span className="text-[13px] font-semibold text-ink">
              {refused ? "No supporting policy found" : "Answer"}
            </span>
          </div>
          <ConfidenceBadge confidence={answer.confidence} score={answer.top_score} />
        </header>

        <div className="px-5 py-4">
          {refused ? (
            <div className="space-y-3">
              <p className="text-[14.5px] leading-relaxed text-ink">{answer.answer}</p>
              <div className="rounded-lg border border-line bg-canvas px-3.5 py-3">
                <p className="text-[13px] leading-relaxed text-ink-muted">
                  The assistant only answers from published policy documents. Rather
                  than infer an answer, it recorded this question so the policy team
                  can see the gap. The best match scored{" "}
                  <span className="numeric font-semibold text-ink">
                    {answer.top_score.toFixed(2)}
                  </span>
                  , below the threshold required to answer.
                </p>
              </div>
            </div>
          ) : (
            <AnswerBody
              text={answer.answer}
              validMarkers={validMarkers}
              onCitationClick={jumpToCitation}
            />
          )}
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-raised px-5 py-2.5">
          <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1 text-2xs text-ink-subtle">
            <span className="inline-flex items-center gap-1.5">
              <Cpu className="h-3 w-3" aria-hidden />
              {answer.model ?? "extractive engine"}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Clock3 className="h-3 w-3" aria-hidden />
              {formatLatency(answer.latency_ms)}
            </span>
            {answer.generation_mode !== "generative" ? (
              <span className="rounded bg-amber-100 px-1.5 py-0.5 font-medium text-amber-800">
                {answer.generation_mode.replace(/_/g, " ")}
              </span>
            ) : null}
            <span className="font-mono text-[10px]">{answer.query_id}</span>
          </div>

          <div className="flex items-center gap-1">
            <span className="mr-1 text-2xs text-ink-subtle">Useful?</span>
            <FeedbackButton
              active={rating === "helpful"}
              disabled={rating !== null || pending}
              onClick={() => submitFeedback("helpful")}
              label="Mark answer helpful"
            >
              <ThumbsUp className="h-3.5 w-3.5" aria-hidden />
            </FeedbackButton>
            <FeedbackButton
              active={rating === "not_helpful"}
              disabled={rating !== null || pending}
              onClick={() => submitFeedback("not_helpful")}
              label="Mark answer not helpful"
              tone="negative"
            >
              <ThumbsDown className="h-3.5 w-3.5" aria-hidden />
            </FeedbackButton>
          </div>
        </footer>
      </article>

      {answer.citations.length > 0 ? (
        <section className="space-y-2">
          <div className="flex items-baseline justify-between">
            <h3 className="label-caps">
              Sources · {answer.citations.length}
            </h3>
            <p className="text-2xs text-ink-subtle">
              Every claim above traces to one of these excerpts
            </p>
          </div>
          <div className="space-y-2">
            {answer.citations.map((citation) => (
              <CitationCard
                key={citation.chunk_id}
                citation={citation}
                highlighted={highlighted === citation.marker}
              />
            ))}
          </div>
        </section>
      ) : null}

      {answer.follow_up_questions.length > 0 ? (
        <section className="space-y-2">
          <h3 className="label-caps">People usually ask next</h3>
          <div className="flex flex-wrap gap-2">
            {answer.follow_up_questions.map((question) => (
              <button
                key={question}
                type="button"
                onClick={() => onFollowUp(question)}
                className="group inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] text-ink-muted transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
              >
                {question}
                <ArrowRight
                  className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-100"
                  aria-hidden
                />
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function FeedbackButton({
  active,
  disabled,
  onClick,
  label,
  tone = "positive",
  children,
}: {
  active: boolean;
  disabled: boolean;
  onClick: () => void;
  label: string;
  tone?: "positive" | "negative";
  children: React.ReactNode;
}) {
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      aria-pressed={active}
      className={cn(
        "px-2",
        active && tone === "positive" && "bg-emerald-50 text-emerald-700",
        active && tone === "negative" && "bg-rose-50 text-rose-700",
      )}
    >
      {children}
    </Button>
  );
}
