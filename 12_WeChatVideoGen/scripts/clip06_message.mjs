import { rec, shot, type, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('06-message');

async function hoverClick(locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 });
  await page.waitForTimeout(250);
  await locator.click({ force: false });
}

async function sendMessage({ name, value, shotBefore }) {
  await page.getByRole('button', { name: 'Send Message', exact: true }).first().click();
  await wait(page, 3000);
  await shot(page, shotBefore);

  await page.fill('input[name="name"]', name);
  await wait(page, 400);

  await page.fill('input[name="value"]', value);
  await wait(page, 400);
  await shot(page, shotBefore.replace('弹窗', '数据'));

  await page.getByRole('button', { name: 'Send', exact: true }).last().click();
  await wait(page, 7000);
}

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages?channel=${CH}`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 5000);
console.log('messages url:', page.url());
await shot(page, '21-消息页');

await sendMessage({ name: 'temperature', value: '26.5', shotBefore: '22-发送消息弹窗' });
await shot(page, '24-消息已发送');

await sendMessage({ name: 'humidity', value: '61.2', shotBefore: '25-再发弹窗' });
await shot(page, '26-消息列表两条');

await ctx.close();
console.log('片段 06 完成');
