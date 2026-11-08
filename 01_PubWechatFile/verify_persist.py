import time, json, re
from playwright.sync_api import sync_playwright

PROFILE = "/Users/liulei/Product/01_PubWechatFile/.publish_profile"
LOG = open("/tmp/verify.log", "w", encoding="utf-8")
def log(*a):
    s=" ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

def stat(page):
    try:
        page.wait_for_selector("div.ProseMirror", timeout=25000)
    except Exception as e:
        log("[WARN] ProseMirror not found:", str(e)[:80]); page.screenshot(path="/tmp/verify_editor.png")
        return None
    page.wait_for_timeout(5000)
    s = page.evaluate("""() => {
        const ps=document.querySelectorAll('div.ProseMirror');
        const el=ps[ps.length-1];
        if(!el) return {err:'no ProseMirror'};
        const imgs=[...el.querySelectorAll('img')];
        return {
            total_imgs: imgs.length,
            mmbiz: imgs.filter(i=>(i.getAttribute('src')||'').includes('mmbiz')).length,
            empty_src: imgs.filter(i=>!(i.getAttribute('src')||'').trim()).length,
            h2: el.querySelectorAll('h2,h1,h3').length,
            has_footer: el.innerText.includes('往期推荐')||el.innerText.includes('关于作者'),
            sample: imgs.slice(0,3).map(i=>(i.getAttribute('src')||'').slice(0,45)),
            url: location.href.slice(0,90)
        };
    }""")
    log("[EDITOR STATS] "+json.dumps(s, ensure_ascii=False))
    page.screenshot(path="/tmp/verify_editor.png")
    return s

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE, headless=False, channel="chrome",
        args=["--no-sandbox","--disable-setuid-sandbox"])
    page = ctx.new_page()
    page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    if "使用账号登录" in page.evaluate("document.body.innerText"):
        log("[NEED LOGIN]"); ctx.close(); raise SystemExit
    log("[OK] logged in")
    tok = re.search(r"token=(\d+)", page.url); tok = tok.group(1) if tok else ""
    page.goto(f"https://mp.weixin.qq.com/cgi-bin/appmsg?begin=0&count=20&type=77&action=list_card&token={tok}&lang=zh_CN", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    cards = page.evaluate("""() => [...document.querySelectorAll('.weui-desktop-card')].map(c=>(c.innerText.split('\\n')[0]||'').trim().slice(0,80))""")
    log("CARDS: "+json.dumps(cards, ensure_ascii=False))
    # target by text
    target = page.locator('.weui-desktop-card', has_text="从零搭云原生").first
    target.hover(); page.wait_for_timeout(1500)
    # 编辑图标是卡片内第 2 个 weui-desktop-icon-btn（截图确认：删除/编辑/发表）
    target.locator("a.weui-desktop-icon-btn").nth(1).click(timeout=8000)
    log("[click] edit icon nth(1)")
    page.wait_for_timeout(3000)
    log("[url] "+page.url[:120])
    stat(page)
    ctx.close()
    log("[DONE]")