import time, json, re
from playwright.sync_api import sync_playwright

PROFILE = "/Users/liulei/Product/01_PubWechatFile/.publish_profile"
LOG = open("/tmp/diag_card.log", "w", encoding="utf-8")
def log(*a):
    s=" ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE, headless=False, channel="chrome",
        args=["--no-sandbox","--disable-setuid-sandbox"])
    page = ctx.new_page()
    page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    tok = re.search(r"token=(\d+)", page.url); tok = tok.group(1) if tok else ""
    page.goto(f"https://mp.weixin.qq.com/cgi-bin/appmsg?begin=0&count=20&type=77&action=list_card&token={tok}&lang=zh_CN", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    cards = page.evaluate("""() => [...document.querySelectorAll('.weui-desktop-card')].map(c=>(c.innerText.split('\\n')[0]||'').trim().slice(0,80))""")
    log("CARDS: "+json.dumps(cards, ensure_ascii=False))
    # target Magistrala (the long one)
    idx = next((i for i,c in enumerate(cards) if "从零搭云原生" in c), None)
    log("target idx="+str(idx))
    if idx is None: ctx.close(); raise SystemExit
    # hover then dump icon buttons outerHTML
    card = page.locator('.weui-desktop-card').nth(idx)
    card.hover(); page.wait_for_timeout(1200)
    html = card.evaluate("""c => {
        const as=[...c.querySelectorAll('a,button')];
        return as.map(a=>a.outerHTML.slice(0,160));
    }""")
    for i,h in enumerate(html):
        log(f"  ICON[{i}] {h}")
    # also try: click each icon-btn-like and see if editor opens
    ctx.close()
    log("[DONE]")
