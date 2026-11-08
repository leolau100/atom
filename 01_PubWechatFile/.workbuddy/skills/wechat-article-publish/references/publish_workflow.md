# 微信发布工作流 · 详细参考

本文档是 `wechat-article-publish` skill 的实现细节与代码参考。SKILL.md 只讲流程与坑位，这里给可复用的具体代码。

---

## A. 渲染驱动（ocean 主题 → wf.html）

用 Playwright 打开 `render-harness.html`（带 query 参数自动渲染并回存），等待 `wf.html` 生成。

```python
# render_driver.py 思路
from playwright.sync_api import sync_playwright
import time, os

HARNESS = "http://127.0.0.1:8899/render-harness.html"   # ⚠️ 必须用 http(s)，render_server.py 已在 8899 提供静态服务
NA = "/Users/liulei/WorkBuddy/2026-08-30-14-40-45/NiceWechatArticle"
WF = f"{NA}/wf.html"

# footer 是可选参数，必须显式传；harness 只认单个 ?footer= URL。
# v2（2026-09-08 起）：footer 只传 footer.html（关于作者 + 加好友二维码）。
# ⚠️ 不要再合并 footer-custom.html —— 它已弃用为空文件，原「往期推荐 + 支持一下三栏」
#    已移除，改由微信原生能力提供（合集连续阅读 = 上一篇/下一篇；文末关注组件 = 关注卡片）。
#    历史存档：footer-v1-第一版（含往期推荐与支持图标）.html
# ⚠️ md/footer 必须用【相对 ROOT 的路径】，绝对路径会被当 absolute URL 解析 → 404
url = f"{HARNESS}?theme=ocean&md=_tmp_magistrala.md&footer=footer.html&save=/__save"
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")          # 用系统 Chrome，避免下载
    pg = b.new_page()
    pg.goto(url, wait_until="domcontentloaded")
    # harness 自动 POST 到 render_server 写 wf.html；轮询 __saved
    for _ in range(60):
        try:
            if pg.evaluate("() => window.__saved === true"): break
        except Exception: pass
        time.sleep(1)
    b.close()
```

**渲染后务必校验产物**：
```bash
WF=.../NiceWechatArticle/wf.html
grep -oE '<h[23][^>]*style="[^"]*background[^"]*"' "$WF" | wc -l   # 应 >0（标题背景）
grep -c "往期推荐" "$WF"; grep -c "关于作者" "$WF"                  # footer 应存在
grep -oE '.{8}<img.{6}' "$WF" | head -3                            # 图结构任意(<p>/<span>/<br>)
```

> 注意：主题由 `theme=` 参数指定，**不再固定 ocean**（2026-09-07 起用户按篇选主题，如 IoTSharp 用 `deepsea` 静海蓝调）。主题 id 从 06 仓库 `src/components/ThemeSelector.vue` 的 `id ↔ 中文名` 映射查（如 `grep "静海" src/components/ThemeSelector.vue`）。
> ⚠️ 校验别一律要求背景色：上面第 43 行的 `background` grep 只对 ocean 类主题成立；`deepsea` 等「白底无背景」主题的 h2 没有 background，`heading bgs` 全 `rgba(0,0,0,0)` 属正常，靠 `border-left: 4px solid rgb(20,102,176)` 竖线体现（改用 grep 竖线/border-left 校验）。

---

## B. publish.py 关键结构（位于 `/Users/liulei/Product/01_PubWechatFile/publish.py`）

常量（已迁移到持久目录，避免 `/tmp` 重启清空登录态）：
```python
PROFILE = "/Users/liulei/Product/01_PubWechatFile/.publish_profile"   # 持久登录态
WF      = "/Users/liulei/WorkBuddy/2026-08-30-14-40-45/NiceWechatArticle/wf.html"
IMG_DIR = "/Users/liulei/Product/01_PubWechatFile/.imgs"
TITLE   = "..."   # 默认 FIWARE 标题
AUTHOR  = "DoublePoint"
SOURCE  = "个人观点，仅供参考"
```

启动会话（用系统 Chrome 持久上下文 + 授权剪贴板）：
```python
ctx = p.chromium.launch_persistent_context(
    user_data_dir=PROFILE, headless=False, channel="chrome",
    args=["--no-sandbox", "--disable-setuid-sandbox"])
ctx.grant_permissions(["clipboard-read", "clipboard-write"])
```

---

## C. 粘贴逻辑（含「继续插入」处理）—— 核心代码

**务必保留以下形态**；`insertHTML` 兜底已移除。

```python
def activate_chrome():
    """AppleScript 把 Google Chrome 置前，保证剪贴板粘贴可用。"""
    for name in ("Google Chrome", "Chrome"):
        try:
            subprocess.run(["osascript", "-e",
                f'tell application "{name}" to activate'], timeout=5, check=False)
            return
        except Exception:
            continue

def cursor_to_end():
    edit.evaluate("""() => {
        const els = document.querySelectorAll('div.ProseMirror');
        const el = els[els.length-1]; el.focus();
        const s = window.getSelection(); const r = document.createRange();
        r.selectNodeContents(el); r.collapse(false);
        s.removeAllRanges(); s.addRange(r);
    }""")

def _click_continue_insert():
    """微信「内容结构检测」对话框的「继续插入」按钮：点它才保留内联样式。"""
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
    # 真实剪贴板粘贴（走微信 paste 处理器，保留 background 等样式）
    edit.evaluate("""async (html) => {
        const plain = html.replace(/<[^>]+>/g, ' ');
        await navigator.clipboard.write([new ClipboardItem({
            'text/html': new Blob([html], {type:'text/html'}),
            'text/plain': new Blob([plain], {type:'text/plain'})
        })]);
    }""", frag)
    activate_chrome()                       # 坑3：强制窗口前台
    edit.wait_for_timeout(800)
    cursor_to_end()
    cdp.send("Input.dispatchKeyEvent", {    # CDP 派发 Cmd+V
        "type": "keyDown", "modifiers": 4, "key": "v", "code": "KeyV",
        "windowsVirtualKeyCode": 86, "commands": ["paste"]})
    cdp.send("Input.dispatchKeyEvent", {
        "type": "keyUp", "modifiers": 4, "key": "v", "code": "KeyV",
        "windowsVirtualKeyCode": 86})
    edit.wait_for_timeout(3500)
    _click_continue_insert()                # 坑1：弹框必须点「继续插入」
    st = body_stats()
    if st["len"] < 200:
        log("[FAIL] body still empty after real paste + 继续插入")
        return 'empty'
    return 'ok'
```

`body_stats()`（判断粘贴是否成功的依据）：
```python
def body_stats():
    return edit.evaluate("""() => {
        let els = Array.from(document.querySelectorAll('div.ProseMirror'));
        let el = els[els.length-1];
        return {img: el.querySelectorAll('img').length,
                mmbiz: el.querySelectorAll('img[src*=mmbiz]').length,
                h2: el.querySelectorAll('h2').length,
                footer: el.textContent.includes('往期推荐'),
                len: el.textContent.length};
    }""")
```

**图片策略（整篇 base64 一次粘贴，微信自动转 mmbiz）**：
```python
# 当前方案：整篇 HTML（含 base64 图）一次真实粘贴，微信 paste 处理器
# 逐张自动上传到 mmbiz 并替换 src，得到可持久化节点。
# ⚠️ 不要用 set_input_files + 占位符：编辑器里能看到 mmbiz，但保存后
#    正文图全部丢失（file input 插入没走微信内容模型，序列化不保留）。
# ⚠️ webp 必须先转 PNG：微信粘贴上传通道处理不了 webp，会「图片处理失败」
#    并清空 src（浏览器能渲染故当时看得见，但保存即丢）。
n_webp = len(re.findall(r'data:image/webp;', html))
if n_webp:
    html = re.sub(r'data:image/([^;]+);base64,([^"]+)', _webp_to_png, html)
    # _webp_to_png: mime=='webp' → Pillow convert('RGBA').save('PNG') →
    #   return f"data:image/png;base64,{b64}"
# 然后整篇一次粘贴（单片段），微信自动上传；轮询直到 mmbiz 数量与图总数一致。
```

---

## D. 发布后重命名（WeChatArticle 仓库）

```bash
cd /Users/liulei/Product/WeChatArticle
git mv "2026/09/<slug>.md"  "2026/09/<slug> （YYYY-M-D日发布，YYYY-M-D日上线）.md"
git mv "2026/09/<slug>.html" "2026/09/<slug> （YYYY-M-D日发布，YYYY-M-D日上线）.html"
git add -A
git commit -q -m "chore: <slug> 发布后重命名(加发布/上线日期后缀)"
git push origin main
```
> 后缀示例（9-5 发布）：` （2026-9-5日发布，2026-9-6日上线）`。`publish.py` 不负责此步。

---

## D2. 发布后更新「在线发布状态台账」（必做约定）⚠️

**2026-09-07 教训**：Fledge(9-6)、ChirpStack(9-7) 两次发布后只做了 git 重命名，漏更新在线文档发布状态——因为流程从未把「更新在线文档」列为强制步骤。从此每次发布完成必须执行本步。

在线台账是腾讯文档个人版在线表格，用户核对进度的唯一来源：

- 文件 ID：`DTHBucU5VRkpxbUtt`，sheet 名：`fDHygY`（「开源物联网平台盘点」）。
- 列：序号 A | 名称 B | … | 发布状态 L（**col 11，0-based**）。
- 行：**序号 N = row N（0-based）**；表头占 row 0，序号 1 → row 1。A1 行号 = N+1。
  - 例：序号 10（Fledge）→ row 10 → `L11`；序号 11（ChirpStack）→ row 11 → `L12`。
- 写值：`YYYY-M-D日发布，YYYY-M-D日上线`（发布当天 / 上线次日，与 git 后缀一致）。

工具族：`mcp__sheetagent__*`
```python
# 1. 先读确认位置（不要盲写）
#    read_table(file_id="DTHBucU5VRkpxbUtt", sheet_name="fDHygY")
#    get_cell_ranges(["A1:L20"], file_id="DTHBucU5VRkpxbUtt")
# 2. 写发布状态（必须 allow_overwrite=true）
set_cell_range(
    file_id="DTHBucU5VRkpxbUtt", sheetName="fDHygY",
    allow_overwrite=True,
    cells={"L11": {"value": "2026-9-6日发布，2026-9-7日上线"},   # Fledge 序号10
           "L12": {"value": "2026-9-7日发布，2026-9-8日上线"}})  # ChirpStack 序号11
# 3. 回读核验
#    get_cell_ranges(["L11:L12"], file_id="DTHBucU5VRkpxbUtt")
```

> 与 git 重命名并列的「发布完成」双验收项，不可省略；无工具权限时须显式告知用户手动改。

---

## E. 发布日志解读（看 `/tmp/publish.log`）

成功标志（以 qslave 第三次发布为例）：
```
[INFO] clicked 「继续插入」 → 微信 paste 处理器已确认，样式保留
[INFO] paste via real clipboard: len=3723 h2=8 img=0
[INFO] heading bgs: ["rgba(0, 119, 182, 0.08)", ... ×13]   # 全部标题背景保留
[OK] cover set: url("https://mmbiz.qpic.cn/...")
[OK] original declared
[OK] source set
[DONE]
```

失败信号：
- `real paste empty, fallback insertHTML` → 旧逻辑（已删除）残留，或焦点问题。
- `heading bgs: []` → 背景被洗，检查是否走了 insertHTML / 是否点了「继续插入」。
- `original declare failed ... intercepts pointer events` → 弹框未消失就执行后续步骤，确保 `_click_continue_insert()` 后等待足够。
- `图片处理失败`（微信弹窗）/ 重开草稿 `mmbiz` 归零 → **webp 未转 PNG**，或用了 set_input_files 占位符（保存后丢）。
- 渲染报 `读取 /Users/... 失败: 404` → md/footer 传了绝对路径，改相对路径。
- `[WARN] 合集 not set` → 合集对话框没选上（选项在 `.select-opts-con` 的 `LI.select-opt-li`，下拉需先真实点击输入框再 fill；别用 `children.length<=1` 过滤选项）。
- `[WARN] 账号名片 未检测到` → 微信「账号搜索建议」接口偶发限流（`cards=0`），非代码错；用户在编辑器手动补 `更多→账号名片→未来技术观察→插入`。

---

## F. 文末「账号名片 + 合集」（2026-09-08 新增必做项，publish.py 自动做）

`publish.py` 在 `来源` 之后、存草稿之前自动执行两步（顺序固定：**合集先、账号名片后**）：

**F1. 合集【开源物联网平台】**（已验证稳定）
```python
# 1) 打开合集选择：点 "未添加" 那块（.js_article_tags_label），不是外层 div/label 文字
edit.evaluate("""()=>{ const a=document.querySelector('#js_article_tags_area .js_article_tags_label'); if(a)a.click(); }""")
# 2) 对话框里真实点击搜索框打开下拉，再 fill（仅 evaluate 设值下拉不弹）
inp = edit.locator(".weui-desktop-dialog:has(.weui-desktop-dialog__title:has-text('合集')) input[placeholder='请选择合集']").first
inp.click(timeout=5000); inp.fill("开源物联网平台")
# 3) 点选项（.select-opts-con 内的 LI.select-opt-li，按文本包含选，勿按叶子过滤）
# 4) 点 button.weui-desktop-btn_primary（确认）
# 成功：#js_article_tags_area 文本 → "合集 开源物联网平台"
```

**F2. 账号名片【未来技术观察】**（best-effort，依赖微信建议接口）
```python
cursor_to_end()  # 名片插到正文末尾
# 打开「更多」菜单 + 点 账号名片（hover 下拉，用 JS click）
edit.evaluate("()=>{const b=document.querySelector('.js_editor_showmore,#js_editor_showmore'); if(b)b.click();}")
edit.evaluate("()=>{const li=document.querySelector('#js_editor_insertProfile'); if(li)li.click();}")
# 「插入账号名片」对话框：点搜索结果卡片 .wx_profile_card（昵称 .wx_profile_nickname == 未来技术观察）
#   —— 不是 profile_history_item（仅出预览、不选中、插入按钮保持禁用）
# 点 button.weui-desktop-btn_primary（插入）
# 建议接口偶发拉不到卡片(cards=0) → 仅 WARN，不阻断；用户手动补
```

> ⚠️ 账号名片放最后：其对话框若因建议接口失败残留，由存草稿前的 `safety` 块 `Esc` 关闭，不干扰前面的合集步骤。

---

## F. 经验要点（跨项目可复用）

1. 微信粘贴 HTML 后**必先处理「内容结构检测」弹框**，点「继续插入」才保留样式；不点就拦截。
2. 禁用 `execCommand('insertHTML')` 作为粘贴兜底（洗样式）。
3. 真实剪贴板粘贴必须保证 Chrome 前台焦点（AppleScript + bring_to_front）。
4. **图片 = 整篇 base64 一次真实粘贴，让微信自动上传 mmbiz**；不要 set_input_files 占位符（保存后丢）。
5. **base64 图必须是 PNG，不能是 webp**（微信处理不了 webp → 图片处理失败 → 保存丢图）。
6. 渲染 harness 的 md/footer 用**相对路径**，绝对路径被当 URL 解析 404。
7. **发布后重开草稿确认图片持久化**（`mmbiz` 数量与发布时一致）才算真正完成。
8. 发布后源文件加「(发布,上线)」日期后缀并提交（既有约定）。
9. 草稿箱 SPA 导航不稳定，重复草稿交用户手动清理。
10. footer 检测关键词：v2 起用「关于作者」（旧的「往期推荐」已移除，用它会恒为 false）。

---

## H. 渲染失败诊断脚本（抓 console + 探测资源）

`render_article.py` 报 `[FAIL] 渲染未保存` 时用它定位（见 SKILL.md 坑 8）：

```python
#!/usr/bin/env python3
import os, subprocess, time, urllib.parse, urllib.request
from playwright.sync_api import sync_playwright

NA = "/Users/liulei/Product/06_NiceWeChatFile"; os.chdir(NA)
PORT = 8907
THEME = "qbitai"          # 换成实际主题 id
MD = "_tmp_xxx.md"        # 06 根下的 md 文件名（相对路径）

env = {**os.environ, "PORT": str(PORT)}
proc = subprocess.Popen(["python3", "render_server.py"], cwd=NA, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(2)
print("server alive:", proc.poll() is None)

# 1) 直连探测：确认静态资源都能取到
for path in ["render-harness.html", MD, "footer.html", f"themes/{THEME}.css",
             "src/render/index.js", "src/config/headingStyle.js"]:
    try:
        code = urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/{urllib.parse.quote(path)}", timeout=5).status
        print(f"  GET {path} -> {code}")
    except Exception as e:
        print(f"  GET {path} -> FAIL {type(e).__name__} {e}")

# 2) 抓浏览器 console / pageerror —— 关键
url = (f"http://127.0.0.1:{PORT}/render-harness.html"
       f"?theme={THEME}&md={urllib.parse.quote(MD)}&footer=footer.html&save=/__save")
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page()
    logs = []
    pg.on("console", lambda m: logs.append(f"[{m.type}] {m.text[:200]}"))
    pg.on("pageerror", lambda e: logs.append(f"[pageerror] {str(e)[:200]}"))
    pg.goto(url, wait_until="domcontentloaded")
    for _ in range(45):
        try:
            if pg.evaluate("() => window.__saved === true"):
                print("SAVED"); break
        except Exception:
            pass
        time.sleep(1)
    else:
        print("TIMEOUT not saved")
    for l in logs[-25:]:
        print("  ", l)
    b.close()
proc.terminate()
```

看 console 判定：
- `Failed to fetch dynamically imported module ... 404` → `src/render/index.js` 的相对 import 补 `.js` 扩展名。
- `TypeError: Failed to execute 'insertBefore' ...` → 渲染代码里节点为 `null`，加 null 保护。
