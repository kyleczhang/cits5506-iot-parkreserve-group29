/**
 * Shared E2E helpers.
 *
 * Driver-side flows hit the real backend; we register a fresh user per
 * test run so they don't collide with the seed data.
 */
import { expect, type Page } from "@playwright/test";

export function randomEmail(): string {
  const tag = Math.random().toString(36).slice(2, 10);
  return `e2e_${tag}@example.com`;
}

export const E2E_PASSWORD = "park-reserve-e2e!";

/** Register a fresh account; backend chains a login so we land on /app. */
export async function registerNewUser(page: Page, email: string) {
  await page.goto("/register");
  await page.getByLabel(/full name/i).fill("E2E Driver");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(E2E_PASSWORD);
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page).toHaveURL(/\/app/);
}

/** Bind a demo plate so the booking wizard can succeed. */
export async function bindPlate(page: Page, plate = "E2EPLT") {
  await page.goto("/app/plates");
  await page.getByLabel(/^plate/i).fill(plate);
  await page.getByRole("button", { name: /bind plate/i }).click();
  await expect(page.getByText(new RegExp(plate, "i"))).toBeVisible();
}
