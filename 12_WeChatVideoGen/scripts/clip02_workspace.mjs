import { rec, shot, type, wait, WS } from './lib.mjs';

const { ctx, page } = await rec('02-workspace');

async function clickBtn(role, name, which = 'first') {
  const btns = page.getByRole('button', { name, exact: true });
  const el = which === 'first' ? btns.first() : btns.last();
  await el.scrollIntoViewIfNeeded();
  const box = await el.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 12 });
  await page.waitForTimeout(250);
  await el.click();
}

await page.goto('http://localhost:3000/en', { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 4500);
await shot(page, '05-工作区列表');

await clickBtn('button', 'Create', 'first');
await wait(page, 3000);
await shot(page, '05b-创建弹窗');

await type(page, 'input[name="name"]', 'Smart Building');
await wait(page, 500);
await type(page, 'input[name="route"]', 'smart-building');
await wait(page, 1200);
await shot(page, '06-新建工作区表单');

await clickBtn('button', 'Create', 'last');
await wait(page, 6500);
await shot(page, '07-工作区创建成功');

await page.goto(`http://localhost:3000/en/workspace/${WS}`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 5000);
await shot(page, '08-进入工作区总览');

await ctx.close();
console.log('片段 02 完成');
