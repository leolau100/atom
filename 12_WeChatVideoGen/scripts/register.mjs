import { launch, shot, dump } from './lib.mjs';

const { ctx, page } = await launch();

// 注册
await page.goto('http://localhost:3000/en/register', { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(3000);
await page.fill('input[name="first_name"]', 'Demo');
await page.fill('input[name="last_name"]', 'User');
await page.fill('input[name="username"]', 'demouser');
await page.fill('input[name="email"]', 'demo@magistrala.local');
await page.fill('input[name="password"]', 'Demo1234!@#');
await page.fill('input[name="confirmPassword"]', 'Demo1234!@#');
await page.waitForTimeout(500);
await shot(page, '01-register');
await page.click('button[type="submit"]');
await page.waitForTimeout(8000);
await shot(page, '02-after-register');
await dump(page, '注册后');

// 登录
await page.goto('http://localhost:3000/en/login', { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(3000);
await page.fill('input[name="identity"]', 'demo@magistrala.local');
await page.fill('input[name="password"]', '12345678');
await page.waitForTimeout(500);
await shot(page, '03-login');
await page.click('button[type="submit"]');
await page.waitForTimeout(10000);
await shot(page, '04-after-login');
await dump(page, '登录后');

await ctx.close();
