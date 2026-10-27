import { expect, test } from '@playwright/test';

test('S16 end-to-end architect workspace acceptance', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /Create an account/ }).click();
  await page.getByPlaceholder('Your name').fill('S16 Acceptance');
  await page.getByPlaceholder('Company name').fill('AIrchitect QA');
  await page.getByPlaceholder('name@company.com').fill('s16-' + Date.now() + '@example.com');
  await page.getByPlaceholder('At least 12 characters').fill('s16-production-password');
  await page.getByRole('button', { name: /Create account/ }).click();
  await expect(page.getByText('Your next project starts here.')).toBeVisible();

  await page.getByPlaceholder('e.g. Riyadh Retail Centre').fill('S16 Acceptance Project');
  await page.getByRole('button', { name: /Create project/ }).click();
  await page.getByRole('button', { name: /Open workspace/ }).click();

  for (const stage of ['Brief', 'World Model', 'Semantic Model', 'Design', 'CAD/BIM Exports', 'Engineering', 'Change Impact', 'Release Validation', 'Regulatory']) {
    await expect(page.getByRole('button', { name: new RegExp(`\\b${stage}\\b`) }).first()).toBeVisible();
  }
  await expect(page.getByRole('heading', { name: 'Versions' })).toBeVisible();

  await page.getByRole('button', { name: 'Brief', exact: true }).last().click();
  await page.getByPlaceholder('Describe your building project…').fill(
    'Six-floor commercial retail building in Riyadh with 8,000 m2 GFA on a 2,000 m2 site and basement parking.',
  );
  await page.getByRole('button', { name: 'Analyze and persist brief' }).click();
  await expect(page.getByText(/Brief revision 1/)).toBeVisible();

  await page.getByRole('button', { name: 'World Model', exact: true }).last().click();
  await page.getByRole('button', { name: /Commit V1/ }).click();
  await expect(page.getByText(/World hash/)).toBeVisible();
  await expect(page.getByText(/Revision/).first()).toBeVisible();
});
