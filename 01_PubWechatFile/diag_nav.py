import time, re, json
from playwright.sync_api import sync_playwright

PROFILE = "/Users/liulei/Product/01_PubWechatFile/.publish_profile"
LOG = open("/tmp/diag_nav.log", "w", encoding="utf-8")
def log(*a):
    s=" ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

def main():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE, headless=False, channel="chrome",
            args=["--no-sandbox","--disable-setuid-sandbox"])
        page = ctx.new_page()
        page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded")
        page.wait_for_timeout(7000)
        # 截图首页看左侧菜单
        page.screenshot(path="/tmp/nav_home.png")
        # 尝试点左侧「草稿箱」
        clicked = None
        for sel in ["text=草稿箱", "a:has-text('草稿箱')", "span:has-text('草稿箱')", "#menu_bar a:has-text('草稿箱')"]:
            try:
                page.locator(sel).first.click(timeout=4000)
                clicked = sel; break
            except Exception:
                continue
        log("[click 草稿箱] "+str(clicked))
        page.wait_for_timeout(6000)
        page.screenshot(path="/tmp/nav_draftlist.png")
        cards = page.evaluate("""() => {
            const out=[];
            document.querySelectorAll('.weui-desktop-card').forEach((c,i)=>{
                out.push({i, text:c.innerText.split('\\n').slice(0,3).join(' | ').trim().slice(0,80)});
            });
            return out;
        }""")
        log("[CARDS] "+json.dumps(cards, ensure_ascii=False))
        # dump sidebar text
        sb = page.evaluate("""() => {
            const els=[...document.querySelectorAll('a,span,div')].filter(e=>/草稿箱|图文|视频|内容与互动|首页/.test(e.textContent)&&e.children.length<=1);
            return els.slice(0,20).map(e=>e.textContent.trim().slice(0,20));
        }""")
        log("[SIDEBAR ITEMS] "+json.dumps(sb, ensure_ascii=False))
        ctx.close(); log("[DONE]")

main()
