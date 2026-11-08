import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-enter');

page.on('console', msg => console.log('CONSOLE:', msg.type(), msg.text()));
page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages?channel=${CH}`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 5000);
await page.getByRole('button', { name: 'Send Message', exact: true }).first().click();
await wait(page, 3000);
await page.fill('input[name="name"]', 'temperature');
await page.fill('input[name="value"]', '26.5');
await wait(page, 500);

// 在 value 字段按 Enter 提交
await page.locator('input[name="value"]').press('Enter');
await wait(page, 5000);
await shot(page, 'diag-enter-after');

await ctx.close();
