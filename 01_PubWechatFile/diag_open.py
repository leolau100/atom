import time, re, json
from playwright.sync_api import sync_playwright

PROFILE = "/Users/liulei/Product/01_PubWechatFile/.publish_profile"
LOG = open("/tmp/diag3.log", "w", encoding="utf-8")
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
        m = re.search(r"token=(\d+)", page.url); tok = m.group(1) if m else ""
        page.goto(f"https://mp.weixin.qq.com/cgi-bin/appmsg?begin=0&count=20&type=77&action=list_card&token={tok}&lang=zh_CN", wait_until="domcontentloaded")
        cards = []
        for _ in range(20):
            page.wait_for_timeout(2000)
            cards = page.evaluate("""() => {
                const out=[];
                document.querySelectorAll('.weui-desktop-card').forEach((c,i)=>{
                    const t=c.innerText.split('\\n').slice(0,3).join(' | ').trim().slice(0,80);
                    out.push({i, text:t});
                });
                return out;
            }""")
            if cards:
                break
        log("[CARDS] "+json.dumps(cards, ensure_ascii=False))
        # find Magistrala card indices
        mags = [c['i'] for c in cards if 'Magistrala' in c['text']]
        log("[Magistrala card indices] "+json.dumps(mags))
        # open the LAST Magistrala card (newest saved)
        idx = mags[-1]
        card = page.locator(".weui-desktop-card").nth(idx)
        # hover then click the edit icon link
        card.scroll_into_view_if_needed(); card.hover(); time.sleep(1.5)
        clicked = card.evaluate("""el => {
            const tips = [...el.querySelectorAll('.weui-desktop-tooltip__wrp')];
            const wrap = tips.find(w => [...w.querySelectorAll('span')].some(s=>s.textContent.trim()==='编辑'));
            if (!wrap) return 'no_wrap';
            const link = wrap.querySelector('a, button') || wrap;
            link.click();
            return 'clicked '+(link.tagName+'.'+link.className).slice(0,50);
        }""")
        log("[EDIT] "+clicked)
        edit=None
        for _ in range(40):
            for pg in ctx.pages:
                try:
                    if pg.url and "appmsg_edit" in pg.url:
                        edit=pg; break
                    if pg.evaluate("() => !!document.querySelector('div.ProseMirror')"):
                        edit=pg; break
                except Exception: pass
            if edit: break
            time.sleep(1)
        if not edit:
            log("[WARN] no editor"); ctx.close(); return
        edit.wait_for_timeout(5000)
        edit.screenshot(path="/tmp/diag_new_draft.png", full_page=True)
        stats = edit.evaluate("""() => {
            const allPM=document.querySelectorAll('div.ProseMirror');
            const el=allPM[allPM.length-1]||document.body;
            const imgs=[...el.querySelectorAll('img')];
            const vis=imgs.filter(i=>{const b=i.getBoundingClientRect();return b.width>5&&b.height>5;});
            const realmm=imgs.filter(i=>i.getAttribute('src')&&i.getAttribute('src').includes('mmbiz'));
            const empt=imgs.filter(i=>!i.getAttribute('src'));
            return {url:location.href.slice(0,90), pm:allPM.length, total:imgs.length, mmbiz_attr:realmm.length, empty_src:empt.length, visible:vis.length, h2:el.querySelectorAll('h2').length, len:el.textContent.length};
        }""")
        log("[NEW DRAFT BODY] "+json.dumps(stats, ensure_ascii=False))
        # sample first 3 img src prefixes
        samp = edit.evaluate("""() => {
            const allPM=document.querySelectorAll('div.ProseMirror');
            const el=allPM[allPM.length-1];
            return [...el.querySelectorAll('img')].slice(0,4).map(i=>(i.getAttribute('src')||'').slice(0,55));
        }""")
        log("[SAMPLE SRC] "+json.dumps(samp, ensure_ascii=False))
        ctx.close(); log("[DONE]")

main()
