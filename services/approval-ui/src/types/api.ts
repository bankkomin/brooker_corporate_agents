export interface ApiError {
  error: string;
  code: string;
  detail: string | null;
}

export interface EscalationItem {
  id: number;
  created_at: string;
  severity: string | null;
  trigger_type: string | null;
  detail: string | null;
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

export interface CeoBoardResponse {
  columns: {
    escalated: EscalationItem[];
    pending: import("./proposal").Proposal[];
    approved: import("./proposal").Proposal[];
    rejected: import("./proposal").Proposal[];
  };
  totals: {
    escalated: number;
    pending: number;
    approved: number;
    rejected: number;
  };
  truncated: {
    escalated: boolean;
    pending: boolean;
    approved: boolean;
    rejected: boolean;
  };
  window_days: number;
}
