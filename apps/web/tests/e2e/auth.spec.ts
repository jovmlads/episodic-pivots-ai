import { test, expect } from "@playwright/test";

test("login page renders", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("Episodic Pivot")).toBeVisible();
  await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
});

test("register page renders", async ({ page }) => {
  await page.goto("/register");
  await expect(page.getByRole("button", { name: /start free trial/i })).toBeVisible();
});

test("unauthenticated redirect from dashboard", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/login/);
});

test("invalid login shows error", async ({ page }) => {
  await page.goto("/login");
  await page.fill("input[type=email]", "bad@example.com");
  await page.fill("input[type=password]", "wrongpassword");
  await page.click("button[type=submit]");
  // Error toast should appear
  await expect(page.locator("[data-sonner-toast]")).toBeVisible({ timeout: 5000 });
});
