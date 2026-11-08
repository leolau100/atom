import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-send');

async function hoverClick(locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 });
  await page.waitForTimeout(250);
  await locator.click({ force: false });
}

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages?channel=${CH}`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 5000);
await shot(page, 'diag-send-page');

await page.getByRole('button', { name: 'Send Message', exact: true }).first().click();
await wait(page, 3000);
await shot(page, 'diag-send-modal');

// 只填 name/value，不选 publisher
await page.fill('input[name="name"]', 'temperature');
await wait(page, 400);
await page.fill('input[name="value"]', '26.5');
await wait(page, 400);
await shot(page, 'diag-send-filled');

// 记录所有按钮信息
const btns = await page.evaluate(() => Array.from(document.querySelectorAll('button')).map(b => ({
  text: b.innerText.trim(),
  type: b.type,
  disabled: b.disabled,
  ariaDisabled: b.getAttribute('aria-disabled'),
  rect: b.getBoundingClientRect ? { x: b.getBoundingClientRect().x, y: b.getBoundingClientRect().y, w: b.getBoundingClientRect().width, h: b.getBoundingClientRect().height } : null
})));
console.log('buttons:', JSON.stringify(btns, null, 2));

// 尝试点击 Send
try {
  const send = page.getByRole('button', { name: 'Send', exact: true }).last();
  await send.click({ timeout: 10000 });
  console.log('Send clicked');
  await wait(page, 5000);
  await shot(page, 'diag-send-after');
} catch (e) {
  console.log('Send error:', e.message.slice(0, 200));
}

await ctx.close();
