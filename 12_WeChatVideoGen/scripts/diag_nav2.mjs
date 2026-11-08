import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-nav2');

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages?channel=${CH}`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 6000);
console.log('url:', page.url());
const text = await page.evaluate(() => document.body.innerText.replace(/\n+/g, ' | ').slice(0, 200));
console.log('TEXT:', text);
await shot(page, 'diag-nav2');

await ctx.close();
