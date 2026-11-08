import { launch, shot, dump } from './lib.mjs';

const { ctx, page } = await launch();
const mode = process.argv[2] || 'home';

if (mode === 'home') {
  await page.goto('http://localhost:3000/en', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(6000);
  await shot(page, 'x-home');
  const info = await page.evaluate(() => ({
    text: document.body.innerText.slice(0, 2000),
    links: Array.from(document.querySelectorAll('a')).map((a) => a.getAttribute('href')).filter(Boolean).slice(0, 30),
    buttons: Array.from(document.querySelectorAll('button')).map((b) => b.innerText.trim().slice(0, 30)).filter(Boolean).slice(0, 40),
    inputs: Array.from(document.querySelectorAll('input')).map((i) => ({ name: i.getAttribute('name'), ph: i.getAttribute('placeholder') })),
  }));
  console.log('TEXT:\n' + info.text);
  console.log('\nLINKS:', JSON.stringify(info.links));
  console.log('\nBUTTONS:', JSON.stringify(info.buttons));
  console.log('\nINPUTS:', JSON.stringify(info.inputs));
}

await ctx.close();
