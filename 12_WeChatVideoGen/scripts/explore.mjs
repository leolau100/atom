import { chromium } from 'playwright-core';

const OUT = '/Users/liulei/Workbuddy/2026-09-03-21-25-37/magistrala-demo/shots';
const args = process.argv.slice(2);
const url = args[0] || 'http://localhost:3000';
const name = args[1] || 'explore';

const browser = await chromium.launch({
  channel: 'chrome',
  headless: true,
  args: ['--no-sandbox'],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(4000);
await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false });
const text = await page.evaluate(() => document.body.innerText.slice(0, 1500));
const inputs = await page.evaluate(() =>
  Array.from(document.querySelectorAll('input,button,a')).slice(0, 40).map((e) => ({
    tag: e.tagName, type: e.type || '', id: e.id || '', name: e.name || '',
    ph: e.placeholder || '', text: (e.innerText || '').slice(0, 40),
  }))
);
console.log('=== URL:', page.url());
console.log('=== TEXT:\n' + text);
console.log('=== ELEMENTS:\n' + JSON.stringify(inputs, null, 1));
await browser.close();
