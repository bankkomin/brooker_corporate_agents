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
  // Present on rows returned from the CEO board approved/rejected columns
  // (joined from approval_decisions.decided_at); absent on plain proposal rows.
  decided_at?: string;
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
