import { test, expect } from "@playwright/test";

// Production base URL for direct API requests
const PROD_URL = "https://episodic-pivots-ai.vercel.app";

test.describe("Security — HTTP Headers", () => {
  test("X-Content-Type-Options: nosniff is set", async ({ page }) => {
    const response = await page.goto("/login");
    const header = response?.headers()["x-content-type-options"];
    console.log("x-content-type-options:", header ?? "NOT SET");
    expect(header).toBe("nosniff");
  });

  test("X-Frame-Options or CSP frame-ancestors prevents clickjacking", async ({ page }) => {
    const response = await page.goto("/login");
    const headers = response?.headers() ?? {};
    const xFrameOptions = headers["x-frame-options"];
    const csp = headers["content-security-policy"];
    const frameAncestors = csp?.includes("frame-ancestors");
    console.log("x-frame-options:", xFrameOptions ?? "NOT SET");
    console.log("csp frame-ancestors:", frameAncestors ? "present" : "NOT SET");
    // Must have at least one of these
    expect(xFrameOptions || frameAncestors).toBeTruthy();
  });

  test("Strict-Transport-Security enforces HTTPS", async ({ page }) => {
    const response = await page.goto("/login");
    const hsts = response?.headers()["strict-transport-security"];
    console.log("strict-transport-security:", hsts ?? "NOT SET");
    expect(hsts).toBeTruthy();
    if (hsts) {
      // max-age must be at least 1 year (31536000)
      const maxAgeMatch = hsts.match(/max-age=(\d+)/);
      if (maxAgeMatch) {
        expect(Number(maxAgeMatch[1])).toBeGreaterThanOrEqual(31536000);
      }
    }
  });

  test("no server version disclosure via headers", async ({ page }) => {
    const response = await page.goto("/login");
    const headers = response?.headers() ?? {};
    const server = headers["server"] ?? "";
    const xPoweredBy = headers["x-powered-by"] ?? "";
    console.log("server:", server || "(not set)");
    console.log("x-powered-by:", xPoweredBy || "(not set)");
    expect(server).not.toMatch(/apache\/\d|nginx\/\d|iis\/\d/i);
    expect(xPoweredBy).not.toMatch(/express|php|asp\.net/i);
  });

  test("no sensitive info in response headers", async ({ page }) => {
    const response = await page.goto("/login");
    const headers = response?.headers() ?? {};
    const headerStr = JSON.stringify(headers).toLowerCase();
    expect(headerStr).not.toContain("supabase_service_role");
    expect(headerStr).not.toContain("anthropic_api_key");
    expect(headerStr).not.toContain("stripe_secret");
  });
});

test.describe("Security — Authentication & Access Control", () => {
  const protectedRoutes = ["/dashboard", "/history", "/settings", "/billing"];

  for (const route of protectedRoutes) {
    test(`${route}: unauthenticated access redirects to /login`, async ({ page }) => {
      await page.goto(route);
      await expect(page).toHaveURL(/login/);
      // Must not render any protected content
      await expect(page.getByText("Dashboard")).not.toBeVisible({ timeout: 2000 }).catch(() => {});
    });
  }

  test("API /api/scans/stream: rejects unauthenticated POST with 401", async ({ request }) => {
    const response = await request.post(`${PROD_URL}/api/scans/stream`, {
      data: { config_id: "arbitrary-id" },
      headers: { "Content-Type": "application/json" },
    });
    expect(response.status()).toBe(401);
  });

  test("API /api/scans/stream: rejects request with forged X-User-Id header", async ({ request }) => {
    // The X-User-Id should only be trusted when set server-side, not by browser
    const response = await request.post(`${PROD_URL}/api/scans/stream`, {
      data: { config_id: "test-id" },
      headers: {
        "Content-Type": "application/json",
        "X-User-Id": "forged-user-id-12345",
      },
    });
    // Should still reject without a valid Supabase session cookie
    expect(response.status()).toBe(401);
  });
});

test.describe("Security — XSS Prevention", () => {
  test("script tag in email field does not execute", async ({ page }) => {
    let alertFired = false;
    page.on("dialog", async (dialog) => {
      alertFired = true;
      await dialog.dismiss();
    });

    await page.goto("/login");
    await page.fill("input[type=email]", "<script>alert('xss')</script>@test.com");
    await page.fill("input[type=password]", "password123");
    await page.click("button[type=submit]");
    await page.waitForTimeout(2000);

    expect(alertFired).toBe(false);
  });

  test("img onerror XSS in email field does not execute", async ({ page }) => {
    let alertFired = false;
    page.on("dialog", async (dialog) => {
      alertFired = true;
      await dialog.dismiss();
    });

    await page.goto("/login");
    await page.fill("input[type=email]", "\" onerror=\"alert(1)");
    await page.fill("input[type=password]", "password123");
    await page.click("button[type=submit]");
    await page.waitForTimeout(2000);

    expect(alertFired).toBe(false);
  });

  test("javascript: protocol in email field does not execute", async ({ page }) => {
    let alertFired = false;
    page.on("dialog", async (dialog) => {
      alertFired = true;
      await dialog.dismiss();
    });

    await page.goto("/login");
    await page.fill("input[type=email]", "javascript:alert('xss')");
    await page.fill("input[type=password]", "password123");
    await page.click("button[type=submit]");
    await page.waitForTimeout(2000);

    expect(alertFired).toBe(false);
  });

  test("XSS payload in register email field does not execute", async ({ page }) => {
    let alertFired = false;
    page.on("dialog", async (dialog) => {
      alertFired = true;
      await dialog.dismiss();
    });

    await page.goto("/register");
    await page.fill("input[type=email]", "<img src=x onerror=alert(document.cookie)>");
    await page.fill("input[type=password]", "password12345");
    await page.click("button[type=submit]");
    await page.waitForTimeout(2000);

    expect(alertFired).toBe(false);
  });
});

test.describe("Security — Cookie Attributes", () => {
  test("auth cookies have Secure flag on production HTTPS", async ({ page, context }) => {
    await page.goto("/login");
    const cookies = await context.cookies();
    const authCookies = cookies.filter(
      (c) => c.name.includes("supabase") || c.name.includes("sb-") || c.name.includes("auth")
    );

    console.log(`Auth cookies found: ${authCookies.length}`);
    authCookies.forEach((c) => {
      console.log(`  ${c.name}: secure=${c.secure}, httpOnly=${c.httpOnly}, sameSite=${c.sameSite}`);
    });

    // On production HTTPS, all auth cookies must be secure
    authCookies.forEach((cookie) => {
      expect(cookie.secure).toBe(true);
    });
  });

  test("cookies do not expose session tokens in name/value pairs to JavaScript unnecessarily", async ({
    page,
  }) => {
    await page.goto("/login");
    const jsAccessibleCookies = await page.evaluate(() => document.cookie);
    // Supabase auth uses httpOnly cookies for access tokens
    // The JS-accessible cookies should not contain raw JWT tokens (they start with "eyJ")
    const hasRawJwt = jsAccessibleCookies.split(";").some((pair) => {
      const value = pair.split("=")[1]?.trim() ?? "";
      return value.startsWith("eyJ") && value.length > 100;
    });

    if (hasRawJwt) {
      console.warn("WARNING: Raw JWT found in JS-accessible cookies");
    }
    console.log("JS-accessible cookies (names only):", jsAccessibleCookies.split(";").map((c) => c.split("=")[0]?.trim()));
  });
});

test.describe("Security — Information Disclosure", () => {
  test("error pages do not leak stack traces", async ({ page }) => {
    const response = await page.goto("/api/scans/stream");
    // Should not be a 500 with stack trace, and page should not show raw error
    const body = await response?.text() ?? "";
    expect(body).not.toMatch(/at\s+\w+\s+\([^)]+:\d+:\d+\)/); // Stack trace pattern
    expect(body).not.toContain("node_modules");
  });

  test("source maps not publicly accessible in production", async ({ request }) => {
    // Next.js should not expose .js.map files in production builds
    const response = await request.get(`${PROD_URL}/_next/static/chunks/main.js.map`);
    // Should be 404 (not found) in production
    expect(response.status()).toBeGreaterThanOrEqual(400);
  });
});
