export type CopilotIntent = 'CLARIFY' | 'DESIGN' | 'EDIT' | 'ANALYZE' | 'REVIEW';

export interface ProposedCommand {
  command_id: string;
  command_type: string;
  payload: Record<string, unknown>;
  reason: string;
  depends_on: string[];
}

export interface AIProposal {
  schema_version: string;
  proposal_id: string;
  project_id: string;
  version_id: string;
  base_revision_hash: string;
  context_hash: string;
  intent: CopilotIntent;
  summary: string;
  commands: ProposedCommand[];
  evidence_ids: string[];
  confidence: number;
  requires_confirmation: boolean;
  canonical_mutation: boolean;
  provider: string;
  model: string;
  model_version: string;
}

export interface CopilotPreviewResponse {
  proposal: AIProposal;
  commands: Record<string, unknown>[];
  executable: boolean;
  validation_errors: string[];
  canonical_state_mutated: boolean;
}

export interface CopilotPlanPreviewResponse {
  proposal_id: string;
  executable: boolean;
  command_ids: string[];
  execution_order: string[];
  impact_groups: string[];
  fingerprint: string | null;
  validation_errors: string[];
  warnings: string[];
  canonical_state_mutated: boolean;
}

export interface CopilotImpactExplanation {
  group: string;
  artifact_type: string;
  description: string;
  regeneration_required: boolean;
}

export interface CopilotImpactPreviewResponse {
  proposal_id: string;
  impact_groups: CopilotImpactExplanation[];
  canonical_state_mutated: boolean;
}

export interface CopilotApprovalTokenResponse {
  proposal_id: string;
  plan_fingerprint: string;
  approval_token: string;
  canonical_state_mutated: boolean;
}

export interface CopilotAcceptanceResponse {
  accepted: boolean;
  reasons: string[];
  canonical_state_mutated: boolean;
}

export interface CopilotCommitResponse {
  proposal_id: string;
  status: 'committed';
  version_id: string;
  revision_hash: string;
  results: Record<string, unknown>[];
  canonical_state_mutated: true;
}

export interface CopilotClientOptions {
  apiBaseUrl: string;
  token?: string;
  fetchImpl?: typeof fetch;
}

export class CopilotApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'CopilotApiError';
    this.status = status;
  }
}

export class CopilotApiClient {
  private readonly apiBaseUrl: string;
  private readonly token: string | undefined;
  private readonly fetchImpl: typeof fetch;

  constructor(options: CopilotClientOptions) {
    this.apiBaseUrl = options.apiBaseUrl.replace(/\/$/, '');
    this.token = options.token;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  async preview(projectId: string, question: string, versionRef: string): Promise<CopilotPreviewResponse> {
    return this.request<CopilotPreviewResponse>(`/projects/${encodeURIComponent(projectId)}/ai/copilot/preview`, {
      method: 'POST',
      body: JSON.stringify({ question, version_ref: versionRef }),
    });
  }

  async planPreview(projectId: string, proposal: AIProposal): Promise<CopilotPlanPreviewResponse> {
    return this.request<CopilotPlanPreviewResponse>(`/projects/${encodeURIComponent(projectId)}/ai/copilot/plan-preview`, {
      method: 'POST',
      body: JSON.stringify({ proposal }),
    });
  }

  async impactPreview(projectId: string, proposal: AIProposal): Promise<CopilotImpactPreviewResponse> {
    return this.request<CopilotImpactPreviewResponse>(`/projects/${encodeURIComponent(projectId)}/ai/copilot/impact-preview`, {
      method: 'POST',
      body: JSON.stringify({ proposal }),
    });
  }

  async issueApprovalToken(projectId: string, proposal: AIProposal): Promise<CopilotApprovalTokenResponse> {
    return this.request<CopilotApprovalTokenResponse>(
      `/projects/${encodeURIComponent(projectId)}/ai/copilot/approval-token`,
      { method: 'POST', body: JSON.stringify({ proposal }) },
    );
  }

  async acceptance(projectId: string, proposal: AIProposal, approvalToken: string): Promise<CopilotAcceptanceResponse> {
    return this.request<CopilotAcceptanceResponse>(`/projects/${encodeURIComponent(projectId)}/ai/copilot/acceptance`, {
      method: 'POST',
      body: JSON.stringify({ proposal, approval_token: approvalToken }),
    });
  }

  async commit(projectId: string, proposal: AIProposal, approvalToken: string): Promise<CopilotCommitResponse> {
    return this.request<CopilotCommitResponse>(`/projects/${encodeURIComponent(projectId)}/ai/copilot/commit`, {
      method: 'POST',
      body: JSON.stringify({ proposal, approval_token: approvalToken }),
    });
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const response = await this.fetchImpl(`${this.apiBaseUrl}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        ...init.headers,
      },
    });
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = typeof payload === 'object' && payload !== null && 'detail' in payload
        ? String(payload.detail)
        : `Copilot request failed (${response.status})`;
      throw new CopilotApiError(response.status, detail);
    }
    return payload as T;
  }
}
