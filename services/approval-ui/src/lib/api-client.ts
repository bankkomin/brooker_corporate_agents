import { getToken } from "./auth";
import { env } from "./env";
import type {
  ProposalListResponse,
  Proposal,
  RejectRequest,
  EditRequest,
} from "@/types/proposal";
import type {
  EscalationListResponse,
  AnalyticsSummary,
  ApiError,
} from "@/types/api";

const GATEWAY_URL = env.NEXT_PUBLIC_GATEWAY_URL;

class ApiClient {
  private getHeaders(): HeadersInit {
    const token = getToken();
    const headers: HeadersInit = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return headers;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        error: "Unknown error",
        code: "INTERNAL_ERROR",
        detail: null,
      }));
      throw error;
    }
    return response.json();
  }

  async listProposals(
    status?: string,
    dept?: string,
  ): Promise<ProposalListResponse> {
    const qs = new URLSearchParams();
    if (status) qs.set("status", status);
    if (dept) qs.set("dept", dept);
    const tail = qs.toString();
    const url = `${GATEWAY_URL}/api/proposals${tail ? `?${tail}` : ""}`;
    const resp = await fetch(url, { headers: this.getHeaders() });
    return this.handleResponse(resp);
  }

  async getProposal(id: string): Promise<Proposal> {
    const resp = await fetch(`${GATEWAY_URL}/api/proposals/${id}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(resp);
  }

  async approveProposal(
    id: string
  ): Promise<{ status: string; proposal_id: string }> {
    const resp = await fetch(
      `${GATEWAY_URL}/api/proposals/${id}/approve`,
      {
        method: "POST",
        headers: this.getHeaders(),
      }
    );
    return this.handleResponse(resp);
  }

  async rejectProposal(
    id: string,
    reason: string
  ): Promise<{ status: string; proposal_id: string }> {
    const body: RejectRequest = { reason };
    const resp = await fetch(
      `${GATEWAY_URL}/api/proposals/${id}/reject`,
      {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify(body),
      }
    );
    return this.handleResponse(resp);
  }

  async editProposal(
    id: string,
    editedValue: string
  ): Promise<{ status: string; proposal_id: string }> {
    const body: EditRequest = { edited_value: editedValue };
    const resp = await fetch(
      `${GATEWAY_URL}/api/proposals/${id}/edit`,
      {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify(body),
      }
    );
    return this.handleResponse(resp);
  }

  async listEscalations(dept?: string): Promise<EscalationListResponse> {
    const qs = dept ? `?dept=${encodeURIComponent(dept)}` : "";
    const resp = await fetch(`${GATEWAY_URL}/api/escalations${qs}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(resp);
  }

  async getAnalyticsSummary(dept?: string): Promise<AnalyticsSummary> {
    const qs = dept ? `?dept=${encodeURIComponent(dept)}` : "";
    const resp = await fetch(`${GATEWAY_URL}/api/analytics/summary${qs}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(resp);
  }

  async listKnowledgeGaps(): Promise<{
    gaps: Array<{
      id: number;
      dept_id: string;
      agent_id: string;
      query: string;
      hit_count: number;
      llm_self_report: string | null;
      expected_doc_type: string | null;
      created_at: string | null;
      resolved_at: string | null;
    }>;
  }> {
    const resp = await fetch(`${GATEWAY_URL}/api/admin/knowledge-gaps`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(resp);
  }

  async resolveKnowledgeGap(
    id: number,
  ): Promise<{ id: number; status: string; resolved_by: string }> {
    const resp = await fetch(
      `${GATEWAY_URL}/api/admin/knowledge-gaps/${id}/resolve`,
      { method: "POST", headers: this.getHeaders() },
    );
    return this.handleResponse(resp);
  }

  async listSkillProposals(
    status: string = "hod_review",
  ): Promise<{
    proposals: Array<{
      id: number;
      dept_id: string;
      agent_id: string;
      skill_path: string;
      trigger: string;
      evidence: { count: number; avg_signal: number };
      status: string;
      proposed_diff: string | null;
      created_at: string | null;
    }>;
  }> {
    const qs = `?status=${encodeURIComponent(status)}`;
    const resp = await fetch(`${GATEWAY_URL}/api/skill-proposals${qs}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(resp);
  }

  async decideSkillProposal(
    id: number,
    action: "approved" | "rejected",
  ): Promise<{ id: number; status: string; decided_by: string }> {
    const resp = await fetch(
      `${GATEWAY_URL}/api/skill-proposals/${id}/decision`,
      {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify({ action }),
      },
    );
    return this.handleResponse(resp);
  }

  async uploadDocument(
    file: File,
    opts: {
      dept?: string;
      docType?: string;
      collection?: string;
      category?: string;
      tags?: string;
      description?: string;
      source?: string;
    } = {}
  ): Promise<{ status: string; chunks?: number; file_hash?: string; reason?: string }> {
    const token = getToken();
    const headers: HeadersInit = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const form = new FormData();
    form.append("file", file);
    form.append("dept", opts.dept ?? "cac");
    form.append("doc_type", opts.docType ?? inferDocType(file.name));
    form.append("collection", opts.collection ?? "cac_docs");
    if (opts.category) form.append("category", opts.category);
    if (opts.tags) form.append("tags", opts.tags);
    if (opts.description) form.append("description", opts.description);
    form.append("source", opts.source ?? "manual_upload");

    const resp = await fetch(`${GATEWAY_URL}/api/uploads/document`, {
      method: "POST",
      headers,
      body: form,
    });
    return this.handleResponse(resp);
  }
}

function inferDocType(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = { pdf: "pdf", xlsx: "xlsx", xls: "xlsx", docx: "docx", txt: "txt", md: "md", csv: "csv" };
  return map[ext] ?? "pdf";
}

export const apiClient = new ApiClient();
