import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-cli');

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages?channel=${CH}`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 5000);
await page.getByRole('button', { name: 'Send Message', exact: true }).first().click();
await wait(page, 3000);
await page.fill('input[name="name"]', 'temperature');
await page.fill('input[name="value"]', '26.5');
await wait(page, 500);

// 点 Use CLI tools
await page.getByText('Use CLI tools', { exact: true }).first().click();
await wait(page, 3000);
await shot(page, 'diag-cli-tab');

const text = await page.evaluate(() => document.body.innerText.replace(/\n+/g, ' | ').slice(800, 1800));
console.log('CLI text:', text);

await ctx.close();
