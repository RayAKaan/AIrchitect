import { expect, test } from '@playwright/test';

test('S16 end-to-end architect workspace acceptance', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /Create an account/ }).click();
  await page.getByPlaceholder('Your name').fill('S16 Acceptance');
  await page.getByPlaceholder('Company name').fill('AIrchitect QA');
  await page.getByPlaceholder('name@company.com').fill('s16-' + Date.now() + '@example.com');
  await page.getByPlaceholder('At least 12 characters').fill('s16-production-password');
  await page.getByRole('button', { name: /Create account/ }).click();
  await expect(page.getByRole('heading', { name: 'What are you building?' })).toBeVisible();
  await page.getByRole('button', { name: 'New project', exact: true }).click();
  await page.getByLabel('New project name').fill('S16 Acceptance Project');
  await page.getByRole('button', { name: 'Create', exact: true }).click();
  await expect(page.getByRole('region', { name: 'AIrchitect project workspace' })).toBeVisible();

  for (const mode of ['Brief', 'Site', 'Explore', 'Design', 'Validate', 'Deliver']) {
    await expect(page.getByRole('button', { name: new RegExp(`\\b${mode}\\b`) })).toBeVisible();
  }
  await page.getByRole('button', { name: 'Advanced' }).click();
  for (const stage of ['Brief', 'World Model', 'Semantic Model', 'Design', 'CAD/BIM Exports', 'Engineering', 'Change Impact', 'Release Validation', 'Regulatory']) {
    await expect(page.getByRole('button', { name: new RegExp(`\\b${stage}\\b`) }).first()).toBeVisible();
  }
  await page.getByRole('button', { name: /Change Impact/ }).click();
  await expect(page.getByRole('heading', { name: 'Dependency graph & change propagation' })).toBeVisible();
  await page.getByRole('button', { name: /CAD\/BIM Exports/ }).click();
  await expect(page.getByRole('heading', { name: 'Validated exports' })).toBeVisible();
});
