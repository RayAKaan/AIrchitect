import { expect, test } from '@playwright/test';

test('registration verification, resend, password recovery and reset are available from the auth UI', async ({ page }) => {
  await page.route('**/auth/refresh', route => route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'No active session' }) }));
  await page.goto('/');
  await page.getByRole('button', { name: /Create an account/ }).click();
  await page.getByPlaceholder('Your name').fill('Identity UI Acceptance');
  await page.getByPlaceholder('Company name').fill('Identity UI QA');
  await page.getByPlaceholder('name@company.com').fill('identity-ui@example.test');
  await page.getByPlaceholder('At least 12 characters').fill('identity-ui-acceptance-password');
  await page.route('**/auth/register', route => route.fulfill({
    status: 201, contentType: 'application/json',
    body: JSON.stringify({
      access_token: '', verification_required: true,
      message: 'Check your email to verify your account.',
      user: { id: 'test-user', email: 'identity-ui@example.test', name: 'Identity UI Acceptance' },
    }),
  }));
  await page.getByRole('button', { name: /Create account/ }).click();
  await expect(page.getByRole('heading', { name: 'Check your inbox' })).toBeVisible();
  await page.route('**/auth/resend-verification', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ message: 'If the account requires verification, an email will be sent shortly.' }),
  }));
  await page.getByRole('button', { name: 'Resend verification email' }).click();
  await expect(page.getByText(/If the account requires verification/)).toBeVisible();

  await page.route('**/auth/verify-email', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ verified: true }),
  }));
  await page.goto('/?verify_token=' + 'v'.repeat(43));
  await expect(page.getByText('Your email address is verified. You can now sign in.')).toBeVisible();

  await page.getByRole('button', { name: 'Forgot password?' }).click();
  await page.getByPlaceholder('name@company.com').fill('identity-ui@example.test');
  await page.route('**/auth/forgot-password', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ message: 'If an account exists for that address, password-reset instructions will be sent.', debug_token: null }),
  }));
  await page.getByRole('button', { name: 'Send reset instructions' }).click();
  await expect(page.getByText(/If an account exists for that address/)).toBeVisible();

  await page.route('**/auth/reset-password', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ password_reset: true }),
  }));
  await page.goto('/?reset_token=' + 'r'.repeat(43));
  await page.getByPlaceholder('At least 12 characters').fill('a-new-secure-password-for-ui');
  await page.getByRole('button', { name: 'Set new password' }).click();
  await expect(page.getByText('Your password has been reset. Sign in with your new password.')).toBeVisible();
});
