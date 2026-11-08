import { launch, shot, dump } from './lib.mjs';

const { ctx, page } = await launch();
await page.goto('http://localhost:3000/en', { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(6000);

// 打开创建工作区
await page.getByRole('button', { name: 'Create' }).first().click();
await page.waitForTimeout(2500);
await page.fill('input[name="name"]', 'Smart Factory');
await page.fill('input[name="route"]', 'smart-factory');
await page.waitForTimeout(800);
await shot(page, 'x-ws-form');
await page.getByRole('button', { name: 'Create', exact: true }).last().click();
await page.waitForTimeout(6000);
await shot(page, 'x-ws-created');
await dump(page, '创建工作区后');

// 点进工作区
const card = page.locator('text=Smart Factory').first();
if (await card.count()) {
  await card.click();
  await page.waitForTimeout(8000);
}
await shot(page, 'x-ws-detail');
const info = await page.evaluate(() => ({
  text: document.body.innerText.slice(0, 1500),
  links: Array.from(document.querySelectorAll('a')).map((a) => a.getAttribute('href')).filter(Boolean).slice(0, 30),
  buttons: Array.from(document.querySelectorAll('button')).map((b) => b.innerText.trim().slice(0, 30)).filter(Boolean).slice(0, 40),
}));
console.log('TEXT:\n' + info.text);
console.log('\nLINKS:', JSON.stringify(info.links));
console.log('\nBUTTONS:', JSON.stringify(info.buttons));
await ctx.close();
