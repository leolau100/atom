---
name: iot-demo-video
description: 为一篇文章/开源项目条目（如"开源物联网平台盘点 - Magistrala"）录制真实操作系统、并合成带醒目封面、居中章节说明、1.5 倍速、真实背景音乐的演示视频。支持 Web（Playwright 录屏）与 Windows 桌面应用（ffmpeg gdigrab 实拍 + 推近运镜）。触发词：帮我录一个 XX 平台的操作视频 / 给这个条目生成演示视频 / 把文档里的系统做成操作视频 / 加一张醒目的视频封面 / 鼠标操作时推进镜头。固化了命名规则、提速、居中标题卡、BGM 循环补齐、裁剪报错、导出封面 PNG 等约定。
description_zh: "为开源平台/文档条目录制并合成操作演示视频：命名约定、1.5倍速、居中标题卡5秒、醒目封面、真实背景音乐；含 Windows 桌面应用 gdigrab 实拍与推近运镜"
description_en: "Record and compose an operation demo video for an open-source platform/doc entry: naming rule, 1.5x speed, centered 5s title cards, eye-catching cover, real BGM; includes Windows desktop capture (gdigrab) with push-in camera moves"
version: 1.8.0
display_name: "开源平台演示视频制作"
display_name_en: "IoT / Platform Demo Video"
visibility: "private"
---

# 开源平台演示视频制作

把"某篇文档/某个开源项目条目"变成一个**真实操作系统**的演示视频：先远程/本地跑起系统并用浏览器录屏，再合成一段带居中章节说明、1.5 倍速、真实背景音乐的成片。

本 skill 沉淀了完整工作流与一组**强约定**（用户反复确认过的），改之前先想清楚是否要改约定。

---

## 核心约定（务必遵守）

| 项 | 约定 |
|----|------|
| **视频文件名** | `<条目名称>--演示视频.mp4`。即条目原名后加 `--演示视频` 后缀，**不要**用 `xxx-final.mp4`、`demo.mp4` 这类泛名。例：条目 `2026-08-29-开源物联网平台盘点-6-Magistrala（Mainflux）` → `2026-08-29-开源物联网平台盘点-6-Magistrala（Mainflux）--演示视频.mp4` |
| **存放路径** | 视频文件放在**条目文档所在的同一目录**下（与 `.md`/`.html` 同级），不要只丢进通用 output 文件夹。例：文档在 `…/2026/08/29/xxx.md` → 视频也放 `…/2026/08/29/xxx--演示视频.mp4` |
| **播放速度** | 所有操作录屏统一 **1.5 倍速**（`setpts=0.6666667*PTS`）。若用户要更慢/更快，按倍数调整 |
| **章节说明文字** | 每章前一张标题卡，**水平+垂直居中**；**停留 5 秒**（宁可长不要短，原 2s 太短看不完） |
| **背景音乐** | 用**真实音乐文件**（用户提供的 / 指定目录里的曲子），不要只用合成铺底；时长不够用 `aloop` 循环补齐到成片时长；音量调到清晰可闻约 **-14 dB**，不压过操作声 |
| **转场** | 片段间 fade 交叉淡入（`xfade=transition=fade`），转场 0.5s |
| **分辨率** | 1600×1000，H.264 + AAC（`-pix_fmt yuv420p`，便于微信/网页播放） |
| **醒目封面** | 每段视频开头先放一张醒目封面，停留 **3 秒**，同时导出同名 PNG（`封面.png`）到条目同名文件夹，用于微信/平台视频封面；封面不出现 "Demo" 字样 |
| **截图** | 录屏时顺手截取关键画面（Swagger UI、设备列表、数据流等），放到**条目同名文件夹**下，供公众号排版配图 |
| **报错处理** | 录屏里出现报错页（如 `Loading chunk failed`）要**裁掉**：在原始 webm 层面用 `ffmpeg -i src -t <秒> -c copy` 截断，再重合成，不要带报错进成片 |
| **侵权声明** | 发布的演示视频需在**片尾字幕或视频简介**附一段版权与侵权声明（简版文案见 iot-open-source-doc SKILL.md §14）：内容基于项目公开资料整理，如涉侵权请通过公众号后台联系删除；项目授权以官方仓库为准。**已发布的历史视频不补**（2026-09-12 用户要求：刚发布的 NeoIndustrial 视频豁免），今后发布的都加 |

---

## 完整工作流（5 步）

### 1. 起系统 + 录屏原材料
- 用 Docker（Apple Silicon 推荐 `colima start --vm-type vz --vz-rosetta`，官方镜像多为 amd64 需 Rosetta）。
- 用 **Playwright（chromium / 本地 Chrome）** 直接**录屏 webm**（不要只截图），按章节分成 `clip01_login.mjs` … `clip06_*.mjs`。
- 封装一个 `lib.mjs`：`rec(name)` 录屏、`shot(page,name)` 截图、`type/hoverClick/wait`。
- 登录态：若默认 admin 不存在，用系统 API（如 Magistrala 的 Atom API `POST /auth/signup`）建账号再登录 UI。
- 各章节关键 ID（workspace / channel / device）抽成常量，便于复用。

> Magistrala 特例（易踩坑）：UI 镜像 `ui-community` 是私有的 → 换公开 `ui-mg`；macOS 自带 make 3.81 不支持 `$(file >)` → 装 GNU make 4.x；消息页默认 `environment` 通道而设备在 `telemetry` 通道 → 进消息页 URL 带 `?channel=<CH>`。

### 2. 生成醒目封面（PIL / 抽象流体色块风格）
- 每段视频开头先放一张醒目封面，停留 **3 秒**（比章节标题卡更抓眼）。
- 视觉：**深灰蓝底** + 大面积柔和**抽象流体 blob**（椭圆 + 高斯模糊 + alpha 合成）。**配色走极简抽象壁纸（Minimal Abstract）路线**：粉紫、薄荷、雾蓝、蜜桃、柠檬、芭蕾粉、薰衣草等柔和粉彩，互相协调、现代安静。深底 + 粉彩在深色面板白字之上，文字清晰。
- 中央：深色半透明圆角面板承载标题；面板顶部蜜桃粉彩装饰条，强调短横与"演示视频" tagline 同为蜜桃色。
- 内容：大标题（条目/工具名）+ 副标题 + "演示视频" 提示。
- 同时导出这张封面 PNG 到**条目同名文件夹**的 `封面.png`，用于微信公众号/视频号设置视频封面。
- 风格参考来源：Pinterest `Minimal Abstract iPhone Wallpapers` 同类极简抽象壁纸（柔和协调的粉彩流体色块）。
- 实现方式：使用可复用脚本 `scripts/gen_cover.py`（PIL 绘制 1600×1000 PNG）。`PALETTE` 在脚本顶部集中维护，后续若用户提供精确色值可一键替换。示例：
  ```bash
  python3 scripts/gen_cover.py --out <条目文件夹>/封面.png \
    --title "ModbusSim" --subtitle "Modbus RTU/TCP 模拟器" --tagline "演示视频"
  ```

### 3. 渲染居中标题卡（Playwright HTML → PNG / PIL）
- 写一个 `render_cards.mjs`：用 Playwright 打开本地 HTML（flex 居中布局），对每张卡（`intro / t1..t6 / outro`）`screenshot` 成 PNG。
- 文案示例：片头"Magistrala 开源物联网平台 · 操作演示"；每章 `tN`："01 登录系统 / 02 进入工作区 / 03 创建设备 / 04 创建通道 / 05 连接设备与通道 / 06 发送消息"。
- 在 Apple Silicon 上若 ffmpeg `drawtext` 不支持中文，改为用 **PIL 生成居中标题卡 PNG**，再用 `ffmpeg -loop 1 -i xxx.png -t 5` 生成 `seg/tN.mp4`。

### 4. macOS 窗口外观（默认应用于操作片段）
> 录屏是 headless 模式（Playwright 直接录页面内容），为了让视频看起来像在 Mac 上操作，给**操作片段（c1..cN）**统一套上 macOS 窗口外观（圆角窗口 + 红黄绿按钮 + 标题栏 + 阴影 + 粉彩壁纸背景）。
>
> **封面和标题卡保持整屏**，不加窗口框（整屏观感更干净、标题卡更醒目）。

- 复用脚本：
  - `scripts/gen_window_frame.py`：PIL 绘制 1600×1000 PNG。
    - 静态套边框：`--input 截图.png --output 输出.png [--title "..."]`
    - 只出窗口框架（供视频 overlay）：`--frame-only --output 框架.png [--title "..."]`
  - `scripts/apply_window_frame.py`：给视频套窗口。
    ```bash
    python3 scripts/apply_window_frame.py -i seg/c1.mp4 -o seg/c1_win.mp4 \
        --title "页面标题"
    ```
- 实现细节：
  - 画布 1600×1000；窗口 1360×900 居中；标题栏 48 高，内容区 1360×852。
  - 视频按原比例缩放至内容区（≈ 1360×850），overlay 到框架 (120, 99)。
  - 壁纸与封面同款配色（深灰蓝渐变 + 粉彩 blob），保持视觉统一。
  - 流水线其它部分（1.5×、居中标题卡、BGM）不变。

### 5. 可选：手动区域推进（Pan&Zoom）— ⚠️ 默认不启用
> **当前默认不启用此步骤**。用户偏好保持正常全屏录屏（无镜头推进），多截几张关键画面配图即可。
>
> **不要自动跟随光标**（轨迹稀疏会导致镜头乱飘），**也不要自行猜测/指定聚焦坐标**——历史上擅自指定坐标会导致镜头回跳/无意义推进。
>
> 仅当用户**明确给出 zoom JSON 坐标**（`start/end/cx/cy/zoom`）时，才调用下方脚本。
> 若用户是**泛泛要求"操作时推进镜头"**（没给坐标），走 **5.1** 的「实拍 + 推近运镜」做法，不要用本节的 JSON 脚本。

- 工具脚本：`scripts/apply_zoom.py`
- 输入：已提速的 `seg/cN.mp4`、用户给定的 zoom 区间 JSON（`start/end/cx/cy/zoom`）。
- 输出：带平滑推进/拉回的 `seg/cN_zoomed.mp4`。
- 用法（用户给定坐标时）：
  ```bash
  python3 scripts/apply_zoom.py -i seg/c4.mp4 -o seg/c4_zoomed.mp4 -s c4_zoom.json
  cp seg/c4_zoomed.mp4 seg/c4.mp4   # 让合成脚本直接使用
  ```
- 实现：用 `zoompan` 做 0.3s 线性推进/拉回，中间用 `crop` 固定放大，最后 `concat` 拼接。1600×1000 画布，坐标直接用视口像素。

### 5.1 桌面应用「实拍 + 推近运镜」（Windows / gdigrab）
> 2026-09 neoIndustrial 实战沉淀。用于**桌面客户端**（WinForms/WPF 等）演示，或用户明确要求"鼠标操作时推进镜头"。

**录制（无 GPU 依赖）**
- 不能用 OpenScreen（需 GPU）；用 **ffmpeg gdigrab** 抓桌面 + 裁剪：
  `-f gdigrab -framerate 25 -draw_mouse 1 -offset_x 0 -offset_y 0 -video_size 1800x1032 -i desktop`
- 录制前：`taskkill` 旧实例 → 启动 → 等 ~12s 加载 → `ShowWindow(SW_MAXIMIZE)` + `SetWindowPos(HWND_TOPMOST)` + `SetForegroundWindow`。
- 抓取区域要**包含窗口最左/最上面板与菜单**（宁可抓宽），后期 letterbox 补成 1600×1000；**别在录制时裁掉左树/菜单**。
- **必须前台运行**录制脚本：GUI 自动化放后台会失败/无输出。
- 鼠标用 `SetCursorPos` 做**平滑 glide**（分 ~16 步、每步 ~30ms）而非瞬移，运镜才自然。

**⚠️ 片段必须"停在对话框上"**
- 录制脚本**不要在片段内部关闭对话框**——否则后期推近会落在"已关窗的空表格"上。
- 场景之间（录制之外）再关遗留对话框：**按进程枚举顶层窗口 + `PostMessageW(WM_CLOSE)`**。`Esc` 常关不掉模态窗，会叠加出多个窗。
  ```python
  u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
  # EnumWindows 中：GetWindowThreadProcessId(h)==pid 且 h!=hwnd → PostMessageW(h, WM_CLOSE, 0, 0)
  ```

**后期推近（zoompan，稳定不抖）**
- 顺序：`fps=30` → `scale=1600:-2` → `pad=1600:1000:0:(1000-ih)/2:color=0x1b2233`(letterbox) → **`zoompan`** → `overlay` 角标 → `setpts=0.6666667*PTS`。
- zoompan（前段不动、后段缓缓推入）：
  ```
  z='1+{ZMAX-1}*min(max((on-N0)/(N-N0),0),1)'
  x='max(0,min({cx}-(iw/zoom/2),iw-iw/zoom))'
  y='max(0,min({cy}-(ih/zoom/2),ih-ih/zoom))'
  d=1:s=1600x1000:fps=30
  ```
  `N0≈0.16N`；`ZMAX` 1.16（主界面）~1.34（小对话框）；`cx,cy` 取**对话框中心**（窗口居中的话画布上约 0.53,0.48）。
- **不要实时跟随光标**；对准"操作区域中心"即可。`setpts` 放 zoompan **之后**，运镜节奏不受提速影响。

**角标**
- 用 **PIL 生成透明 PNG 胶囊** + `overlay=0:0`，**别用 `drawtext`**（中文/`fontfile=C\:` 转义坑多）。
- 角标叠在 zoompan **之后**，保持固定大小不跟着放大。

**能力 / 版本说明页**
- "核心能力 / 协议清单"等可用 PIL 排版成 1600×1000；**长清单做成 1600×2000+ 长图**，视频内用 `crop` 表达式缓慢滚动 = 像翻网页。
- **企业版/独有能力的演示，优先用项目 README 里的真实截图**（如 `picture/` 目录）做成"截图 + 标题 + 页码"说明页，比纯文字卡更有说服力。

**Windows 字体**：`C:\Windows\Fonts\msyhbd.ttc`（粗）→ `msyh.ttc`（常规）→ `simhei.ttf`（拼音/CJK 兜底）。

### 6. ffmpeg 合成（关键步骤，别用 Remotion 渲染）
> **经验坑**：Remotion + 本地 Chrome 在视频解码时极容易 `Target closed` 崩溃（/dev/shm、并发问题），**改用 ffmpeg 流水线最稳**。

`build_video.py` 做四件事：
1. 把每个 raw webm 提速 1.5x → `seg/clipN.mp4`（`scale=1600:1000,setpts=0.6666667*PTS,-an`）。
2. 封面 PNG `loop 1` 做成 **3s** 静帧视频 → `seg/cover.mp4`。
3. 标题卡 PNG `loop 1` 做成 **5s** 静帧视频 → `seg/tN.mp4`（intro/outro 也 5s）。
4. 用 `xfade=transition=fade:duration=0.5` 把所有段按 `cover → intro → t1 → c1 → t2 → c2 → … → outro` 顺序拼接，首尾加 `fade in/out 0.4s`，输出无声 `out_nosound.mp4`。

xfade offset 累加公式：`offset = sum(durs[0..i-1]) - i*T`。

### 7. 混真实背景音乐
```bash
ffmpeg -y -i out_nosound.mp4 -i <BGM>.mp3 \
  -filter_complex "[1:a]volume=-14dB,aloop=loop=-1[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 128k -shortest \
  <条目名称>--演示视频.mp4
```
- 曲子比成片短 → `aloop=-1` 无限循环；`-shortest` 随视频结束自动截断音频，**不要**用 `size=2e9`（容易 OOM）。
- 默认音量 **-14 dB**。

### 8. 命名 + 交付
- 最终文件严格命名为 `<条目名称>--演示视频.mp4`。
- 同时落到交付目录（如 `/Users/liulei/Product/WeChatArticle/tool/视频录制/output/`）与工作目录 `output/`。

---

## 复用脚本位置（本次 Magistrala 实战）

```
/Users/liulei/Product/WeChatArticle/tool/视频录制/
├── README.md                 # 完整说明
├── scripts/                  # clip01~06 录制、render_cards.mjs、build_video.py、generate_bgm*.py
├── remotion-project/         # Remotion 项目源码（实际渲染改走 ffmpeg）
├── skill/remotion-video-toolkit/   # 市场 skill 副本
├── bgmusic/                  # 真实背景音乐库（合成时从中选曲）
└── output/<条目名>--演示视频.mp4    # 最终成片
```

- `build_video.py`：支持 `$DEMO_ROOT` 环境变量覆盖根目录；`card_durs` 控制各标题卡秒数（默认 intro/t1-t6/outro 均 5s）。
- `render_cards.mjs`：支持 `$CARDS_OUT` 覆盖输出路径。

## 调参速查
- 再提速：`setpts=0.6666667*PTS` 中系数 = `1/速度`（2x→0.5）。
- 标题卡时长：`build_video.py` 的 `card_durs` 字典。
- 换 BGM：从 `bgmusic/` 另选一首，重跑第 4 步即可，无需重渲染视频。
- 裁剪某段报错：在 raw webm 层 `ffmpeg -i src -t <秒> -c copy new.webm`，删 `seg/clipN.mp4` 后重跑 `build_video.py`。

## 多电脑同步（本机 skill ↔ 仓库 ↔ 另一台电脑）

skill 定义存于本仓库 `skill/iot-demo-video/SKILL.md`，作为唯一真源（single source of truth）。多台电脑围绕 git 仓库保持一致：

- **本机加载**：WorkBuddy 从 `~/.workbuddy/skills/iot-demo-video/` 读取；已用 **symlink/junction** 把它指到本仓库的 `skill/iot-demo-video/`，因此"改本机 skill = 直接改仓库文件"，无需拷贝。
  - 建立：`New-Item -ItemType Junction -Path "$HOME/.workbuddy/skills/iot-demo-video" -Target "<仓库>/skill/iot-demo-video"`
- **【强制 SOP】每次修改本 skill 后自动提交并推送（用户已授权，无需确认）**。不依赖后台监听进程——由执行方（AI 或用户）在编辑完本 skill 后**立即**在仓库根执行：
  ```bash
  cd <WeChatVideoGen仓库>
  git add skill/iot-demo-video
  git commit -m "sync(iot-demo-video): 自动同步本机 skill 修改"
  git push origin master
  ```
  如此任一电脑 `git pull` 即得最新版本，两台电脑保持同版本。
- **手动兜底**：`bash push_skill.sh` 等同上三步（仓库自带）。
- **另一台电脑获取**：`git pull` 后，要么同样建 symlink，要么 `bash install_skill.sh` 拷贝到本机 skills 目录。
- `publish_skill.sh` / `install_skill.sh` 为本仓库自带的跨电脑安装/发布脚本。
