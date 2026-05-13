/**
 * Driver E2E happy path 1 — register → plate → book → clean cancel.
 *
 * Verified against the legal reservation state graph
 * (backend/app/services/reservation_service.py:193) — cancelling from
 * `ACTIVE` is fine; we deliberately do NOT chain a check-in here
 * because cancel-after-check-in is rejected with 409.
 *
 * NOTE: this spec talks to a real backend. The CI workflow stands up
 * docker/docker-compose + `make migrate seed dev` before invoking
 * Playwright; for local runs you must do the same.
 */
import { expect, test } from "@playwright/test";
import { bindPlate, randomEmail, registerNewUser } from "./helpers";

test("driver registers, books an available bay, then cancels cleanly", async ({
  page,
}) => {
  test.setTimeout(60_000);

  await registerNewUser(page, randomEmail());
  await bindPlate(page, "E2ECLN");

  // From the home page, click `Book` on the first available bay.
  await page.goto("/app");
  const firstBookBtn = page
    .getByRole("button", { name: /book this bay/i })
    .first();
  if ((await firstBookBtn.count()) === 0) {
    test.skip(
      true,
      "No AVAILABLE bay in the live backend; cannot exercise booking happy-path",
    );
    return;
  }
  await firstBookBtn.click();
  await expect(page).toHaveURL(/\/app\/reservations\/new/);

  // Step 1 — the preset bay is already selected via ?bay=…; press Continue.
  await page.getByRole("button", { name: /^continue$/i }).click();

  // Step 2 — pick an arrival ~5 minutes from now.
  const inFive = new Date(Date.now() + 5 * 60 * 1000);
  const local = inFive.toISOString().slice(0, 16); // YYYY-MM-DDTHH:MM
  await page.getByLabel(/expected arrival time/i).fill(local);
  await page.getByRole("button", { name: /continue to payment/i }).click();

  // Step 3 — fill the mock card and submit.
  await page.getByLabel(/card number/i).fill("4111111111111111");
  await page.getByLabel(/cardholder name/i).fill("E2E Driver");
  await page.getByLabel(/^month/i).fill("12");
  await page.getByLabel(/^year/i).fill("2030");
  await page.getByLabel(/^cvv/i).fill("123");
  await page.getByRole("button", { name: /confirm reservation/i }).click();

  await expect(page).toHaveURL(/\/app\/reservations\//);
  await expect(
    page.getByRole("heading", { name: /bay /i }),
  ).toBeVisible();

  // Cancel cleanly (status is ACTIVE).
  await page.getByRole("button", { name: /cancel reservation/i }).click();
  // The toast title may appear once; assert the cockpit re-renders.
  await expect(
    page.getByText(/cancelled|reservation cancelled/i).first(),
  ).toBeVisible({ timeout: 10_000 });
});
