"use client";

import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { CornerDownLeft, Search } from "lucide-react";
import { z } from "zod";

import { Button } from "@/components/ui/Button";
import { Field, Select, Textarea } from "@/components/ui/Field";
import { CATEGORY_OPTIONS } from "@/lib/format";
import type { PolicyCategory } from "@/types/api";

const schema = z.object({
  question: z
    .string()
    .trim()
    .min(8, "Ask a full question so the assistant can find the right policy.")
    .max(500, "Questions are limited to 500 characters."),
  category: z.string().optional(),
});

export type AskFormValues = z.infer<typeof schema>;

export function AskForm({
  pending,
  defaultQuestion,
  onSubmit,
}: {
  pending: boolean;
  defaultQuestion?: string;
  onSubmit: (question: string, category: PolicyCategory | null) => void;
}) {
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<AskFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { question: defaultQuestion ?? "", category: "" },
    mode: "onSubmit",
  });

  const question = watch("question") ?? "";

  // The parent prefills the box when a suggested or follow-up question is
  // clicked; keep the controlled value in step without remounting the form.
  useEffect(() => {
    if (defaultQuestion) {
      setValue("question", defaultQuestion, { shouldValidate: false });
    }
  }, [defaultQuestion, setValue]);

  const submit = handleSubmit((values) => {
    onSubmit(
      values.question.trim(),
      values.category ? (values.category as PolicyCategory) : null,
    );
  });

  return (
    <form onSubmit={submit} noValidate className="card overflow-hidden">
      <div className="space-y-4 px-5 py-5">
        <Field
          label="What do you need to know?"
          htmlFor="question"
          error={errors.question?.message}
          hint={`${question.length}/500`}
          required
        >
          <Textarea
            id="question"
            rows={3}
            placeholder="For example: How many days of annual leave can I carry into next year, and by when must I use them?"
            invalid={Boolean(errors.question)}
            // Ctrl/Cmd+Enter submits: this is a keyboard-first internal tool.
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                event.preventDefault();
                void submit();
              }
            }}
            {...register("question")}
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <Field
            label="Narrow to a policy area"
            htmlFor="category"
            hint="Optional"
          >
            <Select id="category" {...register("category")}>
              <option value="">All policy areas</option>
              {CATEGORY_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>

          <Button type="submit" loading={pending} className="w-full sm:w-auto">
            {!pending ? <Search className="h-4 w-4" aria-hidden /> : null}
            {pending ? "Searching policies" : "Ask Compass"}
          </Button>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-line bg-raised px-5 py-2.5">
        <p className="text-2xs text-ink-subtle">
          Answers come only from published policy documents, with a citation on
          every claim.
        </p>
        <span className="hidden shrink-0 items-center gap-1 text-2xs text-ink-subtle sm:flex">
          <kbd className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono text-[10px]">
            Ctrl
          </kbd>
          <span>+</span>
          <kbd className="rounded border border-line bg-surface px-1 py-0.5 font-mono text-[10px]">
            <CornerDownLeft className="h-2.5 w-2.5" aria-hidden />
          </kbd>
        </span>
      </div>
    </form>
  );
}
