import { rec, shot, type, clickText, wait, WS } from './lib.mjs';

const { ctx, page } = await rec('03-device');

await page.goto(`http://localhost:3000/en/workspace/${WS}/devices`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 4500);
await shot(page, '09-设备列表');

await clickText(page, 'Create');
await wait(page, 2500);
await type(page, 'input[name="name"]', 'Temp Sensor 02');
await wait(page, 400);
await type(page, 'input[name="key"]', 'temp-sensor-02');
await wait(page, 400);
await type(page, 'input[name="serial"]', 'SN-TS-0002');
await wait(page, 1200);
await shot(page, '10-新建设备表单');

await clickText(page, 'Create', true);
await wait(page, 6000);
await shot(page, '11-设备创建成功');

// 查看设备凭证
const card = page.locator('text=Temp Sensor 02').first();
if (await card.count()) {
  const box = await card.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 12 });
  await card.click();
  await page.waitForTimeout(6000);
  await shot(page, '12-设备详情凭证');
}

await ctx.close();
console.log('片段 03 完成');
