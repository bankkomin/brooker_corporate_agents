export interface Proposal {
  id: string;
  created_at: string;
  agent: string;
  file: string;
  tab: string;
  cell: string;
  old_value: string | null;
  new_value: string;
  confidence: number;
  reasoning: string;
  status: "pending" | "approved" | "rejected";
  dept: string;
  source?: string;
}

export interface ProposalListResponse {
  proposals: Proposal[];
  total: number;
}

export interface RejectRequest {
  reason: string;
}

export interface EditRequest {
  edited_value: string;
}
