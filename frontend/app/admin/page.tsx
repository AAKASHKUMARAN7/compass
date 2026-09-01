"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { FileStack, RefreshCw, Search, X } from "lucide-react";

import { DocumentTable } from "@/components/admin/DocumentTable";
import { UploadForm } from "@/components/admin/UploadForm";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, EmptyState } from "@/components/ui/Card";
import { Input, Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError } from "@/lib/api";
import { CATEGORY_OPTIONS, formatNumber } from "@/lib/format";
import type { DocumentRecord, DocumentStatus } from "@/types/api";

export default function AdminPage() {
  const { notify } = useToast();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | "">("");
  const [categoryFilter, setCategoryFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const page = await api.listDocuments({ limit: 200 });
      setDocuments(page.items);
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

  // Filtering happens client-side: the corpus is small, and instant feedback
  // beats a round trip per keystroke.
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return documents.filter((document) => {
      if (statusFilter && document.status !== statusFilter) return false;
      if (categoryFilter && document.category !== categoryFilter) return false;
      if (!needle) return true;
      return (
        document.title.toLowerCase().includes(needle) ||
        document.owner.toLowerCase().includes(needle) ||
        document.filename.toLowerCase().includes(needle)
      );
    });
  }, [documents, search, statusFilter, categoryFilter]);

  const totals = useMemo(
    () => ({
      published: documents.filter((d) => d.status === "published").length,
      archived: documents.filter((d) => d.status === "archived").length,
      chunks: documents.reduce((sum, d) => sum + d.chunk_count, 0),
    }),
    [documents],
  );

  const filtersActive = Boolean(search || statusFilter || categoryFilter);

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Knowledge Base"
        description="Everything the assistant is allowed to answer from. Archiving removes a document from retrieval immediately without deleting it."
        action={
          <Button variant="secondary" onClick={() => void load()} loading={loading}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            Refresh
          </Button>
        }
      />

      <div className="mx-auto grid max-w-6xl gap-6 px-6 py-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Published" value={formatNumber(totals.published)} />
            <Stat label="Archived" value={formatNumber(totals.archived)} />
            <Stat label="Indexed sections" value={formatNumber(totals.chunks)} />
          </div>

          <Card>
            <CardHeader
              title="Policy documents"
              description={
                filtersActive
                  ? `${filtered.length} of ${documents.length} shown`
                  : `${documents.length} document${documents.length === 1 ? "" : "s"}`
              }
            />

            <div className="flex flex-wrap items-center gap-2 border-b border-line px-5 py-3">
              <div className="relative min-w-[200px] flex-1">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-subtle"
                  aria-hidden
                />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search by title, owner or filename"
                  aria-label="Search documents"
                  className="h-9 py-0 pl-9 text-[13px]"
                />
              </div>

              <Select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as DocumentStatus | "")}
                aria-label="Filter by status"
                className="h-9 w-auto py-0 text-[13px]"
              >
                <option value="">All statuses</option>
                <option value="published">Published</option>
                <option value="archived">Archived</option>
                <option value="failed">Failed</option>
              </Select>

              <Select
                value={categoryFilter}
                onChange={(event) => setCategoryFilter(event.target.value)}
                aria-label="Filter by policy area"
                className="h-9 w-auto py-0 text-[13px]"
              >
                <option value="">All areas</option>
                {CATEGORY_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>

              {filtersActive ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSearch("");
                    setStatusFilter("");
                    setCategoryFilter("");
                  }}
                >
                  <X className="h-3.5 w-3.5" aria-hidden />
                  Clear
                </Button>
              ) : null}
            </div>

            {loading && documents.length === 0 ? (
              <TableSkeleton />
            ) : error ? (
              <EmptyState
                title="Cannot load documents"
                description={error}
                action={
                  <Button variant="secondary" onClick={() => void load()}>
                    Try again
                  </Button>
                }
              />
            ) : filtered.length === 0 ? (
              <EmptyState
                icon={<FileStack className="h-5 w-5" aria-hidden />}
                title={filtersActive ? "No documents match these filters" : "No documents yet"}
                description={
                  filtersActive
                    ? "Adjust or clear the filters to see the full set."
                    : "Upload a policy document to make it answerable by the assistant."
                }
              />
            ) : (
              <DocumentTable documents={filtered} onChanged={() => void load()} />
            )}
          </Card>
        </div>

        <aside className="lg:sticky lg:top-6 lg:self-start">
          <Card>
            <CardHeader
              title="Add a policy document"
              description="Parsed by section, embedded, and live in the assistant as soon as indexing finishes."
            />
            <CardBody>
              <UploadForm
                onIngested={(result) => {
                  setDocuments((current) => [result.document, ...current]);
                  void load();
                }}
              />
            </CardBody>
          </Card>
        </aside>
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card px-4 py-3">
      <p className="label-caps">{label}</p>
      <p className="numeric mt-1 text-xl font-semibold tracking-tight text-ink">{value}</p>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="divide-y divide-line">
      {[0, 1, 2, 3].map((row) => (
        <div key={row} className="flex items-center gap-4 px-5 py-4">
          <div className="skeleton h-4 flex-1" />
          <div className="skeleton h-4 w-24" />
          <div className="skeleton h-4 w-20" />
          <div className="skeleton h-5 w-20 rounded-md" />
        </div>
      ))}
    </div>
  );
}
