import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('zz-diag');

async function snap(label) {
  const info = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(Boolean);
    const overlays = document.querySelectorAll('[data-state="open"]').length;
    const inputs = Array.from(document.querySelectorAll('input')).map(i => ({ name: i.getAttribute('name'), ph: i.getAttribute('placeholder'), type: i.type }));
    const bodyText = document.body.innerText.replace(/\n+/g, ' | ').slice(0, 400);
    return { btns: btns.slice(0, 25), overlays, inputs: inputs.slice(0, 12), bodyText };
  });
  console.log(`\n### ${label}`);
  console.log('overlays(open):', info.overlays);
  console.log('buttons:', JSON.stringify(info.btns));
  console.log('inputs:', JSON.stringify(info.inputs));
  console.log('text:', info.bodyText);
  await shot(page, 'diag-' + label);
}

await page.goto(`http://localhost:3000/en/workspace/${WS}/channels/${CH}/connections`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 4500);
await snap('1-connections-page');

// 点击 Connect 打开弹窗
await page.getByText('Connect', { exact: true }).first().click();
await wait(page, 3500);
await snap('2-modal-open');

// 点击 Select device(s)
const sel = page.getByText('Select device(s)', { exact: true }).first();
await sel.scrollIntoViewIfNeeded();
await sel.click();
await wait(page, 2500);
await snap('3-dropdown-open');

await ctx.close();
console.log('DIAG 完成');
