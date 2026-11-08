import { chromium } from 'playwright-core';
import { PROFILE, WS } from './lib.mjs';

const ctx = await chromium.launchPersistentContext(PROFILE, {
  channel: 'chrome',
  headless: true,
  args: ['----no-sandbox', '--disable-dev-shm-usage'],
  viewport: { width: 1600, height: 1000 },
});
const page = ctx.pages()[0] || (await ctx.newPage());

await page.goto('http://localhost:3000/en', { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(6000);
console.log('workspace list url:', page.url());

// 多种方式尝试进入 Smart Factory
const attempts = [
  () => page.locator('a:has-text("Smart Factory")').first(),
  () => page.getByRole('link', { name: /Smart Factory/ }).first(),
  () => page.locator('div').filter({ hasText: /^Smart Factory$/ }).first(),
];

for (let i = 0; i < attempts.length; i++) {
  const loc = attempts[i]();
  const vis = await loc.isVisible().catch(() => false);
  console.log(`attempt ${i}: visible=${vis}`);
  if (vis) {
    try {
      await loc.click({ force: i === 2 });
      await page.waitForURL(/workspace/, { timeout: 15000 });
      console.log('success with attempt', i, 'url:', page.url());
      break;
    } catch (e) {
      console.log('attempt', i, 'failed:', e.message.slice(0, 120));
    }
  }
}

await page.waitForTimeout(4000);
console.log('final url:', page.url());

await ctx.close();
