import { rec, shot, type, wait, WS } from './lib.mjs';

const { ctx, page } = await rec('04-channel');

async function clickBtn(name, which = 'first') {
  const btns = page.getByRole('button', { name, exact: true });
  const el = which === 'first' ? btns.first() : btns.last();
  await el.scrollIntoViewIfNeeded();
  const box = await el.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 12 });
  await page.waitForTimeout(250);
  await el.click();
}

await page.goto(`http://localhost:3000/en/workspace/${WS}/channels`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 4500);
await shot(page, '13-通道列表');

await clickBtn('Create');
await wait(page, 2800);
await type(page, 'input[name="name"]', 'environment');
await wait(page, 400);
await type(page, 'input[name="route"]', 'environment');
await wait(page, 1200);
await shot(page, '14-新建通道表单');

await clickBtn('Create', 'last');
await wait(page, 6000);
await shot(page, '15-通道创建成功');

await ctx.close();
console.log('片段 04 完成');
