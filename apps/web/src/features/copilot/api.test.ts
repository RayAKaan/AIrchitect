import { describe, expect, it, vi } from 'vitest';

import { CopilotApiClient, CopilotApiError, type AIProposal } from './api';

const proposal: AIProposal = {
  schema_version: '1.0.0',
  proposal_id: 'proposal-1',
  project_id: 'project-1',
  version_id: 'version-1',
  base_revision_hash: 'revision-1',
  context_hash: 'context-1',
  intent: 'EDIT',
  summary: 'Update the courtyard.',
  commands: [],
  evidence_ids: [],
  confidence: 0.9,
  requires_confirmation: true,
  canonical_mutation: false,
  provider: 'test',
  model: 'test-model',
  model_version: '1',
};

function client(response: Response) {
  const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(response);
  return { client: new CopilotApiClient({ apiBaseUrl: '/api/v1', token: 'token', fetchImpl }), fetchImpl };
}

describe('CopilotApiClient', () => {
  it('sends revision-scoped preview requests with authentication', async () => {
    const { client, fetchImpl } = clientWithJson({ proposal, commands: [], executable: true, validation_errors: [], canonical_state_mutated: false });

    await client.preview('project/1', 'Change the courtyard', 'version-1');

    expect(fetchImpl).toHaveBeenCalledWith(
      '/api/v1/projects/project%2F1/ai/copilot/preview',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer token' }),
      }),
    );
    expect(JSON.parse(String(fetchImpl.mock.calls[0][1]?.body))).toEqual({
      question: 'Change the courtyard',
      version_ref: 'version-1',
    });
  });

  it('routes acceptance and commit through explicit methods', async () => {
    const { client, fetchImpl } = clientWithJson({ accepted: true, reasons: [], canonical_state_mutated: false });

    await client.acceptance('project-1', proposal, 'approval-token');
    await client.commit('project-1', proposal, 'approval-token');

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      '/api/v1/projects/project-1/ai/copilot/acceptance',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      '/api/v1/projects/project-1/ai/copilot/commit',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('normalizes server errors into a typed error', async () => {
    const { client } = clientWithJson({ detail: 'STALE_AI_PROPOSAL' }, false, 409);

    await expect(client.planPreview('project-1', proposal)).rejects.toEqual(
      expect.objectContaining({
        name: 'CopilotApiError',
        status: 409,
        message: 'STALE_AI_PROPOSAL',
      } satisfies Partial<CopilotApiError>),
    );
  });
});

function clientWithJson(payload: unknown, ok = true, status = 200) {
  const response = new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
  const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(response);
  return {
    client: new CopilotApiClient({ apiBaseUrl: '/api/v1', token: 'token', fetchImpl }),
    fetchImpl,
  };
}
