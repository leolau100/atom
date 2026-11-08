import { launch, shot, dump } from './lib.mjs';

const { ctx, page } = await launch();
await page.goto('http://localhost:3000/en/login', { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(3000);
await page.fill('input[name="identity"]', 'demoadmin@magistrala.local');
await page.fill('input[name="password"]', 'Demo1234!@#');
await page.waitForTimeout(500);
await page.click('button[type="submit"]');
await page.waitForTimeout(10000);
await shot(page, 'test-login');
await dump(page, '登录后');
await ctx.close();
