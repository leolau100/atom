import os, re, sys, time, json, glob, io, base64, subprocess
from playwright.sync_api import sync_playwright
from PIL import Image

PROFILE = "/Users/liulei/Product/01_PubWechatFile/.publish_profile"
WF = "/Users/liulei/Product/06_NiceWeChatFile/wf.html"
IMG_DIR = "/Users/liulei/Product/01_PubWechatFile/.imgs"
TITLE = "做智慧城市或开放数据平台，这个开源免费的 FIWARE 可以当底座"
AUTHOR = "DoublePoint"
SOURCE = "个人观点，仅供参考"
CARD_NAME = "未来技术观察"   # 文末账号名片名称；命令行可覆盖，空字符串=不插入名片
LOG = open("/tmp/publish.log", "w", encoding="utf-8")

def log(*a):
    s = " ".join(str(x) for x in a)
    print(s); LOG.write(s + "\n"); LOG.flush()

def human(d=1.0): time.sleep(d)

def activate_chrome():
    """把已打开的 Google Chrome 窗口带到前台，确保剪贴板粘贴可用。"""
    for name in ("Google Chrome", "Chrome"):
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'tell application "{name}" to activate'],
                timeout=5, check=False)
            return
        except Exception:
            continue

def launch_persistent(p, profile):
    """启动持久化 Chrome。若撞上残留的 ProcessSingleton 死锁（上次异常退出留下的
    SingletonLock/Socket/Cookie），且确认无活进程占用该 profile，就自动清锁重试一次；
    有活进程占用则原样抛出（不能删别人的锁）。"""
    try:
        return p.chromium.launch_persistent_context(
            user_data_dir=profile, headless=False, channel="chrome",
            args=["--no-sandbox", "--disable-setuid-sandbox"])
    except Exception as e:
        msg = str(e)
        if "ProcessSingleton" not in msg and "already in use" not in msg:
            raise
        try:
            holders = subprocess.run(
                ["pgrep", "-f", f"user-data-dir={profile}"],
                capture_output=True, text=True, timeout=5).stdout.strip()
        except Exception:
            holders = ""
        if holders:
            log("[FAIL] profile 正被其他 Chrome 实例使用，请稍后再试")
            raise
        log("[WARN] 检测到残留 singleton 死锁，自动清理后重试")
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            fp = os.path.join(profile, name)
            try:
                if os.path.lexists(fp):
                    os.unlink(fp)
            except Exception as e2:
                log(f"[WARN] 清理 {fp} 失败: {e2}")
        return p.chromium.launch_persistent_context(
            user_data_dir=profile, headless=False, channel="chrome",
            args=["--no-sandbox", "--disable-setuid-sandbox"])

def pick_darkest(img_dir):
    """Return the path of the darkest (lowest luminance) image in img_dir."""
    files = sorted(glob.glob(os.path.join(img_dir, "*.webp")) +
                   glob.glob(os.path.join(img_dir, "*.png")) +
                   glob.glob(os.path.join(img_dir, "*.jpg")) +
                   glob.glob(os.path.join(img_dir, "*.jpeg")))
    if not files:
        return None
    def lum(p):
        im = Image.open(p).convert("RGB").resize((48, 48))
        px = list(im.getdata())
        return sum(0.299*r + 0.587*g + 0.114*b for r, g, b in px) / len(px)
    ranked = sorted(((lum(f), f) for f in files))
    log(f"[INFO] darkest image = {os.path.basename(ranked[0][1])} (lum={ranked[0][0]:.1f})")
    return ranked[0][1]

def logged_in(page):
    try:
        txt = page.evaluate("document.body.innerText")
        return ("内容管理" in txt) and ("使用账号登录" not in txt) and ("登录超时" not in txt)
    except Exception:
        return False

def switch_account(page, name):
    """登录后切到指定公众号（mp 后台右上角账号切换）。best-effort，失败仅 WARN。

    不同微信号各自用独立 --profile 登录时通常无需切号（该微信号只管一个号）；
    但若某 profile 登录的微信名下挂了多个公众号，可传 --account 自动选号。
    """
    log(f"[INFO] 尝试切换到公众号: {name}")
    try:
        # 展开右上角账号下拉（多种可能的选择器，命中其一即可）
        for sel in ["#account_switch", ".weui-desktop-account__switch",
                    "a[href*='account_switch']", ".js_account_switch",
                    "#avatar", ".weui-desktop-account"]:
            try:
                page.locator(sel).first.click(timeout=2500)
                log(f"[INFO] clicked account switcher: {sel}")
                break
            except Exception:
                continue
        human(1.5)
    except Exception:
        pass
    # 在可见文案里找匹配项点击（名称或原始ID）
    try:
        hit = page.evaluate("""(nm) => {
            const all=[...document.querySelectorAll('a,li,div,span')];
            const cand=all.filter(e=>{
                const t=(e.innerText||'').trim();
                return t && t.length<60 && (t.includes(nm) || nm.includes(t));
            });
            cand.sort((a,b)=> (b.innerText.includes(nm)?1:0)-(a.innerText.includes(nm)?1:0));
            if(cand[0]){ cand[0].click(); return cand[0].innerText.trim().slice(0,40); }
            return '';
        }""", name)
        human(2.0)
        log(f"[INFO] 账号切换 → {hit or '未命中，请手动切换'}")
    except Exception as e:
        log("[WARN] 账号切换失败（登录态里手动切）:", e)
    page.wait_for_timeout(3000)  # 切换后 URL 带新 token，等稳定

def reveal_qr(page):
    """点 '扫码登录' 切到二维码模式，截取 QR 元素图到 /tmp/wechat_qr.png。

    mp.weixin.qq.com 默认显示 '微信快捷登录'，此时第一个 <img> 是 0x0 隐藏的
    scanloginqrcode 图；点击 '扫码登录' 后它变成 122x122 可见。
    """
    # 切到扫码模式
    for sel in ["text=扫码登录", "a:has-text('扫码登录')", "span:has-text('扫码登录')"]:
        try:
            page.locator(sel).first.click(timeout=2000)
            log(f"[INFO] clicked {sel}")
            break
        except Exception:
            continue

    # 等第一个 <img> 变为可见（就是 QR）
    for _ in range(30):
        try:
            img = page.locator("img").first
            box = img.bounding_box()
            if box and box["width"] > 50 and box["height"] > 50:
                img.screenshot(path="/tmp/wechat_qr.png")
                log(f"[INFO] QR element saved /tmp/wechat_qr.png ({box['width']}x{box['height']})")
                return True
        except Exception:
            pass
        time.sleep(0.5)

    log("[WARN] QR element not found, fallback full page shot")
    try:
        page.screenshot(path="/tmp/wechat_qr.png")
    except Exception as e:
        log("[WARN] qr shot fail", e)
    return False

def refresh_qr_image(page):
    """Re-capture the current live QR into /tmp/wechat_qr.png (keeps it fresh)."""
    try:
        img = page.locator("img").first
        box = img.bounding_box()
        if box and box["width"] > 50 and box["height"] > 50:
            img.screenshot(path="/tmp/wechat_qr.png")
    except Exception:
        pass

def wait_login(page, timeout=600):
    """Poll until WeChat home shows logged-in UI. Returns True if logged in."""
    if logged_in(page):
        return True
    reveal_qr(page)
    for i in range(timeout):
        if logged_in(page):
            return True
        # keep the presented QR image always current (mp rotates it ~120s)
        if i % 10 == 0:
            try:
                page.bring_to_front()
            except Exception:
                pass
            refresh_qr_image(page)
        time.sleep(1)
    return False

def click_text(page, text, timeout=8000):
    loc = page.get_by_text(text, exact=False)
    loc.first.wait_for(state="visible", timeout=timeout)
    loc.first.click()
    human(1.0)

def main():
    import argparse
    global WF, TITLE, AUTHOR, SOURCE, CARD_NAME, PROFILE, COLLECTION
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default=WF, help="渲染产物 HTML 路径")
    ap.add_argument("--title", default=TITLE, help="微信文章标题")
    ap.add_argument("--author", default=AUTHOR, help="作者")
    ap.add_argument("--source", default=SOURCE, help="创作来源声明")
    ap.add_argument("--collection", default="开源物联网平台", help="微信合集名（自动勾选；留空则不勾选）")
    ap.add_argument("--profile", default=PROFILE, help="持久登录态目录（每个微信号一个，互不干扰）")
    ap.add_argument("--account", default="", help="登录后切换到该公众号（名称/原始ID；留空不切）")
    ap.add_argument("--card-name", default=CARD_NAME, help="文末账号名片名称（空字符串=不插入名片）")
    args = ap.parse_args()
    WF, TITLE, AUTHOR, SOURCE = args.html, args.title, args.author, args.source
    COLLECTION = args.collection  # 全局，供合集步骤使用
    CARD_NAME = args.card_name    # 全局，供账号名片步骤使用
    PROFILE = args.profile        # 覆盖模块默认，供下方 launch 使用

    with sync_playwright() as p:
        ctx = launch_persistent(p, args.profile)
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        page = ctx.new_page()

        # ---------- LOGIN ----------
        log("[1] opening mp home")
        page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        try:
            page.bring_to_front()
        except Exception:
            pass
        if not wait_login(page):
            log("[FAIL] login timeout - please scan QR in the browser window")
            page.screenshot(path="/tmp/publish_state.png")
            ctx.close(); return
        log("[OK] logged in")
        if args.account:
            switch_account(page, args.account)

        # ---------- OPEN EDITOR (direct URL with token) ----------
        log("[2] navigate to new article editor")
        # token is already in the home URL after login
        tok = ""
        m = re.search(r"token=(\d+)", page.url)
        if m:
            tok = m.group(1)
        else:
            page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            m = re.search(r"token=(\d+)", page.url)
            tok = m.group(1) if m else ""
        log("[INFO] token =", tok)
        edit = ctx.new_page()
        edit.goto(f"https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=10&isMul=1&isNew=1&lang=zh_CN&token={tok}", wait_until="domcontentloaded")
        edit.wait_for_timeout(5000)
        try: edit.screenshot(path="/tmp/editor_open.png")
        except Exception: pass
        log("[OK] editor opened")

        # 关闭编辑器内可能弹出的教育/引导对话框（会拦截编辑区点击）
        try:
            edit.wait_for_timeout(2500)
            dlg = edit.locator(".weui-desktop-dialog__wrp.education-dialog")
            if dlg.count() and dlg.first.is_visible():
                log("[INFO] dismissing education-dialog")
                try:
                    dlg.first.locator("button").first.click(timeout=3000)
                except Exception:
                    edit.evaluate("""() => {
                        document.querySelectorAll('.weui-desktop-dialog__wrp, .weui-desktop-mask, .weui-mask').forEach(e => e.remove());
                    }""")
                edit.wait_for_timeout(600)
        except Exception as e:
            log(f"[WARN] education-dialog handling: {e}")

        # ---------- TITLE ----------
        log("[3] fill title")
        # WeChat renders the title as the FIRST visible ProseMirror (above #author)
        te = edit.locator("div.ProseMirror").nth(0)
        te.wait_for(state="visible", timeout=10000)
        te.click(force=True); edit.keyboard.press("Control+A"); edit.keyboard.press("Backspace")
        edit.keyboard.type(TITLE, delay=30); human(0.5)
        log("[OK] title filled")

        # ---------- READ FINAL HTML ----------
        # WeChat auto-uploads base64 images on paste (verified: pasting the
        # raw wf.html yields 15 mmbiz images, 0 leftovers). So a single paste
        # replaces the old "upload 15 images -> clear -> paste" redundancy.
        log("[4] read ocean HTML (base64 images; WeChat uploads on paste)")
        html = open(WF, encoding="utf-8").read()
        b64_imgs = re.findall(r'<img[^>]*src="data:image/[^"]+"[^>]*>', html)
        log(f"[INFO] base64 img tags in wf.html: {len(b64_imgs)}")

        # WeChat 的粘贴上传通道处理不了 webp（会「图片处理失败」并丢弃图：
        # 浏览器能渲染 webp 故当时看得见，但保存时 src 被清空）。统一转 PNG。
        n_webp = len(re.findall(r'data:image/webp;', html))
        if n_webp:
            def _webp_to_png(m):
                mime, b64 = m.group(1), m.group(2)
                if mime.lower() != "webp":
                    return m.group(0)
                try:
                    im = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
                    buf = io.BytesIO(); im.save(buf, "PNG")
                    nb = base64.b64encode(buf.getvalue()).decode()
                    return f"data:image/png;base64,{nb}"
                except Exception as e:
                    log(f"[WARN] webp->png failed: {e}")
                    return m.group(0)
            html = re.sub(r'data:image/([^;]+);base64,([^"]+)', _webp_to_png, html)
            log(f"[INFO] converted {n_webp} webp images -> PNG (WeChat 可上传持久化)")
        else:
            log("[INFO] no webp images, skip conversion")

        # ---------- CLEAR EDITOR then PASTE (synthetic paste event) ----------
        log("[5] clear editor and paste ocean HTML")
        body = edit.locator("div.ProseMirror").nth(1)
        body.click(force=True)
        # robust clear: select all content in the body ProseMirror and delete
        for _ in range(5):
            edit.evaluate("""() => {
                const ps = document.querySelectorAll('div.ProseMirror');
                const el = ps[ps.length-1];
                el.focus();
                const s = window.getSelection();
                s.removeAllRanges();
                const r = document.createRange();
                r.selectNodeContents(el);
                s.addRange(r);
                document.execCommand('delete', false, null);
            }""")
            human(0.3)
            n = edit.evaluate("""() => {
                const ps = document.querySelectorAll('div.ProseMirror');
                const el = ps[ps.length-1];
                return el.querySelectorAll('img').length + el.textContent.replace(/\\s/g,'').length;
            }""")
            if n == 0:
                break
        # WeChat 风控已拦截「合成 ClipboardEvent 派发」，改用「真实剪贴板 + 真实按键」。
        def body_stats():
            return edit.evaluate("""() => {
                let els = Array.from(document.querySelectorAll('div.ProseMirror'));
                let el = els[els.length-1];  // body (last ProseMirror)
                return {img: el.querySelectorAll('img').length,
                        mmbiz: el.querySelectorAll('img[src*=mmbiz]').length,
                        h2: el.querySelectorAll('h2').length,
                        // footer v2（2026-09-08 起）只有「关于作者 + 加作者好友」，
                        // 旧的「往期推荐」已移除，改为检测「关于作者」以免一直误报 false。
                        footer: el.textContent.includes('关于作者'),
                        len: el.textContent.length};
            }""")

        # ------------------------------------------------------------------
        # 图片策略：整篇正文（含 base64 图）一次粘贴。WeChat paste 处理器
        # 收到 base64 <img> 后会逐张自动上传到 mmbiz 并替换 src，得到可
        # 持久化的图片节点。之前用 set_input_files + 占位符的方式虽能在
        # 编辑器里看到 mmbiz:16，但保存草稿后正文图片全部丢失、mmbiz:0
        # （这是因为 file input 触发的插入没走 WeChat 内容模型，序列化时不
        # 保留；封面因为走的是「从正文选择」标准对话框所以得以保留）。
        # 单片段粘贴 → 保留 background-color；自动上传 → 持久化。
        # 折中：base64 体积大、首次粘贴慢；上传需数十秒，下面轮询等到齐。
        # ------------------------------------------------------------------
        n_img = len(re.findall(r'src="data:image/[^"]+"', html))
        text_all = html  # 整篇含 base64 图，WeChat 自动上传
        log(f"[INFO] full html {len(text_all)}ch, base64 imgs={n_img}")

        # 3) 整篇一次性粘贴（单片段，微信不再清洗内联样式）
        cdp = ctx.new_cdp_session(edit)
        body = edit.locator("div.ProseMirror").nth(1)
        body.click(force=True)
        edit.evaluate("""() => {
            const ps=document.querySelectorAll('div.ProseMirror');
            const el=ps[ps.length-1]; el.focus();
            const s=window.getSelection(); s.removeAllRanges();
            const r=document.createRange(); r.selectNodeContents(el); s.addRange(r);
            document.execCommand('delete', false, null);
        }""")
        edit.wait_for_timeout(500)

        def cursor_to_end():
            edit.evaluate("""() => {
                const els = document.querySelectorAll('div.ProseMirror');
                const el = els[els.length-1];
                el.focus();
                const s = window.getSelection();
                const r = document.createRange();
                r.selectNodeContents(el);
                r.collapse(false);
                s.removeAllRanges();
                s.addRange(r);
            }""")

        def _click_continue_insert():
            """微信「内容结构检测」对话框的「继续插入」按钮。
            只有用户(或脚本)点这个，微信的 paste 处理器才会真正把 HTML 写入
            编辑器并保留 background-color 等内联样式；不点就拦截/不写入。
            """
            try:
                edit.locator(
                    ".weui-desktop-dialog button:has-text('继续插入')"
                ).first.click(timeout=3000)
                log("[INFO] clicked 「继续插入」 → 微信 paste 处理器已确认，样式保留")
                edit.wait_for_timeout(3000)
                return True
            except Exception:
                return False

        def paste_text(frag):
            # 真实剪贴板粘贴（走微信自己的 paste 事件处理器，会保留内联样式）。
            # 为避免「非前台窗口读不到剪贴板」，粘贴前 AppleScript 把 Chrome 置前。
            edit.evaluate("""async (html) => {
                const plain = html.replace(/<[^>]+>/g, ' ');
                await navigator.clipboard.write([new ClipboardItem({
                    'text/html': new Blob([html], {type:'text/html'}),
                    'text/plain': new Blob([plain], {type:'text/plain'})
                })]);
            }""", frag)
            activate_chrome()
            edit.wait_for_timeout(800)
            cursor_to_end()
            cdp.send("Input.dispatchKeyEvent", {
                "type": "keyDown", "modifiers": 4, "key": "v", "code": "KeyV",
                "windowsVirtualKeyCode": 86, "commands": ["paste"]})
            cdp.send("Input.dispatchKeyEvent", {
                "type": "keyUp", "modifiers": 4, "key": "v", "code": "KeyV",
                "windowsVirtualKeyCode": 86})
            edit.wait_for_timeout(3500)
            # 微信通常会弹「内容结构检测」对话框（darkmode-low-contrast 等），
            # 必须点「继续插入」才会真正写入并保留 background 等样式；不点
            # 就被拦截，body_stats() 会读到接近空、误判失败。
            if _click_continue_insert():
                pass
            else:
                # 万一按钮没出现（无检测/旧版本），再等一会拿到稳定状态
                edit.wait_for_timeout(1500)
            st = body_stats()
            log(f"[INFO] paste via real clipboard: len={st['len']} h2={st['h2']} img={st['img']}")
            if st["len"] < 50:
                log("[FAIL] body still empty after real paste + 继续插入")
                return 'empty'
            return 'ok'

        r2 = paste_text(text_all)
        log(f"[INFO] single full paste clipboard: {r2}")
        edit.wait_for_timeout(4000)
        log(f"[after text paste] {json.dumps(body_stats(), ensure_ascii=False)}")

        # 等待 WeChat 把 base64 图自动上传到 mmbiz
        deadline = time.time() + 120
        last_mmbiz = -1
        while time.time() < deadline:
            st = body_stats()
            if st["mmbiz"] >= n_img and st["len"] > 50:
                log(f"[INFO] all {n_img} images uploaded: {json.dumps(st, ensure_ascii=False)}")
                break
            if st["mmbiz"] != last_mmbiz:
                log(f"[INFO] waiting for images: {json.dumps(st, ensure_ascii=False)}")
                last_mmbiz = st["mmbiz"]
            time.sleep(2)
        else:
            log(f"[WARN] timeout waiting for images, final: {json.dumps(body_stats(), ensure_ascii=False)}")

        edit.wait_for_timeout(5000)
        stats = body_stats()
        log("[INFO] final stats:", json.dumps(stats, ensure_ascii=False))
        # 验证所有标题背景是否都在
        bg_info = edit.evaluate("""() => {
            const ps=document.querySelectorAll('div.ProseMirror');
            const el=ps[ps.length-1]; const out=[];
            el.querySelectorAll('h2,h3').forEach(h=>out.push(getComputedStyle(h).backgroundColor));
            return out;
        }""")
        log("[INFO] heading bgs:", json.dumps(bg_info, ensure_ascii=False))
        try: edit.screenshot(path="/tmp/after_paste.png")
        except Exception: pass
        if stats["len"] < 50:
            log("[FAIL] body still nearly empty -> abort, NOT saving draft")
            ctx.close(); return
        if stats["mmbiz"] < n_img:
            log(f"[WARN] only {stats['mmbiz']}/{n_img} images uploaded to mmbiz")
        edit.wait_for_timeout(3000)

        # ---------- AUTHOR ----------
        log("[6] fill author")
        try:
            ae = edit.locator("#js_author, #author, [placeholder*='作者']").first
            ae.wait_for(state="visible", timeout=5000)
            ae.click(); edit.keyboard.press("Control+A"); edit.keyboard.press("Backspace")
            edit.keyboard.type(AUTHOR, delay=40); human(0.5)
            log("[OK] author filled")
        except Exception as e:
            log("[WARN] author fill failed:", e)

        # ---------- COVER (set FIRST body image as cover via cover-from-content) ----------
        # WeChat doesn't auto-fill cover when the body has images; we must open the
        # cover area popup, choose 「从正文选择」, pick the first thumbnail, confirm
        # through the two-step modal (选择图片 → 下一步 → 编辑封面 → 确认).
        # The popup is CSS-:hover driven so synthetic mouse events won't show it;
        # we force its display via cssText.
        log("[7] set cover = first body image (从正文选择)")
        try:
            edit.evaluate("""() => {
                const pop = document.querySelector('.js_cover_opr');
                if (pop) {
                    pop.style.cssText = 'display:block !important; visibility:visible !important; opacity:1 !important; z-index:99999 !important;';
                    let p = pop.parentElement;
                    while (p) { if (window.getComputedStyle(p).display === 'none') p.style.display = 'block'; p = p.parentElement; }
                }
            }""")
            human(0.5)
            edit.locator(".js_selectCoverFromContent").first.click(timeout=5000)
            human(3)
            # click first thumb in 「选择图片」modal
            n = edit.evaluate("""() => {
                const ths = document.querySelectorAll('.appmsg_content_img.cover');
                if (ths.length) ths[0].click();
                return ths.length;
            }""")
            log(f"[INFO] cover thumbs available: {n}; selected first")
            human(1.5)
            # click 下一步 in 选择图片 dialog
            edit.locator(".weui-desktop-dialog:has(.weui-desktop-dialog__title:has-text('选择图片')) button:has-text('下一步')").first.click(timeout=5000)
            human(3)
            # click 确认 in 编辑封面 dialog
            edit.locator(".weui-desktop-dialog:has(.weui-desktop-dialog__title:has-text('编辑封面')) button:has-text('确认')").first.click(timeout=5000)
            human(2.5)
            # verify
            cover_bg = edit.evaluate("() => document.querySelector('.js_appmsg_thumb_new')?.style.backgroundImage || ''")
            ok = bool(cover_bg) and ("http" in cover_bg or "mmbiz" in cover_bg)
            log("[OK] cover set:" if ok else "[WARN] cover NOT set:", cover_bg[:100])
            # 恢复封面弹窗：之前被强制 display:block 且 z-index 99999，不恢复会一直
            # 浮在页面上，挡住后面「创作来源」等区域的点击（pointer-events 拦截）。
            edit.evaluate("""() => { const pop=document.querySelector('.js_cover_opr'); if(pop) pop.style.cssText=''; }""")
        except Exception as e:
            log("[WARN] cover set failed (set manually):", e)
            edit.evaluate("""() => { const pop=document.querySelector('.js_cover_opr'); if(pop) pop.style.cssText=''; }""")
            try: edit.keyboard.press("Escape"); human(0.5)
            except Exception: pass

        # ---------- DECLARE ORIGINAL ----------
        log("[8] declare original (文字原创)")
        try:
            edit.locator(".js_unset_original_title").first.click(timeout=6000)
            human(1.5)
            # select 文字原创 radio (via its label)
            edit.locator('label.weui-desktop-form__check-label:has(input[data-label="文字原创"])').click(timeout=5000)
            human(0.8)
            # agree to terms (footer checkbox, OUTSIDE #js_original_edit_box)
            # 用 JS 直接定位 + 点击 + 设 checked，绕过 Playwright 的可见性检查
            ck_res = edit.evaluate("""() => {
                const d = document.querySelector('#js_original_edit_box');
                if (!d) return 'no_dialog';
                const dl = d.closest('.weui-desktop-dialog');
                if (!dl) return 'no_dialog_wrap';
                const cb = dl.querySelector('.weui-desktop-dialog__ft input.weui-desktop-form__checkbox');
                if (!cb) return 'no_checkbox';
                if (!cb.checked) {
                    cb.click();
                    // 也直接置 checked 防止 click 被拦截
                    cb.checked = true;
                    cb.dispatchEvent(new Event('change', {bubbles:true}));
                }
                return 'ok checked=' + cb.checked;
            }""")
            log(f"[INFO] agreement checkbox: {ck_res}")
            # confirm via footer 确定 button (scoped to the original dialog's
            # own .weui-desktop-dialog wrapper, to avoid matching other hidden
            # dialogs' primary buttons like 退出登录/前往实名/去设置)
            edit.locator("#js_original_edit_box").locator(
                "xpath=ancestor::div[contains(@class,'weui-desktop-dialog')]"
            ).locator("button.weui-desktop-btn_primary").click(timeout=5000)
            human(1.5)
            # wait for dialog to disappear (so it won't block save)
            edit.wait_for_function(
                "() => { const d=document.querySelector('#js_original_edit_box');"
                " return !d || getComputedStyle(d).display==='none' || d.offsetParent===null; }",
                timeout=8000)
            log("[OK] original declared")
        except Exception as e:
            log("[WARN] original declare failed:", e)
            try: edit.keyboard.press("Escape"); human(0.5)
            except Exception: pass

        # ---------- SOURCE ----------
        log("[9] set 创作来源")
        try:
            # 关掉编辑器加载时可能残留的账号设置提醒浮层（实名/头像/切换账号），
            # 它们会遮挡来源点击；只点「取消/我知道了/关闭/暂不」，绝不点「前往实名/去设置/退出登录」。
            edit.evaluate("""() => {
                const dismiss=['未授权使用切换账号','公众号尚未实名','未设置头像和名称','完善公众号','使用切换账号'];
                const btns=['取消','我知道了','关闭','暂不'];
                for (const d of document.querySelectorAll('.weui-desktop-dialog')) {
                    if (dismiss.some(bt=>(d.innerText||'').includes(bt))) {
                        const b=[...d.querySelectorAll('button,a')].find(x=>btns.includes((x.textContent||'').trim()));
                        if(b) b.click();
                    }
                }
            }""")
            human(0.8)

            SOURCE_OK = False
            for attempt in range(5):
                # JS 直点来源触发区（绕过浮层遮挡）：点含「未添加/修改/已声明」文字的 span/div
                # （绝不能选外层 <label>，否则只勾选「原创」复选框而不弹来源下拉）
                edit.evaluate("""() => {
                    const a=document.querySelector('#js_claim_source_area');
                    if(!a) return;
                    const el=[...a.querySelectorAll('span,a,div')].find(x=>(x.textContent||'').includes('未添加')||(x.textContent||'').includes('修改')||(x.textContent||'').includes('已声明'));
                    if(el){ el.click(); return; }
                    const trig=a.querySelector('.js_claim_source_desc') || a.querySelector('.allow_click_opr');
                    if(trig) trig.click();
                }""")
                human(1.5)
                # 直接定位来源对话框（同时含「创作来源」与目标文案），点中对应 label
                r = edit.evaluate("""(name) => {
                    const norm = s => (s||'').replace(/\\s+/g,'');
                    const ds=[...document.querySelectorAll('.weui-desktop-dialog')];
                    const dlg=ds.find(x=>norm(x.innerText).includes('创作来源') && norm(x.innerText).includes(norm(name)));
                    if(!dlg) return 'no-dialog';
                    const labels=[...dlg.querySelectorAll('label')];
                    const el=labels.find(x=>norm(x.textContent)===norm(name));
                    if(!el) return 'no-opt:'+labels.length;
                    el.click();
                    return 'clicked';
                }""", SOURCE)
                if r != 'clicked':
                    log(f"[WARN] source option not ready, retry {attempt+1}: {r}")
                    continue
                # 点该对话框内的「确认」
                edit.evaluate("""(name) => {
                    const norm = s => (s||'').replace(/\\s+/g,'');
                    const ds=[...document.querySelectorAll('.weui-desktop-dialog')];
                    const dlg=ds.find(x=>norm(x.innerText).includes('创作来源') && norm(x.innerText).includes(norm(name)));
                    if(!dlg) return;
                    const b=[...dlg.querySelectorAll('button')].find(x=>(x.textContent||'').replace(/\\s+/g,'')==='确认')
                           || dlg.querySelector('button.weui-desktop-btn_primary');
                    if(b) b.click();
                }""", SOURCE)
                human(1.0)
                # 验证：来源区不再显示「未添加」才算成功（避免误报 OK）
                area_text = edit.evaluate("""() => { const a=document.querySelector('#js_claim_source_area'); return a?a.innerText.replace(/\\s+/g,' ').trim():''; }""")
                if ('未添加' not in area_text) and area_text:
                    SOURCE_OK = True
                    log(f"[OK] source set verified: {area_text[:50]}")
                    break
                else:
                    log(f"[WARN] source not reflected, retry {attempt+1}: {area_text[:50]}")
            if not SOURCE_OK:
                log("[FAIL] 创作来源 未能选中（请后台手动选「个人观点，仅供参考」）")
            edit.keyboard.press("Escape"); human(0.5)
        except Exception as e:
            log("[WARN] source set failed:", e)
            try: edit.keyboard.press("Escape"); human(0.5)
            except Exception: pass

        # ---------- ADD TO 合集 ----------
        # 微信「合集」在编辑器底部设置区；点 .js_article_tags_label 打开选择框，
        # 输入合集名 → 点选项 → 确认。已实测生效（area 文本变为「合集 <名>」）。
        # 合集名由 --collection 控制（默认 开源物联网平台）。留空则不勾选。
        # 务必放在「账号名片」之前：账号名片对话框偶发拉不到建议会残留，可能干扰合集输入框。
        if COLLECTION:
            log(f"[9.5] add to 合集 {COLLECTION}")
            try:
                edit.evaluate("""()=>{ const a=document.querySelector('#js_article_tags_area .js_article_tags_label'); if(a)a.click(); }""")
                human(2.0)
                inp = edit.locator(".weui-desktop-dialog:has(.weui-desktop-dialog__title:has-text('合集')) input[placeholder='请选择合集']").first
                # 微信合集搜索是子串匹配；名称可能带/不带空格，故依次尝试：原名 → 去空格 → 首词，命中下拉即选第一个
                search_terms = [COLLECTION, COLLECTION.replace(" ", ""), COLLECTION.split(" ")[0]]
                picked = False
                for term in search_terms:
                    if not term:
                        continue
                    try: inp.click(timeout=5000); human(0.8)
                    except Exception: pass
                    inp.fill(term); human(2.5)
                    try: inp.press("Enter"); human(1.5)
                    except Exception: pass
                    clicked = edit.evaluate("""() => { const ds=[...document.querySelectorAll('.weui-desktop-dialog')]; const d=ds.find(x=>x.innerText.includes('每篇文章最多添加')); const con=d&&d.querySelector('.select-opts-con'); if(!con) return false; const lis=[...con.querySelectorAll('.select-opt-li, li')]; if(!lis.length) return false; lis[0].click(); return true; }""")
                    if clicked:
                        log(f"[INFO] 合集 下拉命中(搜索词='{term}')，已选第一个"); picked = True; break
                    # 未命中则清空重试
                    try: inp.fill(""); human(0.5)
                    except Exception: pass
                if not picked:
                    log("[WARN] 合集 下拉无匹配项（请确认微信后台已创建该合集）")
                human(1.5)
                edit.evaluate("""() => { const ds=[...document.querySelectorAll('.weui-desktop-dialog')]; const d=ds.find(x=>x.innerText.includes('每篇文章最多添加')); const b=d&&d.querySelector('button.weui-desktop-btn_primary'); if(b) b.click(); }""")
                human(2.0)
                area = edit.evaluate("""() => { const a=document.querySelector('#js_article_tags_area'); return a?a.innerText.replace(/\\s+/g,' ').trim():'none'; }""")
                log("[OK] 合集 set:" if COLLECTION.replace(" ","") in area.replace(" ","") else "[WARN] 合集 not set (add manually):", area)
            except Exception as e:
                log("[WARN] 合集 add failed:", e)
        else:
            log("[9.5] 未指定 --collection，跳过合集")

        # ---------- INSERT 账号名片 (未来技术观察) ----------
        # 微信文末「账号名片」是编辑器原生插入的卡片（非 footer HTML 可表示），
        # 必须走编辑器「更多 → 账号名片」对话框。插入位置 = 当前光标（已在正文末尾）。
        # 注意：账号选择依赖微信「账号搜索建议」接口，偶发拉不到卡片（网络/限流），
        # 此时 best-effort 失败 → 仅 WARN，不阻断发布，由用户手动补点。放在最后，
        # 其残留对话框交给下方 safety 块关闭，避免干扰前面的合集步骤。
        if CARD_NAME:
            log(f"[9.6] insert 账号名片 {CARD_NAME}")
            try:
                cursor_to_end()
                edit.evaluate("""()=>{const b=document.querySelector('.js_editor_showmore,#js_editor_showmore'); if(b)b.click();}""")
                human(1.0)
                edit.evaluate("""()=>{const li=document.querySelector('#js_editor_insertProfile'); if(li)li.click();}""")
                human(2.5)
                # 输入账号名片名 → 回车触发微信账号查询 → 选第一个卡片 → 点确认
                search = edit.locator(".weui-desktop-dialog:has(.weui-desktop-dialog__title:has-text('插入账号名片')) input[placeholder*='账号名称或账号ID']").first
                search.click(timeout=5000); human(0.8); search.fill(CARD_NAME); human(0.5)
                search.press("Enter"); human(3.0)  # 回车才真正查询
                picked = edit.evaluate("""(CARD_NAME) => {
                    const ds=[...document.querySelectorAll('.weui-desktop-dialog')];
                    const d=ds.find(x=>x.innerText.includes('插入账号名片'));
                    if(!d) return 'no dialog';
                    const cards=[...d.querySelectorAll('.wx_profile_card')];
                    if(!cards.length) return 'no card (cards=0)';
                    // 按账号名精确匹配，不依赖列表顺序（避免顺序变化选错）
                    const norm = s => (s||'').trim().replace(/\\s+/g,'');
                    let t = cards.find(c => [...c.querySelectorAll('*')].some(e => norm(e.textContent)===norm(CARD_NAME)));
                    if(!t) t = cards.find(c => c.innerText.includes(CARD_NAME));  // 退回模糊包含
                    if(!t) return 'no matching card (total='+cards.length+')';
                    t.click();  // 选中精确匹配到的卡片
                    return 'clicked match card (total='+cards.length+', name='+CARD_NAME+')';
                }""", CARD_NAME)
                log("[INFO] 账号名片 selection:", picked)
                human(1.5)
                # 点「确认」：微信此版对话框的确认按钮不一定是 weui-desktop-btn_primary，
                # 依次尝试多种选择器；点击前确保第一张卡片已选中。重试 3 次。
                def click_confirm():
                    # 直接 evaluate 点 footer「插入」按钮（比 locator 的 :has() 更稳）
                    res = edit.evaluate("""() => {
                        const ds=[...document.querySelectorAll('.weui-desktop-dialog')];
                        const d=ds.find(x=>x.innerText.includes('插入账号名片'));
                        if(!d) return 'no dialog';
                        const ft=d.querySelector('.weui-desktop-dialog__ft');
                        const btn=ft? ft.querySelector('button'): d.querySelector('button.weui-desktop-btn_primary');
                        if(!btn) return 'no btn';
                        if(btn.disabled) return 'btn disabled';
                        btn.click();
                        return 'clicked: '+(btn.textContent||'').trim();
                    }""")
                    return res
                has = False
                for i in range(3):
                    edit.evaluate("""(CARD_NAME) => { const ds=[...document.querySelectorAll('.weui-desktop-dialog')]; const d=ds.find(x=>x.innerText.includes('插入账号名片')); if(!d) return; const cards=[...d.querySelectorAll('.wx_profile_card')]; if(!cards.length) return; const norm=s=>(s||'').trim().replace(/\\s+/g,''); let t=cards.find(c=>[...c.querySelectorAll('*')].some(e=>norm(e.textContent)===norm(CARD_NAME))); if(!t) t=cards.find(c=>c.innerText.includes(CARD_NAME)); if(!t) t=cards[0]; if(t&&!t.classList.contains('wx_profile_card_selected')) t.click(); }""", CARD_NAME)
                    human(1.0)
                    r = click_confirm()
                    log("[INFO] confirm click result:", r)
                    human(2.0)
                    # 成功判定：账号名片是原子节点，昵称未必在 innerText 中，
                    # 故以「已点「插入」且对话框随之关闭」作为插入成功信号（微信仅此一按钮）。
                    dialog_gone = edit.evaluate("""() => { const ds=[...document.querySelectorAll('.weui-desktop-dialog')]; return !ds.find(x=>x.innerText.includes('插入账号名片')); }""")
                    text_has = edit.evaluate("""(nm) => { for(const el of document.querySelectorAll('div.ProseMirror')) if(el.innerText.includes(nm)) return true; return false; }""", CARD_NAME)
                    has = bool(dialog_gone) and (r == 'clicked: 插入' or text_has)
                    if has:
                        break
                log("[OK] 账号名片 inserted" if has else f"[WARN] 账号名片 未检测到 → 请在编辑器手动点「更多→账号名片→{CARD_NAME}→确认」")
            except Exception as e:
                log("[WARN] 账号名片 insert failed:", e)
        else:
            log("[9.6] --card-name 为空，跳过账号名片插入")

        # safety: 关闭一切残留弹窗（内容结构检测 / 原创 / 来源 等），否则会挡住保存按钮
        for _ in range(4):
            try:
                # 内容结构检测对话框若还在，点「继续插入」
                edit.locator(".weui-desktop-dialog button:has-text('继续插入')").first.click(timeout=1500)
                log("[INFO] save前再次点了「继续插入」"); human(1.5)
            except Exception:
                pass
            try: edit.keyboard.press("Escape"); human(0.8)
            except Exception: pass

        # ---------- SAVE DRAFT ----------
        log("[8] save draft")
        saved = False
        for attempt in range(3):
            try:
                btn = edit.locator("#js_save, button.edui-button:has-text('保存'), button:has-text('保存为草稿'), .js_save_btn").first
                btn.wait_for(state="visible", timeout=5000)
                btn.scroll_into_view_if_needed()
                btn.click(timeout=5000, force=True)
                try:
                    edit.get_by_text("已保存", exact=False).wait_for(timeout=6000)
                except Exception:
                    pass
                saved = True
                log(f"[OK] draft saved (attempt {attempt+1})")
                break
            except Exception as e:
                log(f"[WARN] save attempt {attempt+1} failed: {e}")
                try: edit.screenshot(path=f"/tmp/save_fail_{attempt}.png")
                except Exception: pass
                human(1.5)
        edit.wait_for_timeout(2000)
        try: edit.screenshot(path="/tmp/final.png")
        except Exception: pass
        if not saved:
            log("[FAIL] 无法自动保存 —— 请在浏览器里手动点「保存为草稿」")

        ctx.close()
        log("[DONE]")

main()
