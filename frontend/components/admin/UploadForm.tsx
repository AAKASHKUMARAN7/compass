"use client";

import { useRef, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { FileUp, Paperclip, UploadCloud, X } from "lucide-react";
import { z } from "zod";

import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError } from "@/lib/api";
import { CATEGORY_OPTIONS, cn, formatBytes } from "@/lib/format";
import { JURISDICTION_OPTIONS } from "@/lib/persona";
import type { IngestionResult } from "@/types/api";

const ACCEPTED = [".pdf", ".txt", ".md", ".markdown"];
const MAX_BYTES = 15 * 1024 * 1024;

const schema = z.object({
  title: z
    .string()
    .trim()
    .min(3, "Give the document a title employees would recognise.")
    .max(160, "Titles are limited to 160 characters."),
  owner: z
    .string()
    .trim()
    .min(2, "Name the team accountable for this policy.")
    .max(80, "Owner is limited to 80 characters."),
  category: z.string().min(1, "Select a policy area."),
  jurisdiction: z.string().min(1, "Select which entity this governs."),
  version_label: z
    .string()
    .trim()
    .min(1, "Add a version label, for example v1.0.")
    .max(32, "Version label is limited to 32 characters."),
  effective_date: z.string().optional(),
  summary: z.string().trim().max(600, "Summary is limited to 600 characters.").optional(),
});

type FormValues = z.infer<typeof schema>;

export function UploadForm({ onIngested }: { onIngested: (result: IngestionResult) => void }) {
  const { notify } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [pending, setPending] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: "",
      owner: "",
      category: "other",
      jurisdiction: "global",
      version_label: "v1.0",
      effective_date: "",
      summary: "",
    },
  });

  const acceptFile = (candidate: File | undefined | null) => {
    if (!candidate) return;

    const extension = candidate.name.slice(candidate.name.lastIndexOf(".")).toLowerCase();
    if (!ACCEPTED.includes(extension)) {
      setFileError(`Unsupported file type "${extension}". Accepted: PDF, TXT, Markdown.`);
      setFile(null);
      return;
    }
    if (candidate.size > MAX_BYTES) {
      setFileError(`File is ${formatBytes(candidate.size)}. The limit is 15 MB.`);
      setFile(null);
      return;
    }

    setFileError(null);
    setFile(candidate);
    // Save the admin a keystroke: derive a title from the filename when blank.
    setValue("title", deriveTitle(candidate.name), { shouldValidate: false });
  };

  const submit = handleSubmit(async (values) => {
    if (!file) {
      setFileError("Attach a policy document to upload.");
      return;
    }

    setPending(true);
    const form = new FormData();
    form.append("file", file);
    form.append("title", values.title.trim());
    form.append("owner", values.owner.trim());
    form.append("category", values.category);
    form.append("jurisdiction", values.jurisdiction);
    form.append("version_label", values.version_label.trim());
    if (values.effective_date) form.append("effective_date", values.effective_date);
    if (values.summary?.trim()) form.append("summary", values.summary.trim());

    try {
      const result = await api.uploadDocument(form);
      notify({
        tone: "success",
        title: "Document indexed and published",
        description: `${result.document.title} — ${result.chunks_indexed} sections indexed in ${result.duration_ms} ms.`,
      });
      reset();
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      onIngested(result);
    } catch (error) {
      const apiError = error instanceof ApiError ? error : null;
      notify({
        tone: "error",
        title: apiError?.code === "empty_document" ? "Nothing to index" : "Upload failed",
        description: apiError?.detail ?? apiError?.message ?? "Unexpected error.",
      });
    } finally {
      setPending(false);
    }
  });

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div>
        <p className="mb-1.5 text-[13px] font-medium text-ink">
          Policy document<span className="ml-0.5 text-critical">*</span>
        </p>

        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            acceptFile(event.dataTransfer.files?.[0]);
          }}
          className={cn(
            "rounded-xl border-2 border-dashed transition-colors",
            dragging
              ? "border-brand-400 bg-brand-50"
              : fileError
                ? "border-critical/40 bg-rose-50/40"
                : "border-line bg-canvas hover:border-slate-300",
          )}
        >
          {file ? (
            <div className="flex items-center gap-3 px-4 py-3.5">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-surface">
                <Paperclip className="h-4 w-4 text-ink-muted" aria-hidden />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium text-ink">{file.name}</p>
                <p className="text-2xs text-ink-subtle">{formatBytes(file.size)}</p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setFile(null);
                  if (inputRef.current) inputRef.current.value = "";
                }}
                aria-label="Remove attached file"
              >
                <X className="h-4 w-4" aria-hidden />
              </Button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="flex w-full flex-col items-center gap-2 px-4 py-8 text-center"
            >
              <UploadCloud className="h-7 w-7 text-ink-subtle" aria-hidden />
              <span className="text-[13px] font-medium text-ink">
                Drop a file here, or click to browse
              </span>
              <span className="text-2xs text-ink-subtle">
                PDF, TXT or Markdown · up to 15 MB
              </span>
            </button>
          )}
        </div>

        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED.join(",")}
          className="sr-only"
          onChange={(event) => acceptFile(event.target.files?.[0])}
        />

        {fileError ? (
          <p role="alert" className="mt-1.5 text-[12px] font-medium text-critical">
            {fileError}
          </p>
        ) : null}
      </div>

      <Field label="Title" htmlFor="title" error={errors.title?.message} required>
        <Input
          id="title"
          placeholder="Leave and Time Off Policy"
          invalid={Boolean(errors.title)}
          {...register("title")}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Policy area"
          htmlFor="category"
          error={errors.category?.message}
          required
        >
          <Select id="category" invalid={Boolean(errors.category)} {...register("category")}>
            {CATEGORY_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>

        <Field
          label="Applies to"
          htmlFor="jurisdiction"
          error={errors.jurisdiction?.message}
          hint="Overrides global"
          required
        >
          <Select
            id="jurisdiction"
            invalid={Boolean(errors.jurisdiction)}
            {...register("jurisdiction")}
          >
            {JURISDICTION_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Owning team" htmlFor="owner" error={errors.owner?.message} required>
          <Input
            id="owner"
            placeholder="People Operations"
            invalid={Boolean(errors.owner)}
            {...register("owner")}
          />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Version"
          htmlFor="version_label"
          error={errors.version_label?.message}
          required
        >
          <Input
            id="version_label"
            placeholder="v1.0"
            invalid={Boolean(errors.version_label)}
            {...register("version_label")}
          />
        </Field>

        <Field label="Effective date" htmlFor="effective_date" hint="Optional">
          <Input id="effective_date" type="date" {...register("effective_date")} />
        </Field>
      </div>

      <Field
        label="Summary"
        htmlFor="summary"
        error={errors.summary?.message}
        hint="Optional"
      >
        <Textarea
          id="summary"
          rows={2}
          placeholder="What this document covers, in one line."
          invalid={Boolean(errors.summary)}
          {...register("summary")}
        />
      </Field>

      <div className="flex items-center justify-between gap-3 border-t border-line pt-4">
        <p className="text-2xs leading-relaxed text-ink-subtle">
          On upload the file is parsed, split by section, embedded and published
          to the assistant.
        </p>
        <Button type="submit" loading={pending} className="shrink-0">
          {!pending ? <FileUp className="h-4 w-4" aria-hidden /> : null}
          {pending ? "Indexing" : "Upload and index"}
        </Button>
      </div>
    </form>
  );
}

function deriveTitle(filename: string): string {
  return filename
    .replace(/\.[^.]+$/, "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
