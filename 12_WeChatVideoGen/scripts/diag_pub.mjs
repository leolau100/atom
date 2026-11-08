import { rec, shot, wait, WS } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-pub');

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 4500);
await page.getByRole('button', { name: 'Send Message', exact: true }).first().click();
await wait(page, 3000);
await shot(page, 'diag-pub-modal');

// 打开 Publisher 下拉
const sel = page.getByText('Select a device', { exact: true }).first();
await sel.scrollIntoViewIfNeeded();
await sel.click();
await wait(page, 2500);
await shot(page, 'diag-pub-dropdown');

const info = await page.evaluate(() => {
  const items = Array.from(document.querySelectorAll('li, [role="option"], div')).map(e => e.innerText.trim()).filter(Boolean);
  const roles = Array.from(document.querySelectorAll('[role="option"]')).map(e => e.innerText.trim()).filter(Boolean);
  return { items: items.slice(0, 20), roles };
});
console.log('下拉文本项:', JSON.stringify(info.items));
console.log('role=option:', JSON.stringify(info.roles));

await ctx.close();
console.log('DIAG 完成');
