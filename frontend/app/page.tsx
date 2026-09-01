"use client";

import { useCallback, useState } from "react";
import { Lightbulb, ShieldCheck, Sparkles } from "lucide-react";

import { AnswerPanel } from "@/components/ask/AnswerPanel";
import { AskForm } from "@/components/ask/AskForm";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError } from "@/lib/api";
import type { AskResponse, PolicyCategory } from "@/types/api";

const SUGGESTIONS = [
  "How many annual leave days can I carry into next year?",
  "What is the nightly hotel limit for travel to London?",
  "Do I need a medical certificate for a two-day sick absence?",
  "Can I paste customer data into a public AI tool?",
  "How much parental leave does a secondary caregiver get?",
];

export default function AskPage() {
  const { notify } = useToast();
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [pending, setPending] = useState(false);
  const [prefill, setPrefill] = useState<string | undefined>(undefined);

  const ask = useCallback(
    async (question: string, category: PolicyCategory | null) => {
      setPending(true);
      try {
        const result = await api.ask({ question, category });
        setAnswer(result);
        if (result.status === "no_coverage") {
          notify({
            tone: "info",
            title: "Logged as a coverage gap",
            description:
              "No published policy covers this. The policy team sees it in Insights.",
          });
        }
      } catch (error) {
        const message =
          error instanceof ApiError ? error.message : "Unexpected error.";
        notify({
          tone: "error",
          title: "Could not get an answer",
          description: message,
        });
      } finally {
        setPending(false);
      }
    },
    [notify],
  );

  const useSuggestion = useCallback((question: string) => {
    setPrefill(question);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  return (
    <>
      <PageHeader
        eyebrow="Employee assistant"
        title="Ask Compass"
        description="Answers are drawn only from published company policy documents. Every claim carries a citation you can open and verify."
      />

      <div className="mx-auto grid max-w-6xl gap-6 px-6 py-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-5">
          <AskForm pending={pending} defaultQuestion={prefill} onSubmit={ask} />

          {pending ? <AnswerSkeleton /> : null}

          {!pending && answer ? (
            <AnswerPanel answer={answer} onFollowUp={useSuggestion} />
          ) : null}

          {!pending && !answer ? (
            <Card>
              <CardHeader
                title="Try one of these"
                description="Sample questions covering the policies loaded in this environment."
              />
              <CardBody className="space-y-1.5 py-3">
                {SUGGESTIONS.map((question) => (
                  <button
                    key={question}
                    type="button"
                    onClick={() => useSuggestion(question)}
                    className="group flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13.5px] text-ink-muted transition-colors hover:bg-brand-50 hover:text-brand-700"
                  >
                    <Sparkles
                      className="h-3.5 w-3.5 shrink-0 text-ink-subtle transition-colors group-hover:text-brand-500"
                      aria-hidden
                    />
                    {question}
                  </button>
                ))}
              </CardBody>
            </Card>
          ) : null}
        </div>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <Card>
            <CardBody className="space-y-3.5">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-brand-600" aria-hidden />
                <h2 className="text-[13px] font-semibold text-ink">
                  How answers are grounded
                </h2>
              </div>
              <ol className="space-y-3">
                <Step
                  index={1}
                  title="Retrieve"
                  body="Your question is matched against every indexed section of the published policy set."
                />
                <Step
                  index={2}
                  title="Gate"
                  body="If the best match is too weak, Compass declines to answer instead of guessing."
                />
                <Step
                  index={3}
                  title="Cite"
                  body="Source titles, sections and pages are attached from the index, not written by the model."
                />
              </ol>
            </CardBody>
          </Card>

          <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-3.5">
            <div className="flex items-center gap-2">
              <Lightbulb className="h-3.5 w-3.5 text-amber-700" aria-hidden />
              <p className="text-[12.5px] font-semibold text-amber-900">
                Nothing found?
              </p>
            </div>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-amber-900/80">
              An unanswered question is not a dead end. It is recorded as a
              coverage gap and ranked by how often it is asked, so the policy team
              knows exactly what to publish next.
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}

function Step({ index, title, body }: { index: number; title: string; body: string }) {
  return (
    <li className="flex gap-3">
      <span className="numeric mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-line bg-canvas text-[10px] font-semibold text-ink-muted">
        {index}
      </span>
      <span className="space-y-0.5">
        <span className="block text-[12.5px] font-semibold text-ink">{title}</span>
        <span className="block text-[12.5px] leading-relaxed text-ink-muted">{body}</span>
      </span>
    </li>
  );
}

function AnswerSkeleton() {
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-line bg-raised px-5 py-3">
        <div className="skeleton h-4 w-20" />
        <div className="skeleton h-5 w-32 rounded-md" />
      </div>
      <div className="space-y-2.5 px-5 py-5">
        <div className="skeleton h-3.5 w-full" />
        <div className="skeleton h-3.5 w-[92%]" />
        <div className="skeleton h-3.5 w-[78%]" />
        <div className="skeleton mt-4 h-3.5 w-[85%]" />
      </div>
      <div className="border-t border-line bg-raised px-5 py-2.5">
        <div className="skeleton h-3 w-48" />
      </div>
    </div>
  );
}
