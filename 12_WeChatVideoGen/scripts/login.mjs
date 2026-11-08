import { launch, shot, dump } from './lib.mjs';

const { ctx, page } = await launch();
await page.goto('http://localhost:3000/en/login', { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(3000);
await shot(page, '01-login');

await page.fill('input[name="identity"]', 'admin@example.com');
await page.fill('input[name="password"]', '12345678');
await page.waitForTimeout(500);
await shot(page, '02-login-filled');
await page.click('button[type="submit"]');
await page.waitForTimeout(8000);
await shot(page, '03-after-login');
await dump(page, '登录后页面');

await ctx.close();
