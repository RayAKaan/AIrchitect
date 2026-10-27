import { expect, test } from '@playwright/test';

test('Phase 28 release acceptance connects canonical state, semantic model, exports and dependency review', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /Create an account/ }).click();
  await page.getByPlaceholder('Your name').fill('Phase 28 Reviewer');
  await page.getByPlaceholder('Company name').fill('Release Validation QA');
  await page.getByPlaceholder('name@company.com').fill('phase28-' + Date.now() + '@example.com');
  await page.getByPlaceholder('At least 12 characters').fill('phase-28-secure-password');
  await page.getByRole('button', { name: /Create account/ }).click();
  await expect(page.getByText('Your next project starts here.')).toBeVisible();

  await page.getByPlaceholder('e.g. Riyadh Retail Centre').fill('Phase 28 Riyadh Retail');
  await page.getByRole('button', { name: /Create project/ }).click();
  await expect(page.getByText('Phase 28 Riyadh Retail').first()).toBeVisible();
  await page.getByRole('button', { name: /Open workspace/ }).click();

  await page.getByRole('button', { name: 'Brief', exact: true }).last().click();
  await page.getByPlaceholder('Describe your building project…').fill(
    'Six-floor commercial retail building in Riyadh with 8,000 m2 GFA on a 2,000 m2 site and 40 parking spaces in basement parking.',
  );
  await page.getByRole('button', { name: 'Analyze and persist brief' }).click();
  await expect(page.getByText(/Brief revision 1/)).toBeVisible();

  await page.getByRole('button', { name: 'Requirements' }).click();
  await expect(page.locator('.fact-card').first()).toBeVisible();
  await page.getByRole('button', { name: 'World Model' }).click();
  await page.getByRole('button', { name: /Commit V1/ }).click();
  await expect(page.getByText(/World hash/)).toBeVisible();

  await page.getByRole('button', { name: 'Semantic Model' }).click();
  await expect(page.getByRole('heading', { name: 'Semantic model editor' })).toBeVisible();
  await expect(page.getByRole('heading', { name: /Elements \(/ })).toBeVisible();

  await page.getByRole('button', { name: 'CAD/BIM Exports' }).click();
  await expect(page.getByRole('heading', { name: 'Validated exports' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'No CAD/BIM artifacts' })).toBeVisible();

  await page.getByRole('button', { name: 'Change Impact' }).click();
  await expect(page.getByRole('heading', { name: 'Dependency graph & change propagation' })).toBeVisible();
  await expect(page.getByText(/World Model hash:/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'No persisted artifact dependencies yet' })).toBeVisible();

  await page.getByRole('button', { name: 'Release Validation' }).click();
  await expect(page.getByRole('heading', { name: 'Release validation checklist' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Native CAD-host smoke verification' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Legal redistribution clearance' })).toBeVisible();
  await expect(page.getByText('Overall status: REVIEW REQUIRED')).toBeVisible();
});
