import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-msg2');

async function hoverClick(locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 });
  await page.waitForTimeout(250);
  await locator.click({ force: false });
}

// 进入工作区
await page.goto('http://localhost:3000/en', { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 4000);
await hoverClick(page.getByText('Smart Factory', { exact: true }).first());
await wait(page, 5000);
await hoverClick(page.getByText('Messages', { exact: true }).first());
await wait(page, 5000);

// 切到 telemetry
await hoverClick(page.locator('button').filter({ hasText: /environment|telemetry/ }).first());
await wait(page, 2000);
await hoverClick(page.getByText('telemetry', { exact: true }).first());
await wait(page, 4000);
await shot(page, 'diag-msg2-telemetry');

// 打开 Send Message
await page.getByRole('button', { name: 'Send Message', exact: true }).first().click();
await wait(page, 3000);
await shot(page, 'diag-msg2-modal');

// 打开 Publisher 下拉
await hoverClick(page.getByText('Select a device', { exact: true }).first());
await wait(page, 2500);
await shot(page, 'diag-msg2-pubdrop');

const items = await page.evaluate(() => Array.from(document.querySelectorAll('li, [role="option"], div')).map(e => e.innerText.trim()).filter(Boolean).slice(0, 20));
console.log('下拉项:', JSON.stringify(items));

await ctx.close();
console.log('DIAG 完成');
