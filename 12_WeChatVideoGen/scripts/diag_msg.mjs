import { rec, shot, wait, WS } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-msg');

async function snap(label) {
  const info = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(Boolean);
    const overlays = document.querySelectorAll('[data-state="open"]').length;
    const inputs = Array.from(document.querySelectorAll('input')).map(i => ({ name: i.getAttribute('name'), ph: i.getAttribute('placeholder'), type: i.type }));
    const text = document.body.innerText.replace(/\n+/g, ' | ').slice(0, 500);
    return { btns: btns.slice(0, 25), overlays, inputs: inputs.slice(0, 12), text };
  });
  console.log(`\n### ${label}`);
  console.log('overlays:', info.overlays);
  console.log('buttons:', JSON.stringify(info.btns));
  console.log('inputs:', JSON.stringify(info.inputs));
  console.log('text:', info.text);
  await shot(page, 'diagmsg-' + label);
}

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 4500);
await snap('1-messages');

// 点击 Send Message
await page.getByText('Send Message', { exact: true }).first().click();
await wait(page, 3000);
await snap('2-modal');

await ctx.close();
console.log('DIAG 完成');
