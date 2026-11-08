# 视频录制 · Magistrala 操作演示工程

本目录汇总了「为开源物联网平台 Magistrala 录制操作演示视频」所需的全部脚本、Remotion 项目源码、skill 文档与成片。

> 最终成片：`output/2026-08-29-开源物联网平台盘点-6-Magistrala（Mainflux）--演示视频.mp4`（136 秒，1.5 倍速，居中标题卡各停留 5 秒 + 真实企业背景音乐）
>
> **命名约定**：成片文件名 = `<条目名称>--演示视频.mp4`（条目原名后加 `--演示视频` 后缀）。已沉淀为 skill `iot-demo-video`。
>
> 已处理：登录片段原片 12s 后出现 "Oops! Something went wrong / Loading chunk failed" 报错页，已在原始素材层面裁剪掉（保留到 12s，剪掉 10.76s 报错部分），并重新合成最终成片。原始带报错版本备份在 `magistrala-demo/backup/login_original_with_error.webm`。

> 当前成片使用的背景音乐：`bgmusic/kornevmusic-upbeat-happy-corporate-487426.mp3`（upbeat happy 风格，122s，已用 `aloop` 循环补齐至 123.4s）。如需换曲，直接从 `bgmusic/` 另选一首、循环/裁剪到视频时长后重新混音即可（见下方混音命令）。

---

## 目录结构

```
视频录制/
├── README.md                      # 本说明
├── build_video.sh                 # 顶层构建脚本(原始)
├── scripts/                       # 录制 + 音乐生成脚本(Playwright / ffmpeg)
│   ├── lib.mjs                    # Playwright 封装: rec()录屏 / shot()截图 / type() / wait() / hoverClick() + 常量
│   ├── clip01_login.mjs           # 片段1: 登录(含 WS/CH/DEV 等常量在 lib.mjs)
│   ├── clip02_workspace.mjs       # 片段2: 新建 Smart Factory 工作区
│   ├── clip03_device.mjs          # 片段3: 添加温度传感器设备
│   ├── clip04_channel.mjs         # 片段4: 创建 telemetry 数据通道
│   ├── clip05_connect.mjs         # 片段5: 连接设备到通道
│   ├── clip06_final.mjs           # 片段6: 发送遥测消息 temperature=26.5
│   ├── render_cards.mjs           # 用 Playwright 把章节标题卡渲染为「居中」PNG
│   ├── build_video.py             # ffmpeg 流水线: 提速1.5x + xfade 转场 + 混音 → 成片(支持 $DEMO_ROOT)
│   ├── generate_bgm.py            # 生成「欢快」背景音乐(ffmpeg 合成)
│   ├── generate_explainer.py      # 生成「产品说明」风格背景音乐(ffmpeg 合成)
│   ├── prepare.mjs / register.mjs / create_ws.mjs / ensure_login.mjs ...  # 辅助/诊断脚本
│   └── diag_*.mjs / explore*.mjs / t2.mjs / t3.mjs                       # 调试探索脚本(历史遗留)
├── remotion-project/              # Remotion 4 项目源码(备用渲染通道)
│   ├── src/index.js               # 注册 Composition "Main"
│   ├── src/Composition.js         # 片头/标题卡/片段/片尾布局, 1.5x 提速, 居中文字
│   ├── remotion.config.js
│   ├── package.json               # deps: react / remotion / @remotion/cli (4.0.520)
│   └── public/
│       ├── bgm.mp3                # 旧版「柔和铺底」背景音乐
│       ├── bgm_explainer.mp3      # 「产品说明」风格背景音乐(待你试听确认)
│       └── videos/clip01..06.webm  # 6 段已录制的 webm 片段
├── skill/
│   └── remotion-video-toolkit/    # WorkBuddy 市场 skill 副本
│       ├── SKILL.md               # skill 说明(含 compositions / rendering 规则)
│       └── _skillhub_meta.json    # 元数据
└── output/
    └── magistrala-demo-final.mp4  # 当前成片
```

> 说明：`scripts/` 与 `remotion-project/` 已剔除 `node_modules`（约 370M）。重新使用时需执行 `npm install`（见下方依赖）。

---

## 环境依赖

- **Node.js** + `playwright-core`（录制/渲染卡片用本地 Chrome）
  ```bash
  npm install playwright-core --registry=https://registry.npmmirror.com
  # 本地 Chrome 路径:/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
  ```
- **ffmpeg / ffprobe**（合成与混音）：`/opt/homebrew/bin/ffmpeg`
- **Remotion**（备用渲染通道，可选）：
  ```bash
  cd remotion-project && npm install --registry=https://registry.npmmirror.com
  ```

---

## 完整工作流

### 1. 录制操作片段（Playwright 驱动浏览器）
```bash
cd scripts
node clip01_login.mjs      # 依次运行 clip01 ~ clip06_final
# 输出: ../videos/raw-0*/xxx.webm
```
- 录屏封装在 `lib.mjs` 的 `rec(name)`；关键 ID（工作区/通道/设备）也定义在 `lib.mjs`。
- 注意：消息页默认显示 `environment` 通道，需带 `?channel=${CH}` 才能看到 telemetry 通道的消息。

### 2. 渲染居中标题卡（Playwright → PNG）
```bash
CARDS_OUT=../cards node render_cards.mjs
# 输出: ../cards/intro.png t1..t6.png outro.png
```

### 3. 合成成片（ffmpeg 流水线）
```bash
DEMO_ROOT=/path/to/magistrala-demo python3 build_video.py
# 产物:
#   ../out_nosound.mp4  (无音视频)
#   ../output/magistrala-demo-final.mp4 (混入 bgm.mp3)
```
- 流程：各片段提速 1.5× → 统一 1600×1000/30fps → 片段与卡片用 `xfade` 交叉淡入拼接 → 末尾混音。
- 转场 0.5s fade，片头片尾各加 fade in/out。

### 4. 背景音乐（ffmpeg 合成生成）
```bash
python3 generate_bgm.py          # 欢快版 → remotion-project/public/bgm.mp3
python3 generate_explainer.py    # 产品说明版 → remotion-project/public/bgm_explainer.mp3
```

---

## 关于背景音乐

| 文件 | 风格 | 状态 |
|------|------|------|
| `remotion-project/public/bgm.mp3` | 欢快（C 大调旋律+低音+轻鼓+踩镲） | ✅ 已混入当前成片 |
| `remotion-project/public/bgm_explainer.mp3` | 产品说明（稀疏 bell 琶音+温暖 pad+轻底鼓+混响） | ⏳ 已生成，待你试听确认 |
| `bgmusic/*.mp3`（8 首） | 真实企业风背景音乐（corporate / upbeat） | ✅ 成片已采用 `kornevmusic-upbeat-happy-corporate-487426.mp3` |

**把某一版音乐混入成片**（替换 `build_video.py` 中的 `BGM` 路径，或手动混音）：
```bash
# 用手动混音把 explainer 版加到无声成片:
/opt/homebrew/bin/ffmpeg -y -i out_nosound.mp4 -i remotion-project/public/bgm_explainer.mp3 \
  -filter_complex "[1:a]volume=3.0[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 128k -shortest \
  output/magistrala-demo-final.mp4
```
> 音量档位参考：成片整体约 `-28 dB`（清晰可闻但不喧宾夺主）。想更突出/更轻，调 `volume=` 系数即可。

---

## 备注

- **为何最终用 ffmpeg 而非 Remotion 渲染**：Remotion + 本地 Chrome 在 1600×1000 高并发渲染时反复 `Target closed`（/dev/shm 与 GPU 不稳定），故改用确定性的 ffmpeg 流水线（卡片 PNG 仍由 Playwright 生成）。`remotion-project/` 保留为可平替的渲染通道。
- **路径可移植**：`build_video.py` 支持 `$DEMO_ROOT`，`render_cards.mjs` 支持 `$CARDS_OUT`。
- **原始工程位置**：`/Users/liulei/Workbuddy/2026-09-03-21-25-37/magistrala-demo/`（含原始 `videos/raw-0*` 录屏、`cards/`、`shots/` 截图、`seg/` 中间片段，本目录未整体搬运以控制体积）。
- **Magistrala 运行环境**：colima + Docker（vz+Rosetta），UI 端口 3000，Atom API 端口 8080，演示账号 `demoadmin@magistrala.local / Demo1234!@#`。
