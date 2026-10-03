import { expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { mkdir, unlink, writeFile } from "node:fs/promises";

test("desktop workspace connects and recovers from offline", async ({
  page,
  context,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(page.getByText("No collected activity yet")).toBeVisible();
  await expect(page.getByRole("status")).toHaveText("Connected");
  await page.screenshot({ path: testInfo.outputPath("desktop.png"), fullPage: true });
  await context.setOffline(true);
  await expect(page.getByText("Your workspace is offline")).toBeVisible({ timeout: 12000 });
  await page.screenshot({ path: testInfo.outputPath("offline.png"), fullPage: true });
  await context.setOffline(false);
  await page.getByRole("button", { name: /Try again/ }).click();
  await expect(page.getByText("No collected activity yet")).toBeVisible();
});

test("mobile workspace fits the viewport and exposes its mode", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByText("Fixture mode")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Wallet activity" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.screenshot({ path: testInfo.outputPath("mobile.png"), fullPage: true });
});

test("development server refuses private workspace files", async ({ request }) => {
  const suffix = `${process.pid}-${Date.now()}`;
  const names = [
    `frontend/.env.probe-${suffix}`,
    `watchlist.local.probe-${suffix}.json`,
    `local-data/probe-${suffix}.json`,
  ];
  const created: string[] = [];
  await mkdir("local-data", { recursive: true });
  try {
    for (const name of names) {
      await writeFile(name, "PRIVATE_PROBE_MUST_NOT_BE_SERVED", { mode: 0o600, flag: "wx" });
      created.push(name);
      const response = await request.get(`/@fs/${resolve(name)}`);
      expect(response.status()).toBe(403);
      expect(await response.text()).not.toContain("PRIVATE_PROBE_MUST_NOT_BE_SERVED");
    }
  } finally {
    await Promise.all(created.map((name) => unlink(name)));
  }
});
