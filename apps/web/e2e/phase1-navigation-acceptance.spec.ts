import { expect, test, type Page } from '@playwright/test';

async function createWorkspace(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: /Create an account/ }).click();
  await page.getByPlaceholder('Your name').fill('Phase 1 Navigation Acceptance');
  await page.getByPlaceholder('Company name').fill('AIrchitect Phase 1 QA');
  await page.getByPlaceholder('name@company.com').fill(`phase1-navigation-${Date.now()}@example.com`);
  await page.getByPlaceholder('At least 12 characters').fill('phase-one-navigation-password');
  await page.getByRole('button', { name: /Create account/ }).click();
  await expect(page.getByText('Your next project starts here.')).toBeVisible();
  await page.getByPlaceholder('e.g. Riyadh Retail Centre').fill('Phase 1 Navigation Project');
  await page.getByRole('button', { name: /Create project/ }).click();
  await page.getByRole('button', { name: /Open workspace/ }).click();
  await expect(page.getByRole('region', { name: 'AIrchitect project workspace' })).toBeVisible();
}

test('browser back and forward restore workspace mode without dropping unrelated URL state', async ({ page }) => {
  await createWorkspace(page);
  await page.evaluate(() => {
    const url = new URL(window.location.href);
    url.searchParams.set('campaign', 'phase1');
    url.hash = 'workspace';
    window.history.replaceState({}, '', url);
  });

  await page.getByRole('button', { name: /^Design\\b/ }).click();
  await expect(page.getByRole('heading', { name: 'Develop the chosen direction.' })).toBeVisible();
  await expect(page).toHaveURL(/campaign=phase1/);
  await expect(page).toHaveURL(/mode=Design/);
  await expect(page).toHaveURL(/#workspace$/);

  await page.getByRole('button', { name: /^Site\\b/ }).click();
  await expect(page.getByRole('heading', { name: 'Understand the place.' })).toBeVisible();
  await expect(page).toHaveURL(/mode=Site/);

  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Develop the chosen direction.' })).toBeVisible();
  await expect(page).toHaveURL(/mode=Design/);
  await expect(page).toHaveURL(/campaign=phase1/);

  await page.goForward();
  await expect(page.getByRole('heading', { name: 'Understand the place.' })).toBeVisible();
  await expect(page).toHaveURL(/mode=Site/);
});

test('a project and selected mode are restored from the deep link after a full reload', async ({ page }) => {
  await createWorkspace(page);
  await page.getByRole('button', { name: /^Deliver\\b/ }).click();
  await expect(page).toHaveURL(/project=[^&]+/);
  await expect(page).toHaveURL(/mode=Deliver/);

  await page.reload();

  await expect(page.getByRole('region', { name: 'AIrchitect project workspace' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Prepare the professional outputs.' })).toBeVisible();
  await expect(page.getByRole('button', { name: /^Deliver\\b/ })).toHaveAttribute('aria-current', 'step');
});
