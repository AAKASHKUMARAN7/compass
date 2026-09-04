/**
 * Typed client for the Compass API.
 *
 * Every call funnels through `request`, so error-envelope parsing, timeouts and
 * request-id capture are handled once instead of at each call site.
 */

import type {
  AnalyticsOverview,
  ApiErrorBody,
  AskResponse,
  DocumentDetail,
  DocumentRecord,
  DocumentStatus,
  FeedbackRating,
  HealthResponse,
  IngestionResult,
  Page,
  Jurisdiction,
  PolicyCategory,
  QueryLogEntry,
} from "@/types/api";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8010";

const DEFAULT_TIMEOUT_MS = 60_000;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string | null;
  readonly requestId: string | null;

  constructor(
    message: string,
    options: { status: number; code: string; detail?: string | null; requestId?: string | null },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.detail = options.detail ?? null;
    this.requestId = options.requestId ?? null;
  }

  /** True when retrying the same request could plausibly succeed. */
  get isTransient(): boolean {
    return this.status === 0 || this.status >= 500;
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...rest } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(rest.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...rest.headers,
      },
    });
  } catch (error) {
    const aborted = error instanceof DOMException && error.name === "AbortError";
    throw new ApiError(
      aborted
        ? "The request timed out. The service may still be starting up."
        : "Cannot reach the Compass API. Confirm the backend is running on " + API_BASE_URL,
      { status: 0, code: aborted ? "timeout" : "network_error" },
    );
  } finally {
    clearTimeout(timer);
  }

  const requestId = response.headers.get("X-Request-ID");

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const payload = text ? safeParse(text) : null;

  if (!response.ok) {
    const envelope = payload as ApiErrorBody | null;
    throw new ApiError(envelope?.error?.message ?? `Request failed (${response.status}).`, {
      status: response.status,
      code: envelope?.error?.code ?? "http_error",
      detail: envelope?.error?.detail ?? null,
      requestId: envelope?.error?.request_id ?? requestId,
    });
  }

  return payload as T;
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const serialised = search.toString();
  return serialised ? `?${serialised}` : "";
}

export const api = {
  health: () => request<HealthResponse>("/api/health", { timeoutMs: 8_000 }),

  listDocuments: (params: {
    status?: DocumentStatus;
    category?: PolicyCategory;
    search?: string;
    limit?: number;
    offset?: number;
  } = {}) => request<Page<DocumentRecord>>(`/api/documents${query(params)}`),

  getDocument: (id: string) => request<DocumentDetail>(`/api/documents/${id}`),

  uploadDocument: (form: FormData) =>
    request<IngestionResult>("/api/documents", {
      method: "POST",
      body: form,
      timeoutMs: 120_000,
    }),

  setDocumentStatus: (id: string, status: Extract<DocumentStatus, "published" | "archived">) =>
    request<DocumentRecord>(`/api/documents/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  deleteDocument: (id: string) =>
    request<void>(`/api/documents/${id}`, { method: "DELETE" }),

  ask: (payload: {
    question: string;
    category?: PolicyCategory | null;
    asked_by?: string;
    jurisdiction?: Jurisdiction;
  }) =>
    request<AskResponse>("/api/chat/ask", {
      method: "POST",
      body: JSON.stringify({
        question: payload.question,
        category: payload.category ?? null,
        asked_by: payload.asked_by ?? "employee@company.com",
        jurisdiction: payload.jurisdiction ?? "global",
      }),
      timeoutMs: 90_000,
    }),

  history: (params: { limit?: number; offset?: number } = {}) =>
    request<Page<QueryLogEntry>>(`/api/chat/history${query(params)}`),

  sendFeedback: (queryId: string, rating: FeedbackRating, comment?: string) =>
    request<void>(`/api/chat/${queryId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ rating, comment: comment ?? null }),
    }),

  analytics: () => request<AnalyticsOverview>("/api/analytics/overview"),
};
