/** Wire contracts mirrored from the FastAPI schemas. */

export type DocumentStatus = "processing" | "published" | "archived" | "failed";

export type PolicyCategory =
  | "leave_and_time_off"
  | "compensation"
  | "benefits"
  | "expenses_and_travel"
  | "security_and_it"
  | "conduct_and_compliance"
  | "workplace"
  | "other";

export type Jurisdiction = "global" | "uk" | "india" | "us" | "singapore";

export type Confidence = "high" | "medium" | "low" | "none";
export type AnswerStatus = "answered" | "no_coverage";
export type FeedbackRating = "helpful" | "not_helpful";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  llm_provider: string;
  llm_model: string | null;
  embedding_provider: string;
  embedding_model: string;
  generation_mode: "generative" | "degraded" | "extractive";
  generation_detail: string | null;
  documents_published: number;
  chunks_indexed: number;
  checked_at: string;
}

export interface DocumentSection {
  label: string;
  chunk_count: number;
}

export interface DocumentRecord {
  id: string;
  title: string;
  category: PolicyCategory;
  jurisdiction: Jurisdiction;
  owner: string;
  version_label: string;
  effective_date: string | null;
  summary: string | null;
  status: DocumentStatus;
  filename: string;
  content_type: string;
  size_bytes: number;
  page_count: number | null;
  word_count: number;
  chunk_count: number;
  sections: DocumentSection[];
  failure_reason: string | null;
  uploaded_at: string;
  updated_at: string;
}

export interface DocumentChunkPreview {
  chunk_id: string;
  ordinal: number;
  section: string | null;
  page: number | null;
  text: string;
}

export interface DocumentDetail extends DocumentRecord {
  chunks: DocumentChunkPreview[];
}

export interface IngestionResult {
  document: DocumentRecord;
  chunks_indexed: number;
  duration_ms: number;
}

export interface Citation {
  marker: number;
  chunk_id: string;
  document_id: string;
  document_title: string;
  section: string | null;
  page: number | null;
  version_label: string;
  owner: string;
  jurisdiction: Jurisdiction;
  effective_date: string | null;
  relevance: number;
  excerpt: string;
}

export interface AskResponse {
  query_id: string;
  question: string;
  status: AnswerStatus;
  answer: string;
  confidence: Confidence;
  top_score: number;
  citations: Citation[];
  follow_up_questions: string[];
  generation_mode: string;
  model: string | null;
  latency_ms: number;
  created_at: string;
}

export interface QueryLogEntry {
  id: string;
  question: string;
  status: AnswerStatus;
  confidence: Confidence;
  top_score: number;
  category: PolicyCategory | null;
  asked_by: string;
  citation_count: number;
  latency_ms: number;
  feedback: FeedbackRating | null;
  created_at: string;
}

export interface KpiSummary {
  documents_published: number;
  documents_archived: number;
  chunks_indexed: number;
  questions_asked: number;
  answer_rate: number;
  coverage_gap_count: number;
  avg_confidence_score: number;
  avg_latency_ms: number;
  helpful_rate: number | null;
}

export interface CategoryBreakdown {
  category: PolicyCategory;
  document_count: number;
  question_count: number;
}

export interface CoverageGap {
  question: string;
  occurrences: number;
  best_score: number;
  last_asked_at: string;
}

export interface TopQuestion {
  question: string;
  occurrences: number;
  avg_score: number;
}

export interface AnalyticsOverview {
  kpis: KpiSummary;
  categories: CategoryBreakdown[];
  coverage_gaps: CoverageGap[];
  top_questions: TopQuestion[];
  generated_at: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    detail: string | null;
    request_id: string;
  };
}
