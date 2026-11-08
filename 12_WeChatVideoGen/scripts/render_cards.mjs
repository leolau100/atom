import { chromium } from 'playwright-core';
import { mkdirSync } from 'fs';

const OUT = process.env.CARDS_OUT || '/Users/liulei/Workbuddy/2026-09-03-21-25-37/magistrala-demo/cards';
mkdirSync(OUT, { recursive: true });

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const cards = [
  {
    key: 'intro',
    bg: 'linear-gradient(135deg, #020617 0%, #0f172a 100%)',
    title: 'Magistrala 开源物联网平台',
    subtitle: '6 分钟快速上手指南',
    footer: '登录 · 工作区 · 设备 · 通道 · 连接 · 发消息',
    titleSize: 76,
    subColor: '#38bdf8',
  },
  { key: 't1', bg: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', title: '01 登录 Magistrala 平台', subtitle: '访问本地部署的 Magistrala, 使用管理员账号进入控制台' },
  { key: 't2', bg: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', title: '02 新建 Smart Factory 工作区', subtitle: '在工作区模块创建名为 Smart Factory 的工作空间' },
  { key: 't3', bg: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', title: '03 添加温度传感器设备', subtitle: '创建设备 Temp Sensor 01 并查看连接凭证' },
  { key: 't4', bg: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', title: '04 创建 telemetry 数据通道', subtitle: '新建 telemetry 通道用于接收设备遥测消息' },
  { key: 't5', bg: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', title: '05 连接设备到通道', subtitle: '将 Temp Sensor 01 订阅至 telemetry 通道' },
  { key: 't6', bg: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', title: '06 发送遥测消息', subtitle: '通过消息页面向通道发送 temperature=26.5' },
  {
    key: 'outro',
    bg: 'linear-gradient(135deg, #0f172a 0%, #020617 100%)',
    title: '演示结束',
    subtitle: 'Magistrala 提供设备管理、消息总线与规则引擎, 是构建 IoT 平台的完整开源方案。',
  },
];

const fontStack = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif';

function html(c) {
  const footer = c.footer
    ? `<div style="position:absolute;bottom:80px;width:100%;text-align:center;font-size:30px;color:#94a3b8;">${c.footer}</div>`
    : '';
  const subColor = c.subColor || '#94a3b8';
  const titleSize = c.titleSize || 68;
  return `<!doctype html><html><head><meta charset="utf-8"><style>
    *{margin:0;padding:0;box-sizing:border-box;}
    html,body{width:1600px;height:1000px;}
    body{font-family:${fontStack};background:${c.bg};display:flex;align-items:center;justify-content:center;}
    .wrap{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:28px;width:100%;max-width:1400px;padding:40px;}
    .title{font-size:${titleSize}px;font-weight:800;line-height:1.2;color:#f8fafc;}
    .sub{font-size:34px;color:${subColor};line-height:1.5;max-width:1100px;}
  </style></head><body><div class="wrap"><div class="title">${c.title}</div><div class="sub">${c.subtitle}</div></div>${footer}</body></html>`;
}

const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });

for (const c of cards) {
  await page.setContent(html(c), { waitUntil: 'networkidle' });
  await page.waitForTimeout(150);
  await page.screenshot({ path: `${OUT}/${c.key}.png` });
  console.log('rendered', c.key);
}
await browser.close();
console.log('ALL CARDS DONE');
