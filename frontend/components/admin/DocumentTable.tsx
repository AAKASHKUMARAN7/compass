"use client";

import { Fragment, useState } from "react";
import {
  Archive,
  ArchiveRestore,
  ChevronRight,
  FileText,
  Layers,
  Trash2,
} from "lucide-react";

import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError } from "@/lib/api";
import {
  CATEGORY_LABELS,
  cn,
  formatBytes,
  formatDate,
  formatNumber,
  formatRelativeTime,
} from "@/lib/format";
import type { DocumentRecord } from "@/types/api";

export function DocumentTable({
  documents,
  onChanged,
}: {
  documents: DocumentRecord[];
  onChanged: () => void;
}) {
  const { notify } = useToast();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const toggleStatus = async (document: DocumentRecord) => {
    const next = document.status === "published" ? "archived" : "published";
    setBusyId(document.id);
    try {
      await api.setDocumentStatus(document.id, next);
      notify({
        tone: "success",
        title: next === "archived" ? "Document archived" : "Document published",
        description:
          next === "archived"
            ? `${document.title} is no longer used to answer questions.`
            : `${document.title} is live in the assistant.`,
      });
      onChanged();
    } catch (error) {
      notify({
        tone: "error",
        title: "Status change failed",
        description: error instanceof ApiError ? error.message : "Unexpected error.",
      });
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (document: DocumentRecord) => {
    setBusyId(document.id);
    try {
      await api.deleteDocument(document.id);
      notify({
        tone: "success",
        title: "Document deleted",
        description: `${document.title} and its ${formatNumber(document.chunk_count)} indexed sections were removed.`,
      });
      setConfirmId(null);
      onChanged();
    } catch (error) {
      notify({
        tone: "error",
        title: "Delete failed",
        description: error instanceof ApiError ? error.message : "Unexpected error.",
      });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] border-collapse text-left">
        <thead>
          <tr className="border-b border-line">
            <th className="label-caps px-5 py-2.5 font-semibold">Document</th>
            <th className="label-caps px-3 py-2.5 font-semibold">Area</th>
            <th className="label-caps px-3 py-2.5 font-semibold">Owner</th>
            <th className="label-caps px-3 py-2.5 text-right font-semibold">Indexed</th>
            <th className="label-caps px-3 py-2.5 font-semibold">Status</th>
            <th className="label-caps px-3 py-2.5 font-semibold">Updated</th>
            <th className="px-5 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => {
            const expanded = expandedId === document.id;
            const confirming = confirmId === document.id;
            const busy = busyId === document.id;

            return (
              <Fragment key={document.id}>
                <tr
                  className={cn(
                    "border-b border-line align-middle transition-colors",
                    expanded ? "bg-brand-50/40" : "hover:bg-canvas",
                  )}
                >
                  <td className="px-5 py-3">
                    <button
                      type="button"
                      onClick={() => setExpandedId(expanded ? null : document.id)}
                      className="flex items-start gap-2.5 text-left"
                      aria-expanded={expanded}
                    >
                      <ChevronRight
                        className={cn(
                          "mt-1 h-3.5 w-3.5 shrink-0 text-ink-subtle transition-transform",
                          expanded && "rotate-90",
                        )}
                        aria-hidden
                      />
                      <span className="min-w-0">
                        <span className="block text-[13.5px] font-medium text-ink">
                          {document.title}
                        </span>
                        <span className="mt-0.5 block truncate font-mono text-[10.5px] text-ink-subtle">
                          {document.filename} · {formatBytes(document.size_bytes)}
                          {document.page_count ? ` · ${document.page_count} pages` : ""}
                        </span>
                      </span>
                    </button>
                  </td>

                  <td className="px-3 py-3 text-[12.5px] text-ink-muted">
                    {CATEGORY_LABELS[document.category]}
                  </td>

                  <td className="px-3 py-3 text-[12.5px] text-ink-muted">
                    {document.owner}
                  </td>

                  <td className="numeric px-3 py-3 text-right text-[12.5px] text-ink-muted">
                    {formatNumber(document.chunk_count)}
                  </td>

                  <td className="px-3 py-3">
                    <StatusBadge status={document.status} />
                  </td>

                  <td
                    className="px-3 py-3 text-[12.5px] text-ink-muted"
                    title={document.updated_at}
                  >
                    {formatRelativeTime(document.updated_at)}
                  </td>

                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-1">
                      {confirming ? (
                        <>
                          <span className="mr-1 text-2xs font-medium text-critical">
                            Delete permanently?
                          </span>
                          <Button
                            size="sm"
                            variant="danger"
                            loading={busy}
                            onClick={() => remove(document)}
                          >
                            Confirm
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setConfirmId(null)}
                          >
                            Cancel
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            size="sm"
                            variant="secondary"
                            loading={busy}
                            disabled={document.status === "failed"}
                            onClick={() => toggleStatus(document)}
                          >
                            {document.status === "published" ? (
                              <>
                                <Archive className="h-3.5 w-3.5" aria-hidden />
                                Archive
                              </>
                            ) : (
                              <>
                                <ArchiveRestore className="h-3.5 w-3.5" aria-hidden />
                                Publish
                              </>
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setConfirmId(document.id)}
                            aria-label={`Delete ${document.title}`}
                            className="text-ink-subtle hover:text-critical"
                          >
                            <Trash2 className="h-3.5 w-3.5" aria-hidden />
                          </Button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>

                {expanded ? (
                  <tr className="border-b border-line bg-brand-50/20">
                    <td colSpan={7} className="px-5 py-4">
                      <DocumentDetailPanel document={document} />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DocumentDetailPanel({ document }: { document: DocumentRecord }) {
  return (
    <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div className="space-y-3">
        {document.summary ? (
          <p className="text-[13px] leading-relaxed text-ink-muted">{document.summary}</p>
        ) : (
          <p className="text-[13px] italic text-ink-subtle">No summary provided.</p>
        )}

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-[12.5px]">
          <Detail label="Version" value={document.version_label} />
          <Detail label="Effective" value={formatDate(document.effective_date)} />
          <Detail label="Words" value={formatNumber(document.word_count)} />
          <Detail label="Uploaded" value={formatDate(document.uploaded_at)} />
        </dl>

        <p className="font-mono text-[10.5px] text-ink-subtle">{document.id}</p>

        {document.failure_reason ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] text-rose-700">
            {document.failure_reason}
          </p>
        ) : null}
      </div>

      <div>
        <p className="label-caps mb-2 flex items-center gap-1.5">
          <Layers className="h-3 w-3" aria-hidden />
          Detected sections
        </p>
        {document.sections.length ? (
          <ul className="flex flex-wrap gap-1.5">
            {document.sections.slice(0, 14).map((section) => (
              <li
                key={section.label}
                className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-2 py-1 text-[11.5px] text-ink-muted"
              >
                <FileText className="h-3 w-3 text-ink-subtle" aria-hidden />
                <span className="max-w-[220px] truncate">{section.label}</span>
                <span className="numeric text-[10px] text-ink-subtle">
                  {section.chunk_count}
                </span>
              </li>
            ))}
            {document.sections.length > 14 ? (
              <li className="inline-flex items-center px-2 py-1 text-[11.5px] text-ink-subtle">
                +{document.sections.length - 14} more
              </li>
            ) : null}
          </ul>
        ) : (
          <p className="text-[12.5px] text-ink-subtle">
            No headings were detected. Citations for this document will reference the
            page only.
          </p>
        )}
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="label-caps">{label}</dt>
      <dd className="mt-0.5 text-ink">{value}</dd>
    </div>
  );
}
