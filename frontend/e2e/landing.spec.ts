/**
 * Smoke: the public landing page paints and passes a baseline axe scan.
 */
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("landing strip renders + zero serious axe violations", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: /sign in/i })).toBeVisible();

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
});

test("help page is reachable and accessible", async ({ page }) => {
  await page.goto("/help");
  await expect(
    page.getByRole("heading", { name: /how to use/i }),
  ).toBeVisible();

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
});
