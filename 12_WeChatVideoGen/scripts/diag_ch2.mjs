import { rec, shot, wait, WS } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-ch2');

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 4500);
await shot(page, 'diag-ch2-page');

// 尝试多种方式打开 Channel 下拉
const attempts = [
  () => page.getByText('Channel:', { exact: false }).first(),
  () => page.locator('button').filter({ hasText: /environment/ }).first(),
  () => page.locator('text=environment').first(),
];

for (let i = 0; i < attempts.length; i++) {
  const loc = attempts[i]();
  const vis = await loc.isVisible().catch(() => false);
  console.log(`attempt ${i}: visible=${vis}`);
  if (vis) {
    const box = await loc.boundingBox();
    console.log('box:', JSON.stringify(box));
    await loc.click();
    await wait(page, 2000);
    await shot(page, `diag-ch2-drop-${i}`);
    const items = await page.evaluate(() => Array.from(document.querySelectorAll('li, [role="option"], div')).map(e => e.innerText.trim()).filter(t => /telemetry|environment|Channel/.test(t)).slice(0, 15));
    console.log('items:', JSON.stringify(items));
  }
}

await ctx.close();
console.log('DIAG 完成');
