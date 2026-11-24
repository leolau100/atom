# -*- coding: utf-8 -*-
"""仅登录号B（时界之外）：打开扫码二维码，等用户扫码，登录态存回 profile。"""
import sys, time, re, subprocess, os
from playwright.sync_api import sync_playwright

PROFILE = "/Users/liulei/Product/ATOM/01_PubWechatFile/.publish_profile_b"
QR = "/tmp/wechat_qr_b.png"

def log(*a): print(" ".join(str(x) for x in a), flush=True)

def launch(p):
    try:
        return p.chromium.launch_persistent_context(
            user_data_dir=PROFILE, headless=False, channel="chrome",
            args=["--no-sandbox", "--disable-setuid-sandbox"])
    except Exception as e:
        if "ProcessSingleton" not in str(e) and "already in use" not in str(e):
            raise
        holders = subprocess.run(["pgrep", "-f", f"user-data-dir={PROFILE}"],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
        if holders:
            log("[FAIL] profile 正被占用"); raise
        for n in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            fp = os.path.join(PROFILE, n)
            if os.path.lexists(fp): os.unlink(fp)
        return p.chromium.launch_persistent_context(
            user_data_dir=PROFILE, headless=False, channel="chrome",
            args=["--no-sandbox", "--disable-setuid-sandbox"])

def logged_in(page):
    try:
        txt = page.evaluate("document.body.innerText")
        return ("内容管理" in txt) and ("使用账号登录" not in txt) and ("登录超时" not in txt)
    except Exception:
        return False

def show_qr(page):
    for sel in ["text=扫码登录", "a:has-text('扫码登录')", "span:has-text('扫码登录')"]:
        try:
            page.locator(sel).first.click(timeout=3000); log("[INFO] clicked 扫码登录"); break
        except Exception: pass
    for _ in range(20):
        try:
            img = page.locator("img.scanloginqrcode__img, .scanloginqrcode img, img[src*='qrcode']").first
            img.wait_for(state="visible", timeout=1500)
            img.screenshot(path=QR)
            log(f"[OK] QR saved {QR}"); return True
        except Exception:
            try:
                imgs = page.locator("img")
                for i in range(imgs.count()):
                    im = imgs.nth(i)
                    if im.is_visible():
                        box = im.bounding_box()
                        if box and 100 <= box['width'] <= 400 and 100 <= box['height'] <= 400:
                            im.screenshot(path=QR); log(f"[OK] QR saved(fallback) {QR}"); return True
            except Exception: pass
            time.sleep(0.5)
    page.screenshot(path=QR); log("[WARN] QR fallback full page"); return False

with sync_playwright() as p:
    ctx = launch(p)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    if logged_in(page):
        log("[OK] 已登录，无需扫码", page.url)
        ctx.close(); sys.exit(0)
    show_qr(page)
    log("[WAIT] 请在浏览器窗口扫码（二维码每~100s自动刷新），最长等待 300 秒")
    deadline = time.time() + 300
    last_capture = time.time()
    while time.time() < deadline:
        page.wait_for_timeout(3000)
        if logged_in(page):
            log("[OK] 登录成功，登录态已写入 profile", page.url)
            page.wait_for_timeout(2000)
            ctx.close(); sys.exit(0)
        if time.time() - last_capture > 100:
            try:
                img = page.locator("img.scanloginqrcode__img, .scanloginqrcode img, img[src*='qrcode']").first
                img.screenshot(path=QR); log("[INFO] QR refreshed")
            except Exception: pass
            last_capture = time.time()
    log("[FAIL] 登录超时")
    ctx.close(); sys.exit(1)
