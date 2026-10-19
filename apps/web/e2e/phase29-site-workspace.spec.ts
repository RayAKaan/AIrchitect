import { expect, test } from '@playwright/test';

test('Phase 29 site workspace connects canonical geometry, onboarding and board composition', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /Create an account/ }).click();
  await page.getByPlaceholder('Your name').fill('Phase 29 Reviewer');
  await page.getByPlaceholder('Company name').fill('Site Workspace QA');
  await page.getByPlaceholder('name@company.com').fill('phase29-' + Date.now() + '@example.com');
  await page.getByPlaceholder('At least 12 characters').fill('phase-29-secure-password');
  await page.getByRole('button', { name: /Create account/ }).click();
  await expect(page.getByText('Your next project starts here.')).toBeVisible();

  await page.getByPlaceholder('e.g. Riyadh Retail Centre').fill('Phase 29 Site Workspace');
  await page.getByRole('button', { name: /Create project/ }).click();
  await expect(page.getByText('Phase 29 Site Workspace').first()).toBeVisible();
  await page.getByRole('button', { name: /Open workspace/ }).click();

  await page.getByRole('button', { name: 'Site' }).click();
  await expect(page.getByRole('heading', { name: 'Site workflow' })).toBeVisible();
  const template = page.getByRole('combobox', { name: 'Start with a workflow' });
  await template.selectOption('feasibility');
  await expect(template).toHaveValue('feasibility');
  await page.getByRole('button', { name: 'Next' }).click();
  await expect(page.getByText('Add evidence')).toBeVisible();
  await page.getByRole('button', { name: 'Finish guide' }).click();

  await expect(page.getByText('BASEMAP NOT CONFIGURED')).toBeVisible();
  await expect(page.getByText('EPSG:4326 · longitude / latitude')).toBeVisible();
  await page.getByRole('button', { name: 'Set site boundary' }).click();
  await expect(page.getByText(/Canonical revision 1 is persisted/)).toBeVisible();
  await expect(page.getByText(/Site revisions/)).toBeVisible();

  await page.getByRole('button', { name: 'Board' }).click();
  await expect(page.getByRole('heading', { name: 'Site analysis board' })).toBeVisible();
  await expect(page.getByLabel('A1 portrait board preview')).toBeVisible();
  await page.getByLabel('A1 portrait board preview').press('ArrowRight');
  await page.getByLabel('A1 portrait board preview').press('ArrowDown');
  await page.getByRole('button', { name: 'Save layout' }).click();
  await expect(page.getByRole('button', { name: 'Saved' })).toBeVisible();
});
