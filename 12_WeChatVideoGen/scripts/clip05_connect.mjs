import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('05-connect');

async function hoverClick(locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 });
  await page.waitForTimeout(250);
  await locator.click({ force: false });
}

await page.goto(`http://localhost:3000/en/workspace/${WS}/channels/${CH}/connections`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 4500);
await shot(page, '16-通道连接页(空)');

// 打开 Connect Device(s) 弹窗
await page.getByRole('button', { name: 'Connect', exact: true }).first().click();
await wait(page, 3500);
await shot(page, '17-连接弹窗');

// 打开设备下拉
await hoverClick(page.getByText('Select device(s)', { exact: true }).first());
await wait(page, 2500);
await shot(page, '18-选择设备下拉');

// 选择 Temp Sensor 01（下拉项）
await hoverClick(page.getByText('Temp Sensor 01', { exact: true }).first());
await wait(page, 1500);

// 按 Esc 关闭下拉（multi-select 下拉不会自动关）
await page.keyboard.press('Escape');
await wait(page, 800);
await shot(page, '18b-设备已选');

// 勾选 Subscribe / Publish
for (const name of ['Subscribe', 'Publish']) {
  await hoverClick(page.getByText(name, { exact: true }).last());
  await wait(page, 1200);
}
await shot(page, '19-连接配置完成');

// 点击弹窗底部 Connect 提交
await hoverClick(page.locator('button[type="submit"]').filter({ hasText: 'Connect' }).first());
await wait(page, 7000);
await shot(page, '20-设备已连接通道');

await ctx.close();
console.log('片段 05 完成');
