import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-ch');

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages?channel=${CH}`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 4500);
const text = await page.evaluate(() => document.body.innerText.replace(/\n+/g, ' | ').slice(0, 300));
console.log('URL query channel TEXT:', text);
await shot(page, 'diag-ch-url');

// 尝试点击 Channel 下拉
const ch = page.getByText('Channel:', { exact: false }).first();
if (await ch.isVisible().catch(() => false)) {
  await ch.click();
  await wait(page, 1500);
  await shot(page, 'diag-ch-dropdown');
  const items = await page.evaluate(() => Array.from(document.querySelectorAll('li, [role="option"], div')).map(e => e.innerText.trim()).filter(t => /telemetry|environment/.test(t)).slice(0, 10));
  console.log('channel items:', JSON.stringify(items));
}

await ctx.close();
console.log('DIAG 完成');
