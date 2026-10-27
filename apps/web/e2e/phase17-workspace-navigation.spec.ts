import { expect, test, type Page } from '@playwright/test';

async function createWorkspace(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: /Create an account/ }).click();
  await page.getByPlaceholder('Your name').fill('Workspace Navigation QA');
  await page.getByPlaceholder('Company name').fill('AIrchitect Navigation QA');
  await page.getByPlaceholder('name@company.com').fill(`workspace-${Date.now()}@example.com`);
  await page.getByPlaceholder('At least 12 characters').fill('workspace-production-password');
  await page.getByRole('button', { name: /Create account/ }).click();
  await expect(page.getByText('Your next project starts here.')).toBeVisible();
  await page.getByPlaceholder('e.g. Riyadh Retail Centre').fill('Navigation Acceptance Project');
  await page.getByRole('button', { name: /Create project/ }).click();
  await page.getByRole('button', { name: /Open workspace/ }).click();
  await expect(page.getByRole('region', { name: 'AIrchitect project workspace' })).toBeVisible();
}

test('product modes change the real workspace context', async ({ page }) => {
  await createWorkspace(page);
  for (const [mode, title] of [
    ['Brief', 'Tell AIrchitect what you are building.'], ['Site', 'Understand the place.'], ['Explore', 'Explore possibilities.'],
    ['Design', 'Develop the chosen direction.'], ['Validate', 'Check the decisions.'], ['Deliver', 'Prepare the professional outputs.'],
  ] as const) {
    await page.getByRole('button', { name: new RegExp(`^${mode}\\b`) }).click();
    await expect(page.getByRole('heading', { name: title })).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`mode=${mode}`));
  }
});

test('advanced navigation synchronizes with product mode', async ({ page }) => {
  await createWorkspace(page);
  await page.getByRole('button', { name: 'Advanced' }).click();
  await expect(page.getByText('PROFESSIONAL WORKFLOW')).toBeVisible();
  await page.getByRole('button', { name: /Change Impact/ }).click();
  await expect(page.getByRole('heading', { name: 'Check the decisions.' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Simple view' })).toBeVisible();
  await page.getByRole('button', { name: /CAD\/BIM Exports/ }).click();
  await expect(page.getByRole('heading', { name: 'Prepare the professional outputs.' })).toBeVisible();
});

test('workspace state survives reload', async ({ page }) => {
  await createWorkspace(page);
  await page.getByRole('button', { name: new RegExp('^Design\\b') }).click();
  await expect(page).toHaveURL(/mode=Design/);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Develop the chosen direction.' })).toBeVisible();
  await expect(page.getByRole('button', { name: new RegExp('^Design\\b') })).toHaveAttribute('aria-current', 'step');
});
