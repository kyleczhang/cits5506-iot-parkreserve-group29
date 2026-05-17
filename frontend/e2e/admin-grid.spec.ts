/**
 * Admin E2E — sign in as the seeded admin and verify the live grid.
 *
 * The seed migration creates an admin with the email
 * `admin@parkreserve.local` and password `parkreserve-admin`
 * (mirror of backend/scripts/seed.py). If you run this against a
 * non-seeded backend, the test will skip itself.
 */
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const ADMIN_EMAIL =
  process.env["PARKRESERVE_ADMIN_EMAIL"] ?? "admin@parkreserve.local";
const ADMIN_PASSWORD =
  process.env["PARKRESERVE_ADMIN_PASSWORD"] ?? "parkreserve-admin";

test("admin sees the grid and the conflicts page is reachable", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(ADMIN_EMAIL);
  await page.getByLabel(/password/i).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /^sign in$/i }).click();

  // Admin role routes to /admin/grid; if the seed isn't there we skip.
  await page.waitForURL(/\/(admin\/grid|app)/, { timeout: 10_000 });
  if (!page.url().includes("/admin/")) {
    test.skip(
      true,
      "Logged in account is not admin — seed not loaded?",
    );
    return;
  }

  await expect(
    page.getByRole("heading", { name: /live grid/i }),
  ).toBeVisible();

  // Conflicts route is reachable.
  await page.getByRole("link", { name: /conflicts/i }).first().click();
  await expect(
    page.getByRole("heading", { name: /open conflicts/i }),
  ).toBeVisible();

  // Axe scan on the grid.
  await page.goto("/admin/grid");
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
});
