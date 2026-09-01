"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, BarChart3, CircleCheck, RefreshCw, TrendingUp } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, EmptyState } from "@/components/ui/Card";
import { api, ApiError } from "@/lib/api";
import {
  CATEGORY_LABELS,
  cn,
  formatLatency,
  formatNumber,
  formatPercent,
  formatRelativeTime,
} from "@/lib/format";
import type { AnalyticsOverview, QueryLogEntry } from "@/types/api";

export default function InsightsPage() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [history, setHistory] = useState<QueryLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [analytics, log] = await Promise.all([
        api.analytics(),
        api.history({ limit: 12 }),
      ]);
      setOverview(analytics);
      setHistory(log.items);
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unexpected error.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const kpis = overview?.kpis;

  return (
    <>
      <PageHeader
        eyebrow="Operations"
        title="Insights"
        description="How the assistant is performing, and which questions the knowledge base cannot yet answer."
        action={
          <Button variant="secondary" onClick={() => void load()} loading={loading}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            Refresh
          </Button>
        }
      />

      <div className="mx-auto max-w-6xl space-y-6 px-6 py-6">
        {error ? (
          <Card>
            <EmptyState
              title="Cannot load analytics"
              description={error}
              action={
                <Button variant="secondary" onClick={() => void load()}>
                  Try again
                </Button>
              }
            />
          </Card>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            label="Questions asked"
            value={kpis ? formatNumber(kpis.questions_asked) : null}
            caption={kpis ? `${formatNumber(kpis.chunks_indexed)} sections indexed` : undefined}
          />
          <Kpi
            label="Answer rate"
            value={kpis ? formatPercent(kpis.answer_rate) : null}
            caption={
              kpis ? `${formatNumber(kpis.coverage_gap_count)} unanswered` : undefined
            }
            tone={kpis && kpis.answer_rate < 0.7 ? "caution" : "positive"}
          />
          <Kpi
            label="Avg relevance"
            value={kpis ? kpis.avg_confidence_score.toFixed(2) : null}
            caption="Cosine similarity of the top source"
          />
          <Kpi
            label="Avg response"
            value={kpis ? formatLatency(kpis.avg_latency_ms) : null}
            caption={
              kpis?.helpful_rate !== null && kpis?.helpful_rate !== undefined
                ? `${formatPercent(kpis.helpful_rate)} rated helpful`
                : "No ratings yet"
            }
          />
        </div>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
          <Card>
            <CardHeader
              title="Coverage gaps"
              description="Questions the assistant declined, ranked by how often they were asked. This is the content backlog."
              action={
                overview?.coverage_gaps.length ? (
                  <Badge tone="caution">
                    {overview.coverage_gaps.length} to review
                  </Badge>
                ) : null
              }
            />
            {loading && !overview ? (
              <ListSkeleton rows={4} />
            ) : overview?.coverage_gaps.length ? (
              <ul className="divide-y divide-line">
                {overview.coverage_gaps.map((gap) => (
                  <li
                    key={gap.question}
                    className="flex items-start gap-3.5 px-5 py-3.5"
                  >
                    <AlertTriangle
                      className="mt-0.5 h-4 w-4 shrink-0 text-amber-600"
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-[13.5px] leading-snug text-ink">{gap.question}</p>
                      <p className="mt-1 text-2xs text-ink-subtle">
                        Best match scored{" "}
                        <span className="numeric font-medium">
                          {gap.best_score.toFixed(2)}
                        </span>{" "}
                        · last asked {formatRelativeTime(gap.last_asked_at)}
                      </p>
                    </div>
                    {gap.occurrences > 1 ? (
                      <Badge tone="caution">{gap.occurrences}x</Badge>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                icon={<CircleCheck className="h-5 w-5 text-emerald-600" aria-hidden />}
                title="No coverage gaps"
                description="Every question asked so far was answerable from the published policy set."
              />
            )}
          </Card>

          <div className="space-y-5">
            <Card>
              <CardHeader
                title="Most asked"
                description="Answered questions, by frequency."
              />
              {loading && !overview ? (
                <ListSkeleton rows={3} />
              ) : overview?.top_questions.length ? (
                <ul className="divide-y divide-line">
                  {overview.top_questions.slice(0, 6).map((item) => (
                    <li key={item.question} className="flex items-start gap-3 px-5 py-3">
                      <TrendingUp
                        className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-subtle"
                        aria-hidden
                      />
                      <p className="min-w-0 flex-1 text-[13px] leading-snug text-ink-muted">
                        {item.question}
                      </p>
                      <span className="numeric shrink-0 text-2xs text-ink-subtle">
                        {item.occurrences}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No questions yet" />
              )}
            </Card>

            <Card>
              <CardHeader
                title="Coverage by policy area"
                description="Documents published against questions received."
              />
              <CardBody className="space-y-2.5">
                {overview?.categories.length ? (
                  overview.categories.map((row) => {
                    const max = Math.max(
                      ...overview.categories.map((item) =>
                        Math.max(item.document_count, item.question_count),
                      ),
                      1,
                    );
                    return (
                      <div key={row.category} className="space-y-1">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="text-[12.5px] text-ink">
                            {CATEGORY_LABELS[row.category]}
                          </span>
                          <span className="numeric text-2xs text-ink-subtle">
                            {row.document_count} docs · {row.question_count} asked
                          </span>
                        </div>
                        <div className="flex h-1.5 gap-0.5 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="rounded-full bg-brand-500"
                            style={{ width: `${(row.document_count / max) * 100}%` }}
                          />
                          <div
                            className="rounded-full bg-brand-200"
                            style={{ width: `${(row.question_count / max) * 100}%` }}
                          />
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <p className="py-4 text-center text-[13px] text-ink-subtle">
                    No activity yet.
                  </p>
                )}
              </CardBody>
            </Card>
          </div>
        </div>

        <Card>
          <CardHeader
            title="Recent questions"
            description="A full audit trail of what employees asked and how the assistant responded."
          />
          {loading && history.length === 0 ? (
            <ListSkeleton rows={5} />
          ) : history.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-line">
                    <th className="label-caps px-5 py-2.5 font-semibold">Question</th>
                    <th className="label-caps px-3 py-2.5 font-semibold">Outcome</th>
                    <th className="label-caps px-3 py-2.5 text-right font-semibold">Score</th>
                    <th className="label-caps px-3 py-2.5 text-right font-semibold">Sources</th>
                    <th className="label-caps px-3 py-2.5 text-right font-semibold">Latency</th>
                    <th className="label-caps px-5 py-2.5 font-semibold">Asked</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((entry) => (
                    <tr key={entry.id} className="border-b border-line hover:bg-canvas">
                      <td className="max-w-md px-5 py-2.5">
                        <p className="truncate text-[13px] text-ink" title={entry.question}>
                          {entry.question}
                        </p>
                      </td>
                      <td className="px-3 py-2.5">
                        {entry.status === "answered" ? (
                          <Badge tone="positive">Answered</Badge>
                        ) : (
                          <Badge tone="caution">Declined</Badge>
                        )}
                      </td>
                      <td className="numeric px-3 py-2.5 text-right text-[12.5px] text-ink-muted">
                        {entry.top_score.toFixed(2)}
                      </td>
                      <td className="numeric px-3 py-2.5 text-right text-[12.5px] text-ink-muted">
                        {entry.citation_count}
                      </td>
                      <td className="numeric px-3 py-2.5 text-right text-[12.5px] text-ink-muted">
                        {formatLatency(entry.latency_ms)}
                      </td>
                      <td className="px-5 py-2.5 text-[12.5px] text-ink-muted">
                        {formatRelativeTime(entry.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              icon={<BarChart3 className="h-5 w-5" aria-hidden />}
              title="No questions logged"
              description="Ask something on the assistant page and it will appear here."
            />
          )}
        </Card>
      </div>
    </>
  );
}

function Kpi({
  label,
  value,
  caption,
  tone = "neutral",
}: {
  label: string;
  value: string | null;
  caption?: string;
  tone?: "neutral" | "positive" | "caution";
}) {
  return (
    <div className="card px-4 py-3.5">
      <p className="label-caps">{label}</p>
      {value === null ? (
        <div className="skeleton mt-1.5 h-7 w-20" />
      ) : (
        <p
          className={cn(
            "numeric mt-1 text-2xl font-semibold tracking-tight",
            tone === "caution" ? "text-caution" : "text-ink",
          )}
        >
          {value}
        </p>
      )}
      {caption ? <p className="mt-1 text-2xs text-ink-subtle">{caption}</p> : null}
    </div>
  );
}

function ListSkeleton({ rows }: { rows: number }) {
  return (
    <div className="divide-y divide-line">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="space-y-2 px-5 py-3.5">
          <div className="skeleton h-3.5 w-[70%]" />
          <div className="skeleton h-2.5 w-[40%]" />
        </div>
      ))}
    </div>
  );
}
