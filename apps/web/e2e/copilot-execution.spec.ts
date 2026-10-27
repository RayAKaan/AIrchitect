import { expect, test } from '@playwright/test';

test('Copilot keeps canonical mutation behind deterministic plan and acceptance gates', async ({ page }) => {
  const proposal = (projectId: string, versionId: string) => ({
    schema_version: '1.0.0',
    proposal_id: 'e2e-proposal-1',
    project_id: projectId,
    version_id: versionId,
    base_revision_hash: 'revision-e2e',
    context_hash: 'context-e2e',
    intent: 'EDIT',
    summary: 'Increase the courtyard to 120 m².',
    commands: [{
      command_id: 'command-1',
      command_type: 'SetProgramArea',
      payload: { space_type: 'courtyard', area_m2: 120 },
      reason: 'Apply the requested courtyard area.',
      depends_on: [],
    }],
    evidence_ids: [],
    confidence: 0.94,
    requires_confirmation: true,
    canonical_mutation: false,
    provider: 'e2e',
    model: 'e2e-model',
    model_version: '1',
  });

  await page.goto('/');
  await page.getByRole('button', { name: /Create an account/ }).click();
  await page.getByPlaceholder('Your name').fill('Copilot Execution QA');
  await page.getByPlaceholder('Company name').fill('Copilot QA');
  await page.getByPlaceholder('name@company.com').fill(`copilot-${Date.now()}@example.com`);
  await page.getByPlaceholder('At least 12 characters').fill('copilot-e2e-secure-password');
  await page.getByRole('button', { name: /Create account/ }).click();
  await expect(page.getByText('Your next project starts here.')).toBeVisible();

  await page.getByPlaceholder('e.g. Riyadh Retail Centre').fill('Copilot Execution Project');
  await page.getByRole('button', { name: /Create project/ }).click();
  await expect(page.getByText('Copilot Execution Project').first()).toBeVisible();
  await page.getByRole('button', { name: /Open workspace/ }).click();

  await page.getByRole('button', { name: 'Brief' }).click();
  await page.getByPlaceholder('Describe your building project…').fill(
    'Six-floor commercial retail building in Riyadh with 8,000 m2 GFA on a 2,000 m2 site and 40 parking spaces in basement parking.',
  );
  await page.getByRole('button', { name: 'Analyze and persist brief' }).click();
  await expect(page.getByText(/Brief revision 1/)).toBeVisible();
  await page.getByRole('button', { name: 'World Model' }).click();
  await page.getByRole('button', { name: /Commit V1/ }).click();

  await page.route('**/api/v1/projects/*/ai/copilot/preview', async (route) => {
    const url = new URL(route.request().url());
    const body = route.request().postDataJSON() as { version_ref: string };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      proposal: proposal(url.pathname.split('/')[4], body.version_ref),
      commands: [],
      executable: true,
      validation_errors: [],
      canonical_state_mutated: false,
    }) });
  });
  await page.route('**/api/v1/projects/*/ai/copilot/plan-preview', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      proposal_id: 'e2e-proposal-1',
      executable: true,
      command_ids: ['command-1'],
      execution_order: ['command-1'],
      impact_groups: ['geometry', 'quantities', 'cost'],
      fingerprint: 'fingerprint-e2e',
      validation_errors: [],
      warnings: [],
      canonical_state_mutated: false,
    }) });
  });
  await page.route('**/api/v1/projects/*/ai/copilot/approval-token', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      proposal_id: 'e2e-proposal-1',
      plan_fingerprint: 'fingerprint-e2e',
      approval_token: 'approval-token-e2e-12345678901234567890',
      canonical_state_mutated: false,
    }) });
  });
  await page.route('**/api/v1/projects/*/ai/copilot/acceptance', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      accepted: true,
      reasons: [],
      canonical_state_mutated: false,
    }) });
  });
  await page.route('**/api/v1/projects/*/ai/copilot/commit', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      proposal_id: 'e2e-proposal-1',
      status: 'committed',
      version_id: 'e2e-version',
      revision_hash: 'revision-after-e2e',
      results: [{ command_id: 'command-1', status: 'applied' }],
      canonical_state_mutated: true,
    }) });
  });

  await page.getByRole('button', { name: 'Copilot' }).click();
  await page.getByRole('textbox', { name: 'Copilot request' }).fill('Increase the courtyard to 120 m².');
  await page.getByRole('button', { name: 'Preview proposal' }).click();
  await expect(page.getByText('Validated proposal')).toBeVisible();
  await expect(page.getByText('Affected: geometry, quantities, cost')).toBeVisible();

  const commitButton = page.getByRole('button', { name: 'Commit canonical change' });
  await expect(commitButton).toBeDisabled();
  await page.getByRole('button', { name: 'Approve proposal' }).click();
  await expect(page.getByText('Acceptance gate passed.')).toBeVisible();
  await expect(commitButton).toBeEnabled();

  await commitButton.click();
  await expect(page.getByRole('button', { name: 'Committed' })).toBeVisible();
  await expect(page.getByText(/Canonical state updated/)).toBeVisible();
});
