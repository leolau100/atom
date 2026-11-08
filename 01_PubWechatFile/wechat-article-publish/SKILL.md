---
name: wechat-article-publish
description: 把本地渲染好的微信公众号文章（wf.html，含 base64 内嵌图片）一键发布为「草稿」。当用户要把文章发到微信公众号、做公众号草稿、设置封面/原创/创作来源，或需要用 Playwright 驱动 mp.weixin.qq.com 编辑器时使用。触发词：发布公众号、微信草稿、公众号文章、上传到微信、设置封面、声明原创、创作来源。
---

# 微信公众号文章发布

## 适用场景
- 已有渲染好的微信文章 HTML（`wf.html`，图片以 `data:image/...` base64 内嵌）。
- 目标：发布为**草稿**（保存为草稿），并完成 **标题 / 作者 / 封面（正文首图）/ 声明原创（文字原创）/ 创作来源（个人观点，仅供参考）**。
- 注意：是「存草稿」不是「群发」。

## 用户约定（必看）
- **「今天 / 明天 / 昨天」等相对日期词 = 真实日期**：凡是用户让我改文件名后缀、或写在线文档「发布状态」列时提到的「今天 / 明天 / 昨天」，一律按**实际日历日期**替换，且**带上年份**。例如用户在 2026-9-1 说「今天发布明天上线」，应写成 `2026-9-1日发布，2026-9-2日上线`，不要原样保留「今天 / 明天」字样。
- 在线文档「发布状态」列与文件名后缀的日期口径要保持一致。

## 前置条件
1. Python 3 + `pip install playwright pillow`
2. 已安装 Chrome，脚本用 `sync_playwright().chromium.launch_persistent_context(channel="chrome")`。
3. 登录态：首次需扫码。把登录过的 Chrome User Data 拷到 `/tmp/wechat_pub_profile`（或直接用该目录扫码一次），之后复用，无需重扫。token 从首页 URL 取。
4. 待发布 HTML 路径：脚本里 `WF` 常量（默认 `/Users/liulei/WorkBuddy/2026-08-30-14-40-45/NiceWechatArticle/wf.html`）。

## 渲染管线（产出 wf.html）
`wf.html` 由用户自有工具 `NiceWechatArticle/` 生成：
- `render-harness.html`（`renderWechatFragment` 函数）+ `render_server.py`（端口 8899，`/__save` 写回 wf.html）。
- 概览：启动 `python render_server.py` → 用 Playwright 打开 harness 注入正文 → POST 到 `/__save` 得到 `wf.html`。
- 若用户已有现成 wf.html，跳过渲染，直接改脚本 `WF` 指向它即可。

## 发布脚本
本 skill 的 `scripts/publish.py` 是父目录 `publish.py` 的**符号链接**，物理上只有一份文件（用户主工作副本就是它）。

运行（两条等价）：
```bash
python scripts/publish.py          # 经 skill 内的软链
python ../publish.py               # 直接跑父目录那份
```
> 改 `TITLE` / `AUTHOR` / `SOURCE` / `WF` 常量即可换文章。建议后续用 argparse 参数化，避免手改。

## 执行流程（关键步骤）
1. 复用 `/tmp/wechat_pub_profile` 持久上下文，打开 mp 首页，`wait_login` 轮询直到出现「内容管理」且无「使用账号登录」/「登录超时」。
2. 从首页 URL 取 `token`，用直链打开编辑器：
   `cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=10&isMul=1&isNew=1&lang=zh_CN&token=...`
3. 标题：第一个 `div.ProseMirror`（`nth(0)`）全选清空后输入 `TITLE`。
4. 读取 `wf.html`（base64 图片）；对正文 `div.ProseMirror`（`nth(1)`）先清空、再**合成 paste 事件**粘贴。

## 关键坑（必看）
- **base64 粘贴会自动上传到 mmbiz**：微信在 paste 时会把 `data:image/...` 转成 `mmbiz` 图，无需预先上传。所以「先传 15 张图 → 清空 → 再粘贴全文」是冗余的，一次粘贴即可。验证：`mmbiz` 计数 = 正图文数，`dataimg` = 0。
- **Ctrl+V 读不到我们构造的系统剪贴板**，但能读到派发的 `ClipboardEvent` 的 `clipboardData`。务必用 `dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt}))` 而非 `page.keyboard.press('Control+V')`。`DataTransfer` 需设 `text/html` 与 `text/plain`。
- **封面不会自动用首图**：正文有图也不能依赖微信默认。必须：注入 CSS 强制 `.js_cover_opr` 显示，再点 `.js_selectCoverFromContent` → 第一个 `.appmsg_content_img.cover` → 「下一步」→ 编辑封面「确认」。
  ```js
  const pop = document.querySelector('.js_cover_opr');
  pop.style.cssText = 'display:block !important; visibility:visible !important; opacity:1 !important; z-index:99999 !important;';
  ```
  - 封面弹层是 CSS `:hover` 驱动，合成鼠标事件（`mouse.move` / `hover` 派发）不生效，必须用 cssText 强显。
  - 上传文件方式（`set_input_files`）对封面上传器无效（loading 永远不消失），用「从正文选择」最稳。
- **声明原创的「确定」按钮在对话框页脚**：它不在 `#js_original_edit_box` 内，而在该对话框自己的 `.weui-desktop-dialog__ft` 里。多个隐藏对话框共用 `weui-desktop-btn_primary` 类名，必须用 xpath 从 `#js_original_edit_box` 上溯到所属 `.weui-desktop-dialog` 再定位按钮，否则会误点「退出登录 / 前往实名 / 去设置」。
  - 流程：点 `.js_unset_original_title` → 选 `input[data-label=文字原创]` 的 label → 勾选页脚协议 checkbox → 点 scoped 页脚「确定」→ 等待对话框关闭（否则会挡住保存）。
- **创作来源**：`div#js_claim_source_area` → 点「未添加」→ 选文案「个人观点，仅供参考」→ 「确认」。
- **⚠️ `<pre>` 代码块会让整段正文粘贴失败**：微信 ProseMirror 的粘贴解析器在「HTML 含 `<pre>` 代码块 + 图片」组合时会直接报错，**整段正文插入被放弃（body 只剩占位 ~8 字符，图片只进素材库、不进正文），但图仍会被传到 mmbiz**。表现：粘贴后 `after paste stats` 的 `len≈8`、封面弹层能看到 16~17 张素材库缩略图却选不上、保存后是空草稿。排查（实验法）：去掉/转换 `<pre>` 后粘贴完全正常（文本 + 17 图全进 body）。
  - **修复（源头）**：`NiceWechatArticle/src/render/index.js` 的 `renderWechatFragment` 出口加了 `unwrapPreBlocks()`，把 `<pre>`→带行内样式的 `<div class="code-block">`（保留主题对 `pre` 的样式 + 兜底等宽/背景/换行/滚动），对所有调用方（harness、editor 一键复制）统一生效。`publish.py` 里的 `prep_html()` 已撤掉，凡是含代码块的文章都能直接发布，无需额外处理。
  - 配套：`render_server.py` 给静态资源加了 `Cache-Control: no-store`，并清掉 `/tmp/render_profile` 持久 context，否则浏览器会缓存旧 `index.js` 让修复看起来"没生效"。改渲染器后建议 `pkill -f render_server.py; rm -rf /tmp/render_profile; python3 render_server.py` 重启。
  - macOS 注意：没有 `setsid`，后台启动用工具的 `run_in_background` 模式更可靠，否则进程会被回收。
- **⚠️ 渲染服务会死 → publish 静默用错内容（已踩坑）**：`render_server.py` 偶发异常退出（macOS 后台进程被回收、`/tmp/render_profile` 持久 context 异常）。`render_driver.py` 会 `ERR_CONNECTION_REFUSED` 失败、**但 publish.py 完全不知道**——它照常读磁盘上的 `wf.html` 粘贴。如果 `wf.html` 是上一次成功的残留（且没人发现 SAVED 没打出来），就会把旧文章塞进新草稿，造成「**标题是新文章、正文是上篇文章**」的错配。**强制校验**：每次发布前必须 `grep -oc "<新文章关键词>" NiceWechatArticle/wf.html`（如 `grep -oc "OpenRemote"`），确认 ≥1 才是新文章（残留是 0）；如果 grep 显示错配，必须先 `pkill -f render_server.py; rm -rf /tmp/render_profile; python3 render_server.py`（用工具 `run_in_background` 启）+ 重渲染 + 再 grep 确认，再发 publish。
- **⚠️ 微信会话级风控会禁用粘贴（已踩坑，难自动恢复）**：`after paste stats` 出现 `len≈8`、`img:0`、`mmbiz:0` 即正文没粘进去。先用**对照实验**定性：在同一会话里粘贴一份「已知能成功」的历史 `wf.html`（如 `wf_kaa_backup.html`）。**若对照也空** → 本次微信登录会话被风控，**粘贴通道整体禁用**（与文章/浮层/选择器无关，浮层如「未实名/未设头像/选择文章」只是常驻干扰，清掉也不影响结论）。**不能程序化绕过**，只能：① 删 `/tmp/wechat_pub_profile` 重扫二维码换新登录态（需用户在场扫码）；② 等风控冷却后重试；③ 用户在浏览器里手动粘贴。若对照成功、目标失败 → 才是内容问题（继续二分 table/pre/超大图）。
- **`render_driver.py` 用系统 Chrome 通道**：驱动脚本改为 `p.chromium.launch(channel="chrome", headless=True)`，与 `publish.py` 一致，**不要**依赖 playwright 自带 chromium（`playwright install chromium` 在本机常被清/下载极慢易失败）。重建驱动时直接写 `channel="chrome"` 即可。

## 验证
- 保存后等待「已保存」toast；截图 `/tmp/final.png`。
- 成功标志：封面有图、作者正确、带「原创」标、创作来源已填、顶部绿条「已保存」。

## 注意事项
- `scripts/publish.py` 已软链到 `../publish.py`，全项目只有这一份实现，改哪边都是同一文件。
- 登录态过期：删 `/tmp/wechat_pub_profile` 后重扫一次即可。
