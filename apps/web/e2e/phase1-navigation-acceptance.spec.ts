import { expect, test, type Page } from '@playwright/test';

async function createWorkspace(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: /Create an account/ }).click();
  await page.getByPlaceholder('Your name').fill('Phase 1 Navigation Acceptance');
  await page.getByPlaceholder('Company name').fill('AIrchitect Phase 1 QA');
  await page.getByPlaceholder('name@company.com').fill(`phase1-navigation-${Date.now()}@example.com`);
  await page.getByPlaceholder('At least 12 characters').fill('phase-one-navigation-password');
  await page.getByRole('button', { name: /Create account/ }).click();

  await expect(page.getByRole('heading', { name: 'What are you building?' })).toBeVisible();
  await page.getByRole('button', { name: 'New project', exact: true }).click();
  await page.getByLabel('New project name').fill('Phase 1 Navigation Project');
  await page.getByRole('button', { name: 'Create', exact: true }).click();
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

  const workflow = page.getByRole('navigation', { name: 'Project workflow' });
  await expect(workflow).toBeVisible();
  await workflow.getByRole('button', { name: /Design/ }).click();
  await expect(page.getByRole('heading', { name: 'Develop the chosen direction.' })).toBeVisible();
  await expect(page).toHaveURL(/campaign=phase1/);
  await expect(page).toHaveURL(/mode=Design/);
  await expect(page).toHaveURL(/#workspace$/);

  await workflow.getByRole('button', { name: /Site/ }).click();
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
  const workflow = page.getByRole('navigation', { name: 'Project workflow' });
  await expect(workflow).toBeVisible();
  await workflow.getByRole('button', { name: /Deliver/ }).click();
  await expect(page).toHaveURL(/project=[^&]+/);
  await expect(page).toHaveURL(/mode=Deliver/);

  await page.reload();

  await expect(page.getByRole('region', { name: 'AIrchitect project workspace' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Prepare the professional outputs.' })).toBeVisible();
  await expect(workflow.getByRole('button', { name: /Deliver/ })).toHaveAttribute('aria-current', 'step');
});
