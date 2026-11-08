import fs from 'node:fs';
import { rec, shot, type, clickText, wait, PROFILE } from './lib.mjs';

// 登录片段需要干净会话，清掉复用 profile（后续片段会复用登录态）
fs.rmSync(PROFILE, { recursive: true, force: true });

const { ctx, page } = await rec('01-login');

await page.goto('http://localhost:3000/en/login', { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 3000);
await shot(page, '01-登录页');

// 输入账号
await type(page, 'input[name="identity"]', 'demoadmin@magistrala.local');
await wait(page, 600);
await shot(page, '02-输入账号');

// 输入密码
await type(page, 'input[name="password"]', 'Demo1234!@#');
await wait(page, 800);
await shot(page, '03-输入密码');

// 登录
await clickText(page, 'Sign In');
await wait(page, 9000);
await shot(page, '04-登录后工作区列表');

await ctx.close();
console.log('片段 01 完成');
