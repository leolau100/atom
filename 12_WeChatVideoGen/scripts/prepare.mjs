import { launch, shot, dump } from './lib.mjs';

const WS = '617d9051-1366-4946-9dd8-416faba55a90';
const { ctx, page } = await launch();

async function go(path) {
  await page.goto(`http://localhost:3000/en/workspace/${WS}/${path}`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(4000);
}

// 建设备
await go('devices');
const devBtn = page.getByRole('button', { name: /^Create/ }).first();
await devBtn.click();
await page.waitForTimeout(2500);
const f = await page.evaluate(() => ({
  inputs: Array.from(document.querySelectorAll('input,textarea')).map((i) => ({ name: i.getAttribute('name'), ph: i.getAttribute('placeholder'), tag: i.tagName })),
  buttons: Array.from(document.querySelectorAll('button')).map((b) => b.innerText.trim().slice(0, 25)).filter(Boolean).slice(0, 20),
}));
console.log('设备表单 INPUTS:', JSON.stringify(f.inputs));
console.log('设备表单 BUTTONS:', JSON.stringify(f.buttons));
await shot(page, 'x-dev-create');

const nameInput = page.locator('input[name="name"]').last();
await nameInput.fill('Temp Sensor 01');
const idInput = page.locator('input[name="identity"], input[name="key"]').last();
if (await idInput.count()) await idInput.fill('temp-sensor-01');
await page.waitForTimeout(800);
await shot(page, 'x-dev-filled');
await page.getByRole('button', { name: 'Create', exact: true }).last().click();
await page.waitForTimeout(5000);
await shot(page, 'x-dev-list');

// 建通道
await go('channels');
await page.getByRole('button', { name: /^Create/ }).first().click();
await page.waitForTimeout(2500);
await page.locator('input[name="name"]').last().fill('telemetry');
await page.locator('input[name="route"]').last().fill('telemetry');
await page.waitForTimeout(800);
await shot(page, 'x-ch-filled');
await page.getByRole('button', { name: 'Create', exact: true }).last().click();
await page.waitForTimeout(5000);
await shot(page, 'x-ch-list');

// 点进通道看连接页
const chLink = page.locator('text=telemetry').first();
if (await chLink.count()) { await chLink.click(); await page.waitForTimeout(6000); }
await shot(page, 'x-ch-detail');
console.log('\n通道详情:', (await page.evaluate(() => document.body.innerText.slice(0, 800))).replace(/\n+/g, ' | '));
console.log('通道页 BUTTONS:', JSON.stringify(await page.evaluate(() => Array.from(document.querySelectorAll('button')).map((b) => b.innerText.trim().slice(0, 25)).filter(Boolean).slice(0, 30))));

// 消息页
await go('messages');
await shot(page, 'x-messages2');
console.log('\n消息页:', (await page.evaluate(() => document.body.innerText.slice(0, 800))).replace(/\n+/g, ' | '));
console.log('消息页 INPUTS:', JSON.stringify(await page.evaluate(() => Array.from(document.querySelectorAll('input,textarea')).map((i) => ({ name: i.getAttribute('name'), ph: i.getAttribute('placeholder'), tag: i.tagName })).slice(0, 12))));
console.log('消息页 BUTTONS:', JSON.stringify(await page.evaluate(() => Array.from(document.querySelectorAll('button')).map((b) => b.innerText.trim().slice(0, 25)).filter(Boolean).slice(0, 25))));

await ctx.close();
