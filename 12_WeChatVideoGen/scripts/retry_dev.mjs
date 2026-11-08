import { launch, shot } from './lib.mjs';
const WS = '617d9051-1366-4946-9dd8-416faba55a90';
const { ctx, page } = await launch();
for (let i = 1; i <= 3; i++) {
  await page.goto(`http://localhost:3000/en/workspace/${WS}/devices`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(6000);
  const t = await page.evaluate(() => document.body.innerText.slice(0, 200));
  console.log(`第${i}次:`, t.replace(/\n+/g, ' | ').slice(0, 160));
  if (!t.includes('Oops')) { await shot(page, 'x-devices-ok'); break; }
}
await ctx.close();
