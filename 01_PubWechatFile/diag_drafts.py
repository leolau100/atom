import time, json, sys
from playwright.sync_api import sync_playwright

PROFILE = "/Users/liulei/Product/01_PubWechatFile/.publish_profile"
LOG = open("/tmp/diag.log", "w", encoding="utf-8")
def log(*a):
    s=" ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

def main():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE, headless=False, channel="chrome",
            args=["--no-sandbox","--disable-setuid-sandbox"])
        page = ctx.new_page()
        page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        txt = page.evaluate("document.body.innerText")
        if "使用账号登录" in txt or "登录超时" in txt:
            log("[NEED LOGIN] 请扫码"); page.screenshot(path="/tmp/diag_login.png")
            ctx.close(); return
        log("[OK] logged in")
        # token
        m = __import__("re").search(r"token=(\d+)", page.url)
        tok = m.group(1) if m else ""
        # go to draft list
        page.goto(f"https://mp.weixin.qq.com/cgi-bin/appmsg?begin=0&count=20&type=77&action=list_card&token={tok}&lang=zh_CN", wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        # enumerate draft cards
        cards = page.evaluate("""() => {
            const out=[];
            document.querySelectorAll('.weui-desktop-card').forEach(c=>{
                const t=c.querySelector('.weui-desktop-card__title, .title, .appmsg_title')?.innerText||'';
                const u=c.querySelector('.weui-desktop-card__info, .time, .update_time')?.innerText||'';
                const title = c.innerText.split('\\n')[0]||'';
                out.push({title:title.trim().slice(0,60), info:u.trim().slice(0,40)});
            });
            return out;
        }""")
        log("[DRAFT CARDS] total=%d"%len(cards))
        for i,c in enumerate(cards):
            log(f"  [{i}] {c['title']} | {c['info']}")
        page.screenshot(path="/tmp/diag_draftlist.png")
        ctx.close()
        log("[DONE]")

main()
