export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  page_count: number | null;
  status: 'processing' | 'ready' | 'failed' | 'empty';
  error_msg: string | null;
  summary: string | null;
  chunk_count: number | null;
  created_at: string;
}

export interface Chunk {
  id: string;
  content: string;
  chunk_type: 'text' | 'table';
  chunk_index: number;
  page_number: number | null;
  char_start: number;
  char_end: number;
}

export interface SourceChunk {
  chunk_id: string;
  content: string;
  chunk_type: string;
  page_number: number | null;
  char_start: number;
  char_end: number;
  similarity: number;
  bm25_score?: number | null;
  cosine_score?: number | null;
}

export interface BudgetInfo {
  remaining_pct: number;
  model_tier: 'primary' | 'fallback';
  daily_reset_utc: string;
}

export interface QueryResult {
  id: string;
  question: string;
  answer: string;
  confidence: 'high' | 'low' | 'none';
  sources: SourceChunk[];
  latency_ms: number | null;
  model_used: string | null;
  budget: BudgetInfo | null;
  created_at: string;
}

export interface QueryHistoryItem {
  id: string;
  question: string;
  answer: string;
  confidence: string;
  source_count: number;
  created_at: string;
}

export interface BudgetStatus {
  primary_model: string;
  primary_requests_today: number;
  primary_remaining: number;
  fallback_model: string;
  fallback_requests_today: number;
  fallback_remaining: number;
  total_remaining: number;
  remaining_pct: number;
  active_model: string;
  resets_at: string;
}

export interface DashboardStats {
  total_documents: number;
  total_queries: number;
  avg_confidence_pct: number;
  positive_feedback_pct: number | null;
  total_feedback: number;
  budget_remaining_pct: number;
}
