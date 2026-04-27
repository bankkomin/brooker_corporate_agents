export interface ApiError {
  error: string;
  code: string;
  detail: string | null;
}

export interface EscalationItem {
  id: number;
  created_at: string;
  severity: string;
  trigger_type: string;
  detail: string;
  dept: string;
  resolved_at: string | null;
}

export interface EscalationListResponse {
  escalations: EscalationItem[];
  total: number;
}

export interface AnalyticsSummary {
  pending: number;
  approved_today: number;
  escalations: number;
  avg_confidence: number | null;
}
