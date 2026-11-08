import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-unit');

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages?channel=${CH}`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 5000);
await page.getByRole('button', { name: 'Send Message', exact: true }).first().click();
await wait(page, 3000);

// 打开 Unit 下拉
await page.getByText('Select a Unit', { exact: true }).first().click();
await wait(page, 2000);
await shot(page, 'diag-unit-drop');

const items = await page.evaluate(() => Array.from(document.querySelectorAll('li, [role="option"], div')).map(e => e.innerText.trim()).filter(t => /celsius|percent|°C|unit|kelvin|fahrenheit/i.test(t)).slice(0, 10));
console.log('unit items:', JSON.stringify(items));

await ctx.close();
