const puppeteer = require('puppeteer-core');
const fs = require('fs');

// usage: node shot_core.js <url> <outpng> [clipTopPx] [clipHeightPx]
(async () => {
  const url = process.argv[2];
  const out = process.argv[3];
  const clipTop = parseInt(process.argv[4] || '0', 10);
  const clipH = parseInt(process.argv[5] || '0', 10);
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox','--disable-setuid-sandbox','--enable-unsafe-swiftshader','--disable-dev-shm-usage']
  });
  const page = await browser.newPage();
  await page.setViewport({width: 1100, height: 900, deviceScaleFactor: 1});
  await page.goto(url, {waitUntil: 'networkidle2', timeout: 60000}).catch(e=>console.error('goto warn', e.message));
  await new Promise(r=>setTimeout(r, 2500));
  let buf;
  if (clipH > 0) {
    buf = await page.screenshot({clip: {x:0, y:clipTop, width:1100, height:clipH}});
  } else {
    buf = await page.screenshot({fullPage: true});
  }
  fs.writeFileSync(out, buf);
  console.log('saved', out, buf.length);
  await browser.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1);});
