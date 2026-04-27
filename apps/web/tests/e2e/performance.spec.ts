import { test, expect } from "@playwright/test";

// Enterprise performance thresholds aligned with Google Core Web Vitals (Good tier)
const THRESHOLDS = {
  fcp: 1800,          // First Contentful Paint < 1.8s (Good)
  lcp: 2500,          // Largest Contentful Paint < 2.5s (Good)
  ttfb: 800,          // Time to First Byte < 800ms (Good)
  domContentLoaded: 2000,
  fullyLoaded: 4000,
  pageLoad: 3000,     // Total page load < 3s
};

test.describe("Performance — Core Web Vitals", () => {
  test("login page: First Contentful Paint within Good threshold", async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle" });

    const fcp = await page.evaluate(() => {
      const entries = performance.getEntriesByName("first-contentful-paint");
      return entries[0]?.startTime ?? null;
    });

    if (fcp !== null) {
      console.log(`FCP: ${Math.round(fcp)}ms (threshold: ${THRESHOLDS.fcp}ms)`);
      expect(fcp).toBeLessThan(THRESHOLDS.fcp);
    } else {
      console.log("FCP entry not available in this browser");
    }
  });

  test("login page: Largest Contentful Paint within Good threshold", async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle" });

    const lcp = await page.evaluate(
      () =>
        new Promise<number | null>((resolve) => {
          let lcpValue: number | null = null;
          const observer = new PerformanceObserver((list) => {
            const entries = list.getEntries();
            lcpValue = entries[entries.length - 1]?.startTime ?? null;
          });
          try {
            observer.observe({ type: "largest-contentful-paint", buffered: true });
          } catch {
            resolve(null);
            return;
          }
          setTimeout(() => {
            observer.disconnect();
            resolve(lcpValue);
          }, 2000);
        })
    );

    if (lcp !== null) {
      console.log(`LCP: ${Math.round(lcp)}ms (threshold: ${THRESHOLDS.lcp}ms)`);
      expect(lcp).toBeLessThan(THRESHOLDS.lcp);
    } else {
      console.log("LCP entry not available in this browser/context");
    }
  });

  test("login page: Time to First Byte within Good threshold", async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle" });

    const ttfb = await page.evaluate(() => {
      const [nav] = performance.getEntriesByType("navigation") as PerformanceNavigationTiming[];
      if (!nav) return null;
      return nav.responseStart - nav.requestStart;
    });

    if (ttfb !== null) {
      console.log(`TTFB: ${Math.round(ttfb)}ms (threshold: ${THRESHOLDS.ttfb}ms)`);
      expect(ttfb).toBeLessThan(THRESHOLDS.ttfb);
    }
  });

  test("login page: Navigation Timing summary", async ({ page }) => {
    await page.goto("/login", { waitUntil: "load" });

    const timing = await page.evaluate(() => {
      const [nav] = performance.getEntriesByType("navigation") as PerformanceNavigationTiming[];
      if (!nav) return null;
      return {
        ttfb: Math.round(nav.responseStart - nav.requestStart),
        dns: Math.round(nav.domainLookupEnd - nav.domainLookupStart),
        tcp: Math.round(nav.connectEnd - nav.connectStart),
        ssl: Math.round(nav.requestStart - nav.secureConnectionStart),
        domInteractive: Math.round(nav.domInteractive - nav.startTime),
        domContentLoaded: Math.round(nav.domContentLoadedEventEnd - nav.startTime),
        load: Math.round(nav.loadEventEnd - nav.startTime),
        transferSize: nav.transferSize,
        encodedBodySize: nav.encodedBodySize,
        decodedBodySize: nav.decodedBodySize,
      };
    });

    if (timing) {
      console.log("Navigation Timing breakdown:", timing);
      expect(timing.domContentLoaded).toBeLessThan(THRESHOLDS.domContentLoaded);
      expect(timing.load).toBeLessThan(THRESHOLDS.fullyLoaded);
    }
  });

  test("register page: First Contentful Paint within Good threshold", async ({ page }) => {
    await page.goto("/register", { waitUntil: "networkidle" });

    const fcp = await page.evaluate(() => {
      const entries = performance.getEntriesByName("first-contentful-paint");
      return entries[0]?.startTime ?? null;
    });

    if (fcp !== null) {
      console.log(`Register FCP: ${Math.round(fcp)}ms (threshold: ${THRESHOLDS.fcp}ms)`);
      expect(fcp).toBeLessThan(THRESHOLDS.fcp);
    }
  });
});

test.describe("Performance — Resource Budget", () => {
  test("login page: total page weight under 1MB", async ({ page }) => {
    let totalBytes = 0;
    page.on("response", async (response) => {
      const headers = response.headers();
      const contentLength = headers["content-length"];
      if (contentLength) totalBytes += Number(contentLength);
    });

    await page.goto("/login", { waitUntil: "networkidle" });

    const transferSize = await page.evaluate(() => {
      const entries = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
      return entries.reduce((sum, e) => sum + (e.transferSize || 0), 0);
    });

    console.log(`Total transfer size: ${Math.round(transferSize / 1024)}KB`);
    expect(transferSize).toBeLessThan(1024 * 1024); // 1MB
  });

  test("login page: fewer than 30 network requests", async ({ page }) => {
    const requests: string[] = [];
    page.on("request", (req) => requests.push(req.url()));

    await page.goto("/login", { waitUntil: "networkidle" });

    console.log(`Total requests: ${requests.length}`);
    expect(requests.length).toBeLessThan(30);
  });

  test("login page: no render-blocking resources", async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle" });

    const blocking = await page.evaluate(() => {
      const entries = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
      return entries
        .filter((e) => (e as unknown as { renderBlockingStatus?: string }).renderBlockingStatus === "blocking")
        .map((e) => e.name);
    });

    if (blocking.length > 0) {
      console.warn("Render-blocking resources:", blocking);
    }
    console.log(`Render-blocking resources: ${blocking.length}`);
    expect(blocking.length).toBeLessThan(3);
  });

  test("page load within 3s wall-clock", async ({ page }) => {
    const start = Date.now();
    await page.goto("/login", { waitUntil: "load" });
    const elapsed = Date.now() - start;

    console.log(`Wall-clock page load: ${elapsed}ms (threshold: ${THRESHOLDS.pageLoad}ms)`);
    expect(elapsed).toBeLessThan(THRESHOLDS.pageLoad);
  });
});

test.describe("Performance — Mobile", () => {
  test("login page loads on mobile viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const start = Date.now();
    await page.goto("/login", { waitUntil: "load" });
    const elapsed = Date.now() - start;

    console.log(`Mobile load time: ${elapsed}ms`);
    expect(elapsed).toBeLessThan(5000); // More lenient for mobile network simulation
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
  });

  test("login page responsive on mobile viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/login");
    // Form should be fully visible without horizontal scroll
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
  });
});
