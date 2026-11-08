import { launch, shot } from './lib.mjs';

const WS = '617d9051-1366-4946-9dd8-416faba55a90';
const CH = 'b0919a3a-f7d4-477b-82cc-ddc9dfaab74e';
const { ctx, page } = await launch();

async function go(url) {
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(4000);
}
const info = () => page.evaluate(() => ({
  text: document.body.innerText.slice(0, 700).replace(/\n+/g, ' | '),
  inputs: Array.from(document.querySelectorAll('input,textarea')).map((i) => ({ name: i.getAttribute('name'), ph: i.getAttribute('placeholder'), tag: i.tagName })).slice(0, 12),
  buttons: Array.from(document.querySelectorAll('button')).map((b) => b.innerText.trim().slice(0, 25)).filter(Boolean).slice(0, 30),
}));

// 通道详情（连接管理）
await go(`http://localhost:3000/en/workspace/${WS}/channels/${CH}`);
await shot(page, 'x-ch-detail2');
const d = await info();
console.log('通道详情 TEXT:', d.text);
console.log('通道详情 BUTTONS:', JSON.stringify(d.buttons));

// 消息：发送弹窗
await go(`http://localhost:3000/en/workspace/${WS}/messages`);
await page.getByRole('button', { name: 'Send Message' }).first().click();
await page.waitForTimeout(3000);
await shot(page, 'x-send-dialog');
const s = await info();
console.log('\n发送弹窗 TEXT:', s.text);
console.log('发送弹窗 INPUTS:', JSON.stringify(s.inputs));
console.log('发送弹窗 BUTTONS:', JSON.stringify(s.buttons));

await ctx.close();
