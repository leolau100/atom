---
name: wechat-article-publish
description: "Automate publishing Markdown articles to the WeChat Official Account draft box. Covers NiceWechatArticle ocean-theme rendering, Playwright system Chrome paste into the WeChat editor, handling the WeChat content-structure-check dialog (must click 继续插入 to keep background-color styles), and the post-publish filename date-suffix convention. CRITICAL pitfalls baked in: (1) WeChat cannot process webp images on paste — they silently fail and vanish after save, must convert base64 webp→PNG first; (2) whole-article base64 single paste so WeChat auto-uploads to mmbiz (do NOT use set_input_files placeholders — those vanish after save); (3) render-harness md/footer URLs must be relative (absolute paths 404); (4) always re-open the draft to confirm images persisted (mmbiz count persists). Use this skill when publishing to WeChat, or when reported: stripped background colors, missing images, 图片处理失败, empty drafts."
agent_created: true
---

# 微信公众号文章自动化发布

把 Markdown 文章渲染成 ocean 主题 HTML，并通过 Playwright + 系统 Chrome 自动化粘贴到微信公众号编辑器的草稿箱，发布完成后按约定重命名源文件。

## 何时使用

- 用户要求「把某篇文章发到微信公众号 / 发布到微信草稿」。
- 需要自动化把 HTML 拷贝进微信编辑器（避免手工粘贴的重复劳动）。
- 微信内文章**背景色 / 内联样式丢失**——这几乎总是粘贴方式不对，参考下方「关键坑位」。
- 文章在 WeChatArticle 仓库发布后需要**加日期后缀重命名**。

## 三个仓库/目录约定

| 用途 | 路径 |
|---|---|
| 文章源（`.md`/`.html`） | `/Users/liulei/Product/WeChatArticle/2026/MM/`（git 仓库 `git@github.com:leolau100/WeChatArticle.git`） |
| 渲染器（NiceWechatArticle） | `/Users/liulei/WorkBuddy/2026-08-30-14-40-45/NiceWechatArticle/`（含 `render-harness.html`、`render_server.py`、`themes/ocean.css`） |
| 发布器 `publish.py` | `/Users/liulei/Product/01_PubWechatFile/`（git 仓库 `git@github.com:leolau100/WeChatPublish.git`） |

> 渲染产物固定写到 `NiceWechatArticle/wf.html`，`publish.py` 默认读取它。

## 标准流程

### 1. 渲染（支持多主题，`theme=` 指定）

用 `render-harness.html` 把目标 `.md` 渲染成 `wf.html`（图片内联为 base64）：

```
render-harness.html?theme=<主题id>&md=<md相对路径>&footer=<footer文件>&save=/__save
```

**主题 id 查表**：06 仓库 `src/components/ThemeSelector.vue` 有 `id ↔ 中文名` 映射（如 `deepsea` = 静海蓝调、`ocean` = 海洋）。用户给中文主题名时先 `grep "静海" src/components/ThemeSelector.vue` 之类查到 id 再传 `theme=`。

> ⚠️ **校验标准随主题变化，别一律要求「标题有背景色」**（2026-09-07 首次用非 ocean 主题时踩到）：
> - `ocean`：h2 带 `background-color: rgba(0,119,182,0.08)` 背景块。
> - `deepsea`（静海蓝调，2026-09-07 IoTSharp 首用）：**白底无背景**，`heading bgs` 全 `rgba(0,0,0,0)` 属**正常**；靠 `border-left:4px solid rgb(20,102,176)` 竖线 + 文字 `rgb(10,42,74)` 体现。
> → 按主题实际视觉特征判断，避免把正确渲染误判成「背景被洗」。

⚠️ **footer 是可选 URL 参数，不传就不加**（`const footerUrl = params.get('footer') || ''`）。

**footer v2 约定（2026-09-08 起）**：只传 `&footer=footer.html`，内容仅「关于作者 + 加作者好友二维码」。**不要再合并 `footer-custom.html`**（已弃用为空文件）。

> ⚠️ **文末的「关注卡片」与「上一篇/下一篇目录」都是微信原生能力，不要自己写进 footer**（用户 2026-09-08 明确要求）：
> - **上一篇/下一篇** → 微信【合集】+「文末连续阅读」：后台 `内容管理 → 合集` → 创建**文章合集** → 打开**「连续阅读」**开关 → 发布新文章时勾选该合集。文章底部自动出现 `上一篇 / 下一篇` + 合集目录入口。
>   - 合集内**至少 2 篇**才显示；**历史已发布文章不会自动生效**，需重新编辑保存才会补上。
> - **关注卡片** → 微信文末原生关注组件（自动展示），或在编辑器插入「公众号名片」。
>
> 第一版 footer（含往期推荐列表 + 支持一下「点赞/收藏/星标」三栏）已存档为 06 仓库 `footer-v1-第一版（含往期推荐与支持图标）.html`，仅供回溯、不参与渲染。

它会 POST 渲染结果到 `render_server.py` 并写入 `wf.html`。校验产物：
- `h2/h3` 内联 `style` 符合**当前主题**特征（ocean 看背景色、deepsea 看竖线，见上）。
- 正文图片不一定包在 `<p>` 里（实测有 `<span><img>`、`<br><img>`），发布脚本已改为匹配任意 base64 `<img>`，无需手动调整结构。

06 仓库已有固化脚本，**优先直接用**（自动复制 md 到 06 根、渲染、校验，默认 footer v2）：
```bash
cd /Users/liulei/Product/06_NiceWeChatFile
python3 render_article.py --md "/abs/path/文章.md" --theme deepsea
#   --footer 默认 footer.html（v2）；--theme 默认 ocean；md 也接受 06 根相对文件名
```
渲染驱动脚本写法另见 `references/publish_workflow.md`。

### 2. 发布（`publish.py`）

脚本已参数化：
```
python3 publish.py --title "<文章标题>" [--html wf.html] [--author DoublePoint] [--source "个人观点，仅供参考"]
```
脚本自动完成：登录（持久化登录态，无需重扫）→ 打开新文章编辑器 → 填标题 → 整篇粘贴 HTML → 真实文件上传图片 → 设封面（正文第一张）→ 文字原创 → 创作来源 → **加合集【开源物联网平台】** → **文末插账号名片【未来技术观察】** → 存草稿。

> ⚠️ **文末账号名片 + 合集是用户 2026-09-08 新增的必做项**（见 坑 9）。两者都在 `publish.py` 的 `[9.5] 合集 / [9.6] 账号名片` 步骤自动做，无需手动。

### 3. 发布后重命名（重要约定）

文章成功发布后，**必须**把 WeChatArticle 仓库里对应的源文件（及所在文件夹，若存在）重命名加后缀，否则与既有约定不一致：
```
# 若文章在独立子目录内(如 Magistrala)，整个文件夹也要加后缀：
git mv "2026/08/29/2026-08-29-xxx（Mainflux）" \
       "2026/08/29/2026-08-29-xxx（Mainflux） （YYYY-M-D日发布，YYYY-M-D日上线）"
# 文件加后缀（直接位于日期目录或已随文件夹移动后）：
git mv "YYYY-MM-DD-xxx.md" "YYYY-MM-DD-xxx （YYYY-M-D日发布，YYYY-M-D日上线）.md"
git mv "YYYY-MM-DD-xxx.html" "YYYY-MM-DD-xxx （YYYY-M-D日发布，YYYY-M-D日上线）.html"
git add -A && git commit -m "chore: <slug> 发布后重命名(加发布/上线日期后缀)"
git push origin main
```
⚠️ **整目录重命名约定**：当文章以「同名子目录」组织（md/html/mp4/assets 都在里面，如 `2026/08/29/2026-08-29-xxx（Mainflux）/`）时，**文件夹和文件都要加后缀**，不能只改文件不改文件夹（2026-09-06 因此返工过）。
后缀里的「发布」取当天、「上线」取次日（如 9-5 发布 → `2026-9-5日发布，2026-9-6日上线`）。`publish.py` 不负责这步，需另行执行。

### 4. 发布后更新「在线发布状态台账」（必做约定）⚠️

> **2026-09-07 教训**：9-06（Fledge）、9-07（ChirpStack）两次发布后**只做了 git 重命名，漏更新在线文档发布状态**。原因：本流程在 9-06 之前从未把「更新在线文档」固化成强制步骤，9-01~9-05 是手动补的，未传入流程，顺手发布时自然遗忘。从此**每次发布完成（含 git 重命名后）必须执行本步**，否则状态台账与真实发布脱节。

在线台账是一份**腾讯文档在线表格**（个人版），记录每篇文章的发布状态，是用户核对进度的唯一来源，与 git 重命名同等重要。

- 文件：`DTHBucU5VRkpxbUtt`（腾讯文档个人版，sheet 名 `fDHygY`「开源物联网平台盘点」）。
- 列结构：序号 A | 名称 B | … | 发布状态 L（**col 11，0-based**）。
- 行约定：**序号 N = row N（0-based）**；0-based row 10 → A1 行号 11（即序号 10 在 L11）。注意表头占 row 0，故序号 1 在 row 1 而非 row 0。
- 写入值格式：`YYYY-M-D日发布，YYYY-M-D日上线`（发布取当天、上线取次日，与 git 后缀一致）。

操作步骤（用 `mcp__sheetagent` 工具族）：
1. `read_table` / `get_cell_ranges` 先读该表，确认目标文章序号对应的行、列位置没错。
2. `set_cell_range`（必须 `allow_overwrite=true`）写 发布状态列：如 Fledge(序号10) → `L11` 写 `2026-9-6日发布，2026-9-7日上线`；ChirpStack(序号11) → `L12` 写 `2026-9-7日发布，2026-9-8日上线`。
3. 写后**回读该格**（再 `get_cell_ranges`）确认写入生效，再向用户报告「发布状态已更新」。

> ⚠️ 这是与 git 重命名并列的「发布完成」双验收项之一，**不可省略**。若本次会话无在线文档工具权限，必须显式告知用户「发布状态未更新」，请其手动改，绝不能静默跳过。

## 关键坑位（核心经验）

### 坑 1：粘贴后必须点击「继续插入」 ⚠️ 最重要

微信在 Cmd+V 真实粘贴 HTML 后会弹出 **「内容结构检测」** 对话框（标题"内容结构检测"，列出 `darkmode-low-contrast` 等风险），提供「取消」和绿色「继续插入」按钮。

- **只有点击「继续插入」，微信的 paste 处理器才会真正把 HTML 写入编辑器并保留 `background-color` 等内联样式。**
- 不点 → 内容被拦截，`body_stats()` 读到接近空，进而误判"粘贴失败"。
- 实现：粘贴后主动 `edit.locator(".weui-desktop-dialog button:has-text('继续插入')").first.click()`。

### 坑 2：禁止使用 `document.execCommand('insertHTML', ...)` 兜底

为绕过"空粘贴"而改用 `insertHTML` 直接塞 DOM，**会绕过微信 paste 事件处理器**，导致微信的样式归一化把内联 `background-color` 洗掉（表现为"上半有背景下半白"或整体无背景）。手动 Cmd+V 能保留样式，就是因为走的是真正的 paste 事件。

→ 主粘贴必须是**真实剪贴板粘贴**（走微信 paste 处理器 + 点「继续插入」）。`insertHTML` 不得作为兜底。

### 坑 3：真实剪贴板粘贴需要 Chrome 前台焦点

`navigator.clipboard.write` + 派发 Cmd+V 依赖系统剪贴板。macOS 安全策略：**非前台（非激活）App 读不到剪贴板**，导致正文空粘贴（`len:8`，但标题用 `keyboard.type` 因走 CDP 直注反而能填）。

→ 粘贴前用 `activate_chrome()`（AppleScript `tell application "Google Chrome" to activate`）+ `edit.bring_to_front()` 强制窗口前台，再写剪贴板、再 Cmd+V。

### 坑 4：图片 = 整篇 base64 一次真实粘贴（微信自动上传 mmbiz），且必须转 PNG ⚠️ 关键

当前正确方案（2026-09-06 修正）：**整篇含 base64 图的 HTML 一次真实 Clipboard 粘贴**，WeChat 的 paste 处理器收到 base64 `<img>` 后会**逐张自动上传到 mmbiz 并替换 src**，得到可**持久化**的图片节点。

> ⚠️ 不要再走「占位符 + `set_input_files` 真实文件上传」老路：那种方式编辑器里能看到 `mmbiz:16`，但**保存草稿后正文图片全部丢失（重开变 `mmbiz:0`）**——因为 file input 触发的插入没走微信内容模型、序列化时不保留；封面因走「从正文选择」标准对话框才得以保留。踩坑返工多次。

两个硬约束：
- **⚠️ 图片必须是 PNG，不能是 webp**：微信粘贴上传通道**处理不了 webp**，会报**「图片处理失败」**并把 src 清空（浏览器能渲染 webp 故粘贴时看得见，但保存即丢）。`publish.py` 已在读取 wf.html 后把 base64 webp 统一 `Pillow.convert("RGBA").save("PNG")` 再粘贴；若未来渲染器直接产出 PNG 可省这步，但 webp 一律要先转。
- **单片段粘贴**：整篇一次粘贴（不要分段），否则后续片段的 `background-color` 会被微信清洗（"上半有背景下半白"）。

校验：发布日志应出现 `converted N webp images -> PNG` 与 `mmbiz: N`（N 与正文+二维码图总数一致），且保存后重开草稿 `mmbiz` 仍为 N（见坑 6）。

### 坑 5：渲染 `render-harness.html` 的 md/footer 必须用**相对路径**

harness 用 `fetch(mdUrl)` 直接取 URL。**绝对路径（如 `/Users/.../x.md`）会被当 absolute URL 解析、向浏览器请求 `http://Users/.../` 而 404**（控制台报 `读取 /Users/... 失败: 404`）。

→ 必须通过 `http://127.0.0.1:8899/render-harness.html?...` 打开（render_server.py 已在 8899 提供静态服务），md/footer 给**相对 ROOT 的路径**（如 `md=_tmp_magistrala.md&footer=_combined_footer.html`）。渲染驱动用 Playwright `goto` 该 URL，`domcontentloaded` + 轮询 `window.__saved`。

### 坑 6：必须验证「保存后」图片真的持久化（重开草稿核对）

「保存时日志 `mmbiz:16`」**不等于**重开后还有图。本次踩坑：单粘贴/set_input_files 两种方式都出现过"保存时看着有图、重开 `mmbiz:0`、正文空 src"。**每次发布后，务必登录草稿箱打开该草稿，确认正文 `<img src=mmbiz>` 数量与发布时一致**。

草稿箱自动化导航很不稳定（见坑 7），人工在 mp 后台核对最可靠；若用脚本，记得：草稿列表卡片的"编辑"是**第 2 个 `weui-desktop-icon-btn`**（左起：删除/编辑/发表），且需 hover 后真实点击。

### 坑 7：草稿箱 SPA 导航不稳定，勿自动化清理

草稿箱（`type=77&action=list_card`）经常返回"暂无素材"空态，自动化打开/删除草稿不可靠，且曾误删正确草稿。删除重复草稿交由用户手动处理。

### 坑 8：渲染报「未保存」时的定位方法（index.js 依赖 / 代码级错误）

`render_article.py` 打印 `[FAIL] 渲染未保存` 时**不要反复重试**，直接抓浏览器 console：起 server → Playwright 打开 harness → 监听 `console` + `pageerror`（诊断脚本见 `references/publish_workflow.md` §H）。

两类真实原因（2026-09-08 一次连踩两个）：
- **`Failed to fetch dynamically imported module: .../src/render/index.js`（404）** → `src/render/index.js` 里**相对 import 少了 `.js` 扩展名**（如 `from '../config/headingStyle'`）。Vite 开发能解析，但 harness 是**纯浏览器 ES module + importmap、没有打包器**，必须写全 `'.js'`。修：补扩展名。
- **运行时 TypeError**（如 `insertBefore ... parameter 1 is not of type 'Node'`）→ 渲染代码 bug（某节点为 `null`），需加 null 保护。

> ⚠️ 06 是 Vite 项目：`src/` 下源码**只有带 `.js` 扩展名**的 import 才能在 harness 里跑。改动 `src/render/*` 后应立即用 `render_article.py` 回归一次再发文。
>
> 另：发布日志里的 `footer` 字段现已改为检测「关于作者」（v2 移除往期推荐后，旧的 `includes('往期推荐')` 会恒为 `false`，属误报）。

### 坑 9：文末「账号名片」+「合集」是微信编辑器原生插入，必须走对话框（2026-09-08 新增必做项）

用户 2026-09-08 要求：每篇文章文末加**账号名片【未来技术观察】** + 加入**合集【开源物联网平台】**。两者都是编辑器原生能力，`publish.py` 已自动做（`[9.5] 合集` → `[9.6] 账号名片`，顺序固定）。

**A. 合集（已验证稳定生效）**
- 触发点：`#js_article_tags_area .js_article_tags_label`（"未添加"那块，不是外层 div/label 文字）。
- 对话框标题「合集」，含 `input[placeholder='请选择合集']`；**必须先真实 `.click()` 该输入框打开下拉**，再 `.fill()`（仅 `evaluate` 设值下拉不弹）。
- 选项在 `.select-opts-con` 内，是 `LI.select-opt-li`（**内部有子节点**，`children.length<=1` 过滤会误排除 → 必须按 `.select-opt-li` 或 textContent 包含「开源物联网平台」来选，不可按叶子过滤）。
- 点选项 → 点 `button.weui-desktop-btn_primary`（确认）。成功标志：`#js_article_tags_area` 文本变为 `合集 开源物联网平台`。

**B. 账号名片（best-effort，依赖微信建议接口）**
- 触发：`更多`菜单 `.js_editor_showmore` → `LI#js_editor_insertProfile`（hover 下拉，用 JS `.click()` 打开，Playwright 动作点击会被 hover 关闭拦截）。
- 弹「插入账号名片」对话框；**选中的是搜索结果卡片 `.wx_profile_card`（含昵称 `.wx_profile_nickname`）**，不是「最近使用」的 `profile_history_item`（点了只出预览、不真正选中、插入按钮保持禁用）。
- 点卡片 → 点 `button.weui-desktop-btn_primary`（插入）即可插入到当前光标（步骤前已 `cursor_to_end()` 移到正文末尾）。
- ⚠️ **账号卡片来自微信「账号搜索建议」接口，偶发拉不到（`cards=0`，疑似限流/网络）** → 此时插入失败、仅 `[WARN]` 不阻断发布，需用户在编辑器手动补：`更多 → 账号名片 → 未来技术观察 → 插入`。

**顺序约定**：合集（可靠）放前、账号名片（可能残留对话框）放后，其残留对话框交给发布前 `safety` 块 `Esc` 关闭，避免干扰合集输入框。

## 发布验证清单

发布后检查 `/tmp/publish.log`：
- `[clicked 「继续插入」]` 出现（坑 1 已处理）。
- `paste via real clipboard: len>200 h2>0`。
- `heading bgs: ["rgba(0, 119, 182, 0.08)" × N]` 全部存在（背景已保留）。
- `mmbiz: N`（图片全部上传）、封面/原创/来源 `OK`。
- `[OK] 合集 set: 合集 开源物联网平台`（坑 9A 生效）；若 `[WARN] 合集 not set` 需在编辑器手动加合集。
- `[OK] 账号名片 inserted`（坑 9B 生效）；若 `[WARN] 账号名片 未检测到` 属微信建议接口限流，需在编辑器手动补「更多→账号名片→未来技术观察」。
- 最后 `[DONE]`。

详细代码与命令见 `references/publish_workflow.md`。
