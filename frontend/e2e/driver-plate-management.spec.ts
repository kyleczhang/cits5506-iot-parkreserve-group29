/**
 * Driver E2E happy path 2 — bind a plate, see it listed, remove it.
 *
 * Replaces the "manual check-in" flow which needs an MQTT-driven
 * `reservation.pending_check_in` event we can't easily inject from
 * Playwright. Plate management is the next-most-valuable read/write
 * coverage on the driver side.
 */
import { expect, test } from "@playwright/test";
import { bindPlate, randomEmail, registerNewUser } from "./helpers";

test("driver binds and removes a plate", async ({ page }) => {
  await registerNewUser(page, randomEmail());
  await bindPlate(page, "E2EMGT");

  // Click Remove → confirm in the AlertDialog.
  await page.getByRole("button", { name: /remove plate e2emgt/i }).click();
  await page.getByRole("button", { name: /^remove$/i }).click();

  await expect(page.getByText("E2EMGT")).toHaveCount(0);
});
