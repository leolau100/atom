import { rec, shot, wait, WS, CH } from './lib.mjs';

const { ctx, page } = await rec('zz-diag-send3');

const requests = [];
page.on('request', req => {
  if (req.url().includes('messages') || req.url().includes('msg') || req.method() !== 'GET') {
    requests.push({ method: req.method(), url: req.url().slice(0, 120) });
  }
});
page.on('response', res => {
  if (res.url().includes('messages') || res.url().includes('msg') || res.request().method() !== 'GET') {
    console.log('RESP:', res.status(), res.request().method(), res.url().slice(0, 120));
  }
});

await page.goto(`http://localhost:3000/en/workspace/${WS}/messages?channel=${CH}`, { waitUntil: 'networkidle', timeout: 60000 });
await wait(page, 5000);
await page.getByRole('button', { name: 'Send Message', exact: true }).first().click();
await wait(page, 3000);
await page.fill('input[name="name"]', 'temperature');
await page.fill('input[name="value"]', '26.5');
await wait(page, 400);

console.log('REQ before send:', JSON.stringify(requests));
await page.getByRole('button', { name: 'Send', exact: true }).last().click();
await wait(page, 5000);
console.log('REQ after send:', JSON.stringify(requests));

await ctx.close();
