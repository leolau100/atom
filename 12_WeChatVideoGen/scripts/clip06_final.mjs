import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('06-final');

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages?channel=${CH}`, {
  waitUntil: 'networkidle',
  timeout: 60000,
});
await wait(page, 5000);
await shot(page, '21-消息页');

// 打开发送弹窗
await page.getByRole('button', { name: 'Send Message', exact: true }).first().click();
await wait(page, 3000);
await shot(page, '22-发送消息弹窗');

// 填写遥测数据
await page.fill('input[name="name"]', 'temperature');
await wait(page, 600);
await page.fill('input[name="value"]', '26.5');
await wait(page, 600);
await shot(page, '23-填写遥测数据');

// 提交
await page.getByRole('button', { name: 'Send', exact: true }).last().click();
await wait(page, 10000);
await shot(page, '24-消息已发送');

// 再等多几秒,让消息列表刷新出来
await wait(page, 5000);
await shot(page, '25-消息列表');

await ctx.close();
console.log('片段 06-final 完成');
