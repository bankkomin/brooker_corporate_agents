import { getToken } from "./auth";
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

const GATEWAY_URL =
  process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:3000";

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

  async listProposals(status?: string): Promise<ProposalListResponse> {
    const params = status ? `?status=${status}` : "";
    const resp = await fetch(`${GATEWAY_URL}/api/proposals${params}`, {
      headers: this.getHeaders(),
    });
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

  async listEscalations(): Promise<EscalationListResponse> {
    const resp = await fetch(`${GATEWAY_URL}/api/escalations`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(resp);
  }

  async getAnalyticsSummary(): Promise<AnalyticsSummary> {
    const resp = await fetch(`${GATEWAY_URL}/api/analytics/summary`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(resp);
  }
}

export const apiClient = new ApiClient();
