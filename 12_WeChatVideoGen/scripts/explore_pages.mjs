import { launch, shot, dump } from './lib.mjs';

const WS = '617d9051-1366-4946-9dd8-416faba55a90';
const { ctx, page } = await launch();

async function look(path, label, clickCreate = true) {
  await page.goto(`http://localhost:3000/en/workspace/${WS}/${path}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(6000);
  await shot(page, `x-${label}`);
  const info = await page.evaluate(() => ({
    text: document.body.innerText.slice(0, 900),
    inputs: Array.from(document.querySelectorAll('input,textarea')).map((i) => i.getAttribute('name') || i.getAttribute('placeholder')).filter(Boolean).slice(0, 15),
    buttons: Array.from(document.querySelectorAll('button')).map((b) => b.innerText.trim().slice(0, 25)).filter(Boolean).slice(0, 25),
  }));
  console.log(`\n########## ${label} (/${path})`);
  console.log('TEXT:', info.text.replace(/\n+/g, ' | ').slice(0, 500));
  console.log('INPUTS:', JSON.stringify(info.inputs));
  console.log('BUTTONS:', JSON.stringify(info.buttons));

  if (clickCreate) {
    const btn = page.getByRole('button', { name: /^Create/ }).first();
    if (await btn.count()) {
      await btn.click();
      await page.waitForTimeout(3000);
      await shot(page, `x-${label}-create`);
      const f = await page.evaluate(() => ({
        text: document.body.innerText.slice(0, 900),
        inputs: Array.from(document.querySelectorAll('input,textarea')).map((i) => ({
          name: i.getAttribute('name'), ph: i.getAttribute('placeholder'), tag: i.tagName,
        })),
        buttons: Array.from(document.querySelectorAll('button')).map((b) => b.innerText.trim().slice(0, 25)).filter(Boolean).slice(0, 25),
      }));
      console.log(`--- ${label} 创建表单:`);
      console.log('TEXT:', f.text.replace(/\n+/g, ' | ').slice(0, 400));
      console.log('INPUTS:', JSON.stringify(f.inputs));
      console.log('BUTTONS:', JSON.stringify(f.buttons));
    }
  }
}

await look('devices', 'devices');
await look('channels', 'channels');
await look('messages', 'messages', false);
await look('dashboards', 'dashboards');
await ctx.close();
