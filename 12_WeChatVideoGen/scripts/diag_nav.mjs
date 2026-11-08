import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-nav');

for (const path of [
  `/en/workspace/${WS}/messages`,
  `/en/workspace/${WS}/messages?channel=${CH}`,
  `/en/workspace/${WS}/channels/${CH}/connections`,
]) {
  await page.goto(`http://localhost:3000${path}`, { waitUntil: 'networkidle', timeout: 60000 });
  await wait(page, 5000);
  console.log(`\n${path} -> ${page.url()}`);
  const text = await page.evaluate(() => document.body.innerText.replace(/\n+/g, ' | ').slice(0, 180));
  console.log('TEXT:', text);
  await shot(page, 'nav-' + path.replace(/[^a-z0-9]/g, '_'));
}

await ctx.close();
