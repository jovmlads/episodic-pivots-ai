import { test, expect } from "@playwright/test";

test.describe("Authentication — Public Pages", () => {
  test("login page renders with all required elements", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText("Episodic Pivot")).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
    await expect(page.locator("input[type=email]")).toBeVisible();
    await expect(page.locator("input[type=password]")).toBeVisible();
    await expect(page.getByRole("link", { name: /14-day free trial/i })).toBeVisible();
  });

  test("register page renders with all required elements", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByText("Episodic Pivot")).toBeVisible();
    await expect(page.getByRole("button", { name: /start free trial/i })).toBeVisible();
    await expect(page.locator("input[type=email]")).toBeVisible();
    await expect(page.locator("input[type=password]")).toBeVisible();
    await expect(page.getByRole("link", { name: /sign in/i })).toBeVisible();
  });

  test("root / redirects unauthenticated user to /login", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/login/);
  });
});

test.describe("Authentication — Protected Route Redirects", () => {
  const protectedRoutes = ["/dashboard", "/history", "/settings", "/billing"];

  for (const route of protectedRoutes) {
    test(`unauthenticated access to ${route} redirects to /login`, async ({ page }) => {
      await page.goto(route);
      await expect(page).toHaveURL(/login/);
    });
  }
});

test.describe("Authentication — Error States", () => {
  test("invalid credentials shows error toast", async ({ page }) => {
    await page.goto("/login");
    await page.fill("input[type=email]", "nonexistent@example.com");
    await page.fill("input[type=password]", "wrongpassword123");
    await page.click("button[type=submit]");
    await expect(page.locator("[data-sonner-toast]")).toBeVisible({ timeout: 8000 });
  });

  test("password shorter than 8 chars fails HTML5 constraint validation", async ({ page }) => {
    await page.goto("/register");
    await page.fill("input[type=email]", "test@example.com");
    await page.fill("input[type=password]", "short1");

    // HTML5 minLength blocks submission before JS runs — verify constraint fails
    const isValid = await page
      .locator("input[type=password]")
      .evaluate((el: HTMLInputElement) => el.validity.valid);
    expect(isValid).toBe(false);

    // After click, browser validation should keep us on /register
    await page.click("button[type=submit]");
    await expect(page).toHaveURL(/register/);
  });

  test("submit button shows loading state during login attempt", async ({ page }) => {
    await page.goto("/login");
    await page.fill("input[type=email]", "test@example.com");
    await page.fill("input[type=password]", "password123");

    const submitButton = page.getByRole("button", { name: /sign in/i });
    await submitButton.click();

    // Button should show loading state briefly
    await expect(page.getByRole("button", { name: /signing in/i })).toBeVisible({ timeout: 2000 });
  });
});

test.describe("Authentication — Form Validation", () => {
  test("email input enforces email type", async ({ page }) => {
    await page.goto("/login");
    const type = await page.locator("input[type=email]").first().getAttribute("type");
    expect(type).toBe("email");
  });

  test("password input is masked (type=password)", async ({ page }) => {
    await page.goto("/login");
    const type = await page.locator("input[type=password]").first().getAttribute("type");
    expect(type).toBe("password");
  });

  test("register password enforces minlength=8", async ({ page }) => {
    await page.goto("/register");
    const minLength = await page.locator("input[type=password]").getAttribute("minlength");
    expect(Number(minLength)).toBeGreaterThanOrEqual(8);
  });

  test("login email and password fields are required", async ({ page }) => {
    await page.goto("/login");
    const emailRequired = await page.locator("input[type=email]").getAttribute("required");
    const passwordRequired = await page.locator("input[type=password]").getAttribute("required");
    expect(emailRequired).not.toBeNull();
    expect(passwordRequired).not.toBeNull();
  });
});
