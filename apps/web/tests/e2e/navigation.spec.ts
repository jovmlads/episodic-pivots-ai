import { test, expect } from "@playwright/test";

test.describe("Navigation & Routing", () => {
  test("page title is set to Episodic Pivot", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveTitle(/Episodic Pivot/i);
  });

  test("login → register link navigates correctly", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("link", { name: /14-day free trial/i }).click();
    await expect(page).toHaveURL(/register/);
    await expect(page).toHaveTitle(/Episodic Pivot/i);
  });

  test("register → login link navigates correctly", async ({ page }) => {
    await page.goto("/register");
    await page.getByRole("link", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/login/);
    await expect(page).toHaveTitle(/Episodic Pivot/i);
  });

  test("unknown route returns 404 or redirects to login", async ({ page }) => {
    const response = await page.goto("/this-route-does-not-exist-xyz-404");
    const status = response?.status();
    const url = page.url();
    // Must be either a 404 or a redirect to login (middleware catches unauthenticated)
    expect(status === 404 || url.includes("login")).toBeTruthy();
  });

  test("html lang attribute is set", async ({ page }) => {
    await page.goto("/login");
    const lang = await page.locator("html").getAttribute("lang");
    expect(lang).toBe("en");
  });

  test("dark mode class applied to html element", async ({ page }) => {
    await page.goto("/login");
    const classes = await page.locator("html").getAttribute("class");
    expect(classes).toContain("dark");
  });

  test("no broken images on login page", async ({ page }) => {
    const failedImages: string[] = [];
    page.on("response", (response) => {
      if (
        response.request().resourceType() === "image" &&
        response.status() >= 400
      ) {
        failedImages.push(response.url());
      }
    });
    await page.goto("/login", { waitUntil: "networkidle" });
    expect(failedImages).toHaveLength(0);
  });

  test("no console errors on login page", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto("/login", { waitUntil: "networkidle" });
    // Filter out known benign third-party errors
    const criticalErrors = errors.filter(
      (e) => !e.includes("favicon") && !e.includes("net::ERR")
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test("no console errors on register page", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto("/register", { waitUntil: "networkidle" });
    const criticalErrors = errors.filter(
      (e) => !e.includes("favicon") && !e.includes("net::ERR")
    );
    expect(criticalErrors).toHaveLength(0);
  });
});
