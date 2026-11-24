"""Read-only preflight for the 号B (时界之外) publish automation.

Checks which WeChat MP account is currently logged in for .publish_profile_b.
Exit codes:
  0 = logged in AND account is 时界之外  -> safe to publish
  1 = logged in but WRONG account        -> DO NOT publish
  2 = not logged in (login required)     -> DO NOT publish, needs QR scan
  3 = error
"""
import sys
from playwright.sync_api import sync_playwright

PROFILE = "/Users/liulei/Product/ATOM/01_PubWechatFile/.publish_profile_b"
EXPECTED = "时界之外"

with sync_playwright() as p:
    ctx = None
    try:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE, headless=False, channel="chrome",
            args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://mp.weixin.qq.com/", timeout=30000)
        # 已登录时首页会自动跳转到 /cgi-bin/home?...&token=...，跳转完成前 body 仍是登录页。
        # 固定等 5s 会把「实际已登录」误判成 NOT_LOGGED_IN（2026-11-18、11-22 均踩过）。
        # 以 URL 出现 token= 为准（最多等 20s），再留 3s 让昵称等内容渲染。
        try:
            page.wait_for_url(lambda u: "token=" in u, timeout=20000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        txt = page.evaluate("document.body.innerText") or ""
        # login page markers
        if ("使用账号登录" in txt) or ("扫码登录" in txt) or ("内容管理" not in txt):
            print("NOT_LOGGED_IN: login page shown, QR scan required")
            code = 2
        else:
            names = []
            try:
                names = [v.strip() for v in page.locator("[class*=nickname]").all_inner_texts() if v.strip()]
            except Exception:
                pass
            names = list(dict.fromkeys(names))
            if names and any(EXPECTED in n for n in names):
                print("OK_ACCOUNT: 时界之外  (nicknames=%s)" % names[:4])
                code = 0
            elif names:
                print("WRONG_ACCOUNT: expected 时界之外, got %s" % names[:4])
                code = 1
            else:
                # fall back to body text
                if EXPECTED in txt:
                    print("OK_ACCOUNT (body-text fallback): 时界之外")
                    code = 0
                else:
                    print("UNKNOWN_ACCOUNT: cannot read nickname")
                    code = 1
    except Exception as e:
        print("ERROR:", e)
        code = 3
    finally:
        if ctx:
            try:
                ctx.close()
            except Exception:
                pass
print("EXIT_CODE=%d" % code)
sys.exit(code)
