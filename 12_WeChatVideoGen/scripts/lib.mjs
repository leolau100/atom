import { chromium } from 'playwright-core';
import fs from 'node:fs';

const ROOT = '/Users/liulei/Workbuddy/2026-09-03-21-25-37/magistrala-demo';
export const SHOTS = `${ROOT}/shots`;
export const VIDEO_DIR = `${ROOT}/videos`;
export const PROFILE = `${ROOT}/automation/.profile`;
export const WS = '617d9051-1366-4946-9dd8-416faba55a90';
export const CH = 'b0919a3a-f7d4-477b-82cc-ddc9dfaab74e';

fs.mkdirSync(SHOTS, { recursive: true });
fs.mkdirSync(VIDEO_DIR, { recursive: true });

/** 带录屏的持久化上下文 */
export async function rec(clip) {
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    channel: 'chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
    viewport: { width: 1600, height: 1000 },
    recordVideo: { dir: `${VIDEO_DIR}/raw-${clip}`, size: { width: 1600, height: 1000 } },
  });
  const page = ctx.pages()[0] || (await ctx.newPage());
  return { ctx, page };
}

export async function shot(page, name) {
  await page.screenshot({ path: `${SHOTS}/${name}.png` });
  console.log('  [截图]', name, '|', page.url().replace('http://localhost:3000', ''));
}

/** 慢速输入，录屏里能看到逐字输入 */
export async function type(page, sel, text) {
  const el = page.locator(sel).last();
  await el.click();
  await page.waitForTimeout(300);
  await el.pressSequentially(text, { delay: 90 });
}

/** 鼠标先移动再点击，录屏有指针轨迹 */
export async function click(page, sel, opts = {}) {
  const el = page.locator(sel).first();
  await el.scrollIntoViewIfNeeded();
  const box = await el.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 12 });
  await page.waitForTimeout(200);
  await el.click(opts);
}

export async function clickText(page, text, exact = false) {
  const el = page.getByRole('button', { name: text, exact }).last();
  const box = await el.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 12 });
  await page.waitForTimeout(250);
  await el.click();
}

export async function go(page, path) {
  await page.goto(`http://localhost:3000${path}`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3500);
}

export const wait = (page, ms) => page.waitForTimeout(ms);
