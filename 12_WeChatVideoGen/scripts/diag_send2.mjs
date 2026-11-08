import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-send2');

page.on('console', msg => console.log('CONSOLE:', msg.type(), msg.text()));
page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages?channel=${CH}`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 5000);
await page.getByRole('button', { name: 'Send Message', exact: true }).first().click();
await wait(page, 3000);
await page.fill('input[name="name"]', 'temperature');
await wait(page, 400);
await page.fill('input[name="value"]', '26.5');
await wait(page, 400);

// 尝试选 publisher
await page.getByText('Select a device', { exact: true }).first().click();
await wait(page, 1500);
await page.getByText('Temp Sensor 01', { exact: false }).first().click();
await wait(page, 1000);

await shot(page, 'diag-send2-filled');

await page.getByRole('button', { name: 'Send', exact: true }).last().click();
await wait(page, 5000);
await shot(page, 'diag-send2-after');

await ctx.close();
