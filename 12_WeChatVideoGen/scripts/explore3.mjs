import { launch, shot, dump } from './lib.mjs';

const { ctx, page } = await launch();
await page.goto('http://localhost:3000/en', { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(6000);

await page.getByRole('button', { name: 'Create' }).first().click();
await page.waitForTimeout(3000);
await shot(page, 'x-create-dialog');
const info = await page.evaluate(() => ({
  text: document.body.innerText.slice(0, 1200),
  inputs: Array.from(document.querySelectorAll('input,textarea')).map((i) => ({
    name: i.getAttribute('name'), id: i.id, ph: i.getAttribute('placeholder'), tag: i.tagName,
  })),
  buttons: Array.from(document.querySelectorAll('button')).map((b) => b.innerText.trim().slice(0, 30)).filter(Boolean).slice(0, 25),
}));
console.log('TEXT:\n' + info.text);
console.log('\nINPUTS:', JSON.stringify(info.inputs, null, 1));
console.log('\nBUTTONS:', JSON.stringify(info.buttons));
await ctx.close();
