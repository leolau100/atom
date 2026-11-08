import { chromium } from 'playwright-core';
import { PROFILE, WS } from './lib.mjs';

const ctx = await chromium.launchPersistentContext(PROFILE, {
  channel: 'chrome',
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
  viewport: { width: 1600, height: 1000 },
});
const page = ctx.pages()[0] || (await ctx.newPage());

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages`, { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(4000);

const url = page.url();
console.log('current url:', url);
if (url.includes('/login')) {
  console.log('需要登录');
  await page.fill('input[name="identity"]', 'demoadmin@magistrala.local');
  await page.waitForTimeout(300);
  await page.fill('input[name="password"]', 'Demo1234!@#');
  await page.waitForTimeout(500);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(10000);
  console.log('after login url:', page.url());
} else {
  console.log('已登录');
}

await ctx.close();
