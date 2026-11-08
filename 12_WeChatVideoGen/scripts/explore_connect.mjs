import { rec, shot, WS, CH, wait } from './lib.mjs';

const { ctx, page } = await rec('zz-test-conn');

await page.goto(`http://localhost:3000/en/workspace/${WS}/channels/${CH}`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 4500);
await page.getByRole('button', { name: 'Connections', exact: true }).first().click().catch(() => {});
await wait(page, 4000);
await shot(page, 't-conn-tab');
console.log('连接页 TEXT:', (await page.evaluate(() => document.body.innerText.slice(0, 600))).replace(/\n+/g, ' | '));
console.log('连接页 BUTTONS:', JSON.stringify(await page.evaluate(() => Array.from(document.querySelectorAll('button')).map((b) => b.innerText.trim().slice(0, 25)).filter(Boolean).slice(0, 30))));

// 点 Connect
const connBtn = page.getByRole('button', { name: /^Connect/ }).first();
if (await connBtn.count()) {
  await connBtn.click();
  await wait(page, 3500);
  await shot(page, 't-conn-modal');
  console.log('\n连接弹窗 TEXT:', (await page.evaluate(() => document.body.innerText.slice(0, 700))).replace(/\n+/g, ' | '));
  console.log('弹窗 INPUTS:', JSON.stringify(await page.evaluate(() => Array.from(document.querySelectorAll('input')).map((i) => ({ type: i.type, name: i.getAttribute('name'), ph: i.getAttribute('placeholder') })).slice(0, 15))));
  console.log('弹窗 BUTTONS:', JSON.stringify(await page.evaluate(() => Array.from(document.querySelectorAll('button')).map((b) => b.innerText.trim().slice(0, 25)).filter(Boolean).slice(0, 30))));
}
await ctx.close();
