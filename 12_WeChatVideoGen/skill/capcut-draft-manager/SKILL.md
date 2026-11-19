---
name: capcut-draft-manager
description: |
  管理 macOS 版剪映专业版（JianyingPro / CapCut 中国版 10.x）的本地草稿工程。
  适用于：列出所有草稿、查看草稿路径与占用、复制草稿做副本、以某个成品草稿
  为模板生成新书/新项目模板、修改草稿标题或时间线里的书名、备份整个草稿库、
  查看草稿引用的素材、替换配图、把背景图/背景音乐等轨道对齐到字幕与配音的
  总时长、批量对齐字幕的字号/缩放/位置/样式、限制字幕文本框最大宽度与折行数、
  重做草稿封面（含草稿箱缩略图）、改完草稿后重开剪映并置顶。
  当用户说「剪映草稿」「复制草稿」「草稿改名/改标题」「草稿在哪」
  「备份我的剪辑工程」「以某某草稿为模板生成新草稿」「十分钟读完一本书下一本」
  「把背景图/BGM 裁到和字幕配音一样长」「时长对齐」
  「字幕字体大小/缩放/位置不对」「字幕样式被重置」
  「字幕宽度没调」「字幕折行太多/换行好几次」「字幕挡住光盘了」
  「封面怎么又变回上一本书了」「草稿箱封面不对」时使用本技能。
  脚本入口 scripts/jy_draft.py，自带 jy-draftc 加解密二进制，
  不依赖任何外部仓库。
---

# 剪映草稿管理（macOS · WorkBuddy 版）

## 零、路径与环境变量（换机器先看这里）

脚本不绑定用户名，换电脑/换路径只需设环境变量，不必改代码：

| 变量 | 作用 | 默认值 |
|---|---|---|
| `JY_DRAFT_ROOT` | 剪映草稿库根目录 | `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft` |
| `JY_APP` | 剪映 App 路径 | `/Applications/VideoFusion-macOS.app` |
| `BOOK_ROOT` | 文章仓库根目录（`jy_draft.py covers` 找封面模板与输出位置用） | `~/Product/WeChatArticle/十分钟读完一本书` |

另外 `jy_draft.py` 多数子命令都接受显式参数（`--article-root` 等），可临时覆盖。
推荐在 shell 里统一导出：

```bash
export BOOK_ROOT="$HOME/Product/WeChatArticle/十分钟读完一本书"
export SKILL_DIR="$BOOK_ROOT/skills/capcut-draft-manager"   # 或装到 ~/.workbuddy/skills/capcut-draft-manager
```

依赖：macOS（Quartz/pyobjc 通常系统自带）、`python3`、`magick`(ImageMagick，生成文章封面用)、
`ffprobe`(校验成片)。`scripts/bin/jy-draftc-mac` 为本机（Apple Silicon）预编译二进制，
换到 Intel Mac 需自行编译或从剪映 App 内提取对应工具。

## 一、底层事实（2026-11-14 在本机 10.3.0 实测校准）

剪映草稿 = **一个目录 + 一份全局明文索引 + 目录内的加密工程包**。

| 对象 | 路径 | 形态 |
|---|---|---|
| 草稿根目录 | `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft` | — |
| **全局索引** | `<根目录>/root_meta_info.json` | **明文 JSON**，可安全读写 |
| 草稿目录 | `<根目录>/<草稿名>` | 含素材、时间线、封面 |
| 工程主体 | `<草稿目录>/draft_info.json` | **加密**（base64 密文） |
| **工程副本** | `<草稿目录>/Timelines/<content_id>/draft_info.json` | **加密**，剪映以它为准并回写根目录 |
| 草稿元信息 | `<草稿目录>/draft_meta_info.json` | **加密**，内含 `draft_id` / `draft_name` / `draft_fold_path` / 云同步字段 |
| 时间线配置 | `<草稿目录>/Timelines/project.json` | 明文，但**只有** `config/id/main_timeline_id/timelines/version`，**不含素材路径** |
| 封面 | `<草稿目录>/draft_cover.jpg` | 二进制 |
| 密钥库 | `<草稿目录>/crypto_key_store.dat` | 二进制，**必须随目录一起复制** |
| 配音音频 | `<草稿目录>/textReading/*.wav` | 二进制，草稿会引用，不要删 |

`root_meta_info.json` 顶层只有 `root_path` / `draft_ids` / `all_draft_store` 三个键；
`all_draft_store[]` 每条含 `draft_id`、`draft_name`、`draft_fold_path`、
`draft_json_file`、`draft_cover`、`draft_root_path`、`tm_draft_create`、
`tm_draft_modified` 以及一组云同步字段。`draft_ids` 可能与实际条目数漂移，
**写操作一律重算为 `len(all_draft_store)`**。

草稿箱按 `tm_draft_modified` 倒序（`homePageLocalModifyTimeSortOrder=true`），
新条目应 `insert(0)` 并刷新时间戳才能排第一。

> **关键修正（相对旧版认知）**：加密的 `draft_meta_info.json` 里确实存了
> `draft_id` / `draft_name` / `draft_fold_path` / 云字段，剪映会读取它。
> 只改外层索引会产生「半校准」副本：内层 id 与源草稿撞车、改名后被改回、
> 副本去拉云端状态。本技能通过自带的 `jy-draftc` 解密→改→加密回写，
> 把内外两层一起对齐。素材路径在加密的 `draft_info.json` 的
> `materials.*.path` 里，且常用 `##_draftpath_placeholder_…##` 相对引用，
> 必须还原成草稿目录内的真实路径才能判断是否存在。

## 二、铁律

1. **写操作前必须让剪映完全退出**。剪映运行时会锁草稿 JSON 并把内存状态回写磁盘，
   覆盖外部改动。本技能默认**自动**完全退出（`osascript quit` 常被
   `minimize_to_tray_when_app_quit=true` 吞掉，`open_draft.py` 会 `pkill` 兜底）。
2. **写操作完成后自动重开剪映并把目标草稿置顶**（用户 2026-11-09 明确要求，
   不要让用户自己退出/重开/找草稿）。`--no-reopen` 可关闭。
   当前无「辅助功能」与「屏幕录制」权限，只能做到「窗口打开 + 草稿第一位」，
   无法自动双击进入编辑界面；若将来授权，`open_draft.py` 会用 AXPress 直达。
3. **改索引前必须备份**，自动写为 `root_meta_info.json.bak.<时间戳>`；
   索引用 `os.replace` 原子写回。
4. **绝不手工编辑加密文件**，只能通过 `scripts/bin/jy-draftc-mac` 解密→改→加密。
   两份 `draft_info.json`（根目录 + `Timelines/<content_id>/`）都要改，
   否则剪映会用时间线副本覆盖根目录。
5. **content id 必须保持不变**，与 `Timelines/<content_id>` 目录名一致，不要换新 uuid；
   要换的是 `draft_id`（外层索引 + 内层 meta 同步换成同一个新大写 UUID）。
6. **整目录复制**，含 `crypto_key_store.dat`、`Resources/`、`Timelines/`、
   `textReading/`、`common_attachment/`。只跳过纯备份/临时文件
   （`.backup/`、`*.bak*`、`*.tmp`、`template-*.tmp`），它们不含素材引用。
7. **新副本的云同步字段必须置空**，内外两层都要清，否则副本会去拉云端状态。
8. **改书名只替换精确等于书名的标题文本**（如 `《小王子》`），
   不要全局替换正文里出现的同名文字；同时同步 `styles[].range` 到新长度。
9. **删除草稿**不走本技能；如需删除，先让用户确认，且删除后同步从
   `all_draft_store` 移除条目并重算 `draft_ids`。
10. 完成后如实报告，**不要声称「已在剪映里验证」**，除非真的打开看过。

## 三、标准流程

### 固定分工（用户 2026-11-14 明确，以后每本书都按此执行）

> 用户原话：「以后我处理音频和生成字幕，你负责帮我修改位置、标题、图片、封面等信息」。

| 谁 | 负责范围 |
|---|---|
| **用户**（剪映里手工） | 生成配音音频（TTS）；生成/导入字幕正文 |
| **Agent**（本技能） | 字幕的**位置 / 缩放 / 字号 / 行间距 / 描边等样式 / 文本框宽度与折行**；时间线书名标题与草稿名；背景图 / 配图生成与替换（含右下角去 AI 标识）；封面（全量同步）；背景图 / 贴纸 / 顶部标题 / BGM 对齐到字幕+配音总长；**收尾生成文章仓库的手机竖版 + 电脑横版封面双图**；改完自动重开剪映并置顶 |

边界与默认动作：

- **不生成配音；对用户手工做的字幕不改动正文**。文字内容 / `words` / `current_words` / `text_to_audio_ids` / `group_id` / 片段 ID 一律不动。**例外（用户 2026-11-16 更新）**：agent 全流程自动生成的字幕（§八 TTS/SRT 链路，`inject_srt.py` 产出、无逐字绑定），由 `fix-subtitles` 的 flat 默认去掉硬换行、**保留标点**、一整句一行（仅显式 `--strip-punct` 才去标点）；配音按整段 wav 对齐不受影响，见 §F6。旧的 23 字插 `\n` 折行已被 flat 覆盖，仅在显式 `--max-chars` 时启用。
- 用户也可能用「导入 SRT + 一整条外部旁白 wav」的方式做音频字幕（2026-11-14《住小房子的女人》即此形态），与 TTS 分段字幕结构不同：字幕 `font_size` 字段存在、`fixed_width` 不存在、文本无 `\n`。按 §F4 / §F5 / §F6 的兼容规则处理，不要套用 TTS 草稿的写死假设。
- 用户做完 TTS 后剪映会重置字幕样式（`scale=1.0`、位置归零、行间距 0.02、丢描边字体）并新增 `fixed_width`、硬插换行 → **每次用户说「音频/字幕做好了」，默认按序执行**：
  1. 按铁律 1 完全退出剪映；
  2. `fit-duration -s <草稿>`（对齐铺底轨道与 BGM 到字幕+配音总长，字幕/配音轨不动）；
  3. `fix-subtitles -s <草稿> --from 小王子`（样式 + 默认 flat：去硬换行、保留标点、一整句一行、宽度不变）；
  4. `fix-cover -s <草稿>`（若换书 / 换图 / 封面回退，必须全量同步，见 §F7）；
  5. 自动重开剪映并把目标草稿置顶（铁律 2）；
  6. **`covers -s <书名>`**：调用文章仓库两个封面脚本，输出手机竖版 + 电脑横版
     两张 png 到该文章 markdown 同文件夹（§H，用户 2026-11-14 明确「以后每次
     处理完之后」都要做，不要漏）。
- 一本书只生成一张主题插画，封面 = 同一张图 + 书名文字的派生结果（§F3）；不要为封面二次生图。
  §H 的两张是**公众号文章封面**（另一套模板、另一套脚本），与剪映草稿封面不是一回事，
  不违反「一张插画」约定。
- 用户偏好零操作：能脚本化的都脚本化，只在需要目视确认时请用户看一眼，不要求用户手动执行任何命令。

脚本统一入口（所有命令都支持 `--root` 覆盖草稿库路径）：

```bash
SK=${SKILL_DIR:-$HOME/.workbuddy/skills/capcut-draft-manager}/scripts/jy_draft.py
```

### A. 查草稿 / 查路径

```bash
python3 "$SK" list
```
输出草稿名、修改时间、占用、目录是否存在；`draft_ids` 漂移会显式提示。
草稿库路径默认 `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft`，可用 `JY_DRAFT_ROOT` 或 `--root` 覆盖。

### B. 复制草稿（做副本 / 生成下一本书的模板）

```bash
# 纯副本
python3 "$SK" copy -s "11月8日" -n "11月8日-横屏版"

# 以成品草稿为模板生成新书草稿：换书名标题 + 重生成封面（本系列常用）
python3 "$SK" copy -s "小王子" -n "明朝那些事" -t "明朝那些事"
```

`copy` 依次执行：自动退出剪映 → 备份索引 → 整目录复制 → 新大写 UUID →
**同步回写内层加密 meta** → 外层索引 `insert(0)` 并清空云字段、重算 `draft_ids` →
（可选 `--title`）替换两份 `draft_info.json` 里的标题文本并生成封面 →
自动重开剪映、把新草稿置顶。

`--title` 只改标题，**字幕正文、配音音频、配图仍沿用源草稿作为占位内容**；
这是刻意保留的可逆做法，后续用文案注入脚本替换即可。

### C. 改草稿标题

```bash
python3 "$SK" rename -s "11月8日 (1)" -n "双十一口播成片"
```
目录重命名 + 外层索引 + **内层加密 meta 同步**，因此不会再出现「剪映把名字改回去」。
源目录缺失时直接报错，不会把索引指向不存在的目录。

### D. 只改书名（不动草稿名）

```bash
python3 "$SK" retitle -s "明朝那些事" -t "明朝那些事儿"
```
改两份工程 JSON 的标题文本 + 重新生成封面。源书名默认取草稿名，
不一致时用 `--from-title` 指定。

### E. 备份整个草稿库

```bash
python3 "$SK" backup -d ~/Desktop/jianying_backup
```
复制到带时间戳的子目录；剪映运行时会给出「快照可能不一致」警告但不阻断。

### F. 查看素材引用

```bash
python3 "$SK" materials -s "小王子"
```
解密 `draft_info.json` 读 `materials.*.path`，把 draftpath 占位符还原为草稿内路径，
逐条标注 `[缺失]`。不再依赖不含路径的 `Timelines/project.json`。

### F2. 替换草稿里的背景图 / 配图（含去 AI 标识）

AI 生成的图右下角通常带「AI生成 / WORKBUDDY」标识，**本系列配图不得出现**。
`set-bg` 默认会自动清理，也可单独调用清理脚本：

```bash
# 一步到位：去标识 + 换图 + 重做封面 + 自动重开
python3 "$SK" set-bg -s "明朝那些事" -i /path/to/mingchao.png

# 只清理标识
python3 "$(dirname "$SK")/clean_ai_mark.py" \
    --in generated.png --out clean.jpg
```

`set-bg` 依次执行：自动退出剪映 → （默认）去右下角 AI 标识 → 图片存入草稿
`Resources/` → 解密改两份 `draft_info.json` 里所有 `materials.videos[].path`
的 `/Resources/*.jpg|png` 引用并同步 `width`/`height` → 加密回写 →
用新图作底重新生成封面 → 自动重开剪映、目标草稿置顶。

参数：`--old 旧文件名` 只替换指定旧图；`--filename` 指定存入的文件名；
`-t 书名` 指定封面文字；`--no-clean-mark` 图已无标识时跳过清理；
`--no-cover` 不动封面。

> 图片必须落在**草稿内部 `Resources/`**，并用
> `##_draftpath_placeholder_…##/Resources/xxx.jpg` 相对引用；
> 外部中文绝对路径会被剪映判「媒体丢失」。去标识采用
> 「邻近星场克隆 + 亮度匹配 + 只羽化左/上边界」，不要改回整块 inpaint
> （会留暗矩形）或纯文字阈值修复（会留浅色块）。
>
> 2026-11-14 修正：`make_cover.py` 原先的暗角 mask 方向写反，
> `Image.composite` 把整张底图涂成纯深色（当年为遮盖旧图右下角 AI 标识），
> 导致换底图前后封面像素完全一致、插画根本没显示。
> **现在按底图平均亮度自动分两套版式**（阈值 140）：
> 深色插画 → 压暗 0.42 + 底部渐变 + 反转暗角 + 白字；
> 明亮插画 → 轻微提亮 + 浅色柔光 + **深墨字白描边 + 暖棕系列名**，
> 绝不压暗。内嵌封面工程的模板字色也同步按亮度切换。
> 不要再改回纯色遮盖式封面，也不要在浅色图上用白字。

### F3. 一本书只生成一张图（用户 2026-11-14 明确约定）

**每本书只生成一张主题插画**（1536×1024，去右下角 AI 标识后存入草稿
`Resources/`）。草稿封面**不是第二张图**，而是同一张图叠加书名文字后的派生结果，
由 `make_cover.py` 自动生成到 `<草稿>/draft_cover.jpg`：

```text
主题插画（唯一一次图像生成）
   ├─ → Resources/<book>_bg.jpg   时间线 / 唱片背景
   └─ → draft_cover.jpg           同一张图 + 《书名》+ 系列名 + 署名
```

因此**不要为封面再调用一次图像生成**，也不要把这两个文件当成两张独立配图交付。
`copy -t` / `retitle` / `set-bg` 重做封面时，`make_cover()` 会通过
`current_bg(fold)` 自动读取草稿当前配图作为底图；**不要改成 skill 内置的
`assets/series_bg.jpg`（那是《小王子》的旧星场图）**，否则改书名会把本书插画覆盖掉。

> **主题不固定（用户 2026-11-14 明确）**：「怎么都是深色的背景呢」——
> 前几本都是深蓝星云/暗色油画，用户不喜欢。新书按书名换主题与色调，
> 默认走**明亮浅色**，生成 prompt 里要显式写
> 「不要深色背景 / 不要夜空 / 不要星云」。若风格方向不确定，先给用户
> 2–4 个选项再生成（生图有积分成本）。一本书仍只生成一张图。
>
> **颜色要鲜艳（用户 2026-11-15 明确）**：「生成视频的背景图片的颜色都太淡了，
> 以后要更鲜艳一些」。即**明亮 + 高饱和**，不是改回深色。现有三本亮色图实测
> HSV 平均饱和度仅 `S=0.074`（三体）/ `0.079`（遥远的救世主）/
> `0.178`（整理人生）、亮度 206~230 —— 这种「近乎灰白的淡彩」就是被否定的形态，
> 不要再用它当风格样板。
>
> **默认风格＝明亮高饱和的写实摄影（用户 2026-11-15 看样图后确认）**。
> 样图 `outputs/摄影风格样图.png`（湖蓝墙 / 明黄窗帘 / 橙红郁金香 / 摊开的书）
> 实测 `S=0.557 / V=0.778 / 亮度=165`。prompt 以「写实摄影、专业单反、自然日光、
> 浅景深、真实质感」开头，**不要再写插画 / 水彩 / 油画 / 绘画感**。
>
> **每张图必须体现书名（用户 2026-11-15 明确）**：不能交通用的「书 + 咖啡」静物。
> 按该书的**核心意象、场景、物件、时代与地域**定制摄影主体和主色，例如
> 《百年孤独》→ 热带小镇、香蕉园、黄蝴蝶、斑驳旧宅；《活着》→ 黄昏田野、老牛、
> 土屋；《月亮与六便士》→ 南太平洋、画室、调色板；《围城》→ 民国书房、城墙、
> 旧船票。构图统一：**主体偏右，左侧留大面积干净负空间**给模板的光盘和字幕；
> **背景图本身不带任何文字 / logo**，书名由 `make_cover.py` 在封面层叠加，
> 否则会出现双重书名。一本书仍只生成一张图。
>
> 生图 prompt 必须同时给出两类要求：
> - 正向：`写实摄影质感`、`高饱和度、色彩鲜明`、`大面积饱和色块`（按书名选，
>   如明亮湖蓝 / 靛青 / 橙金 / 翠绿 / 品红）、`色彩对比清晰`、`主体偏右左侧留白`；
> - 负向：`不要插画 / 水彩 / 油画 / 任何绘画感`、`不要文字 / 水印 / logo / 人物`，
>   加上 `不要低饱和 / 淡彩 / 灰白奶油滤镜 / 莫兰迪 / 雾蒙蒙泛白`，
>   并保留 `不要深色背景 / 夜空 / 星云`。
>
> **摄影图去 AI 标识必须用 `clean_ai_mark.py --mode clone`**（沿纹理方向水平
> 平移克隆 + 中位数亮度匹配 + 左边界羽化 14px，输出 `.png` 无损）。默认的
> 「亮底中值」模式会把木纹 / 织物横纹抹成明显模糊块，白色笔画 inpaint 也会留竖条；
> 只有水平克隆能让摄影纹理连续无痕。
>
> **验收量化**（生成后先跑，别等导出视频才发现问题）：把图缩到 200px，
> 算 HSV 均值，`S ≥ 0.32`（理想 0.35~0.50）且 `V ≥ 0.75`。
> `S < 0.30` 视为不合格，重生成而不是靠后期硬拉。
>
> **高饱和摄影图以 V 为准**：加权亮度 `lum` 会被大片饱和深蓝 / 深红天然拉低
> （《生死疲劳》配图 `S=0.738 / V=0.768` 达标，但 `lum` 仅 123），
> 别再用「lum ≥ 175」卡摄影图。若摄影图 V 不足，**不要做 RGB gamma**
> （提亮的同时会掉饱和、发白），只提 HSV 的 V 通道、S 通道原样保留：
>
> ```python
> import cv2, numpy as np
> h, s, v = cv2.split(cv2.cvtColor(cv2.imread(src), cv2.COLOR_BGR2HSV))
> v2 = np.clip((v.astype(np.float32)/255)**0.42 * 255, 0, 255).astype(np.uint8)
> out = cv2.cvtColor(cv2.merge([h, s, v2]), cv2.COLOR_HSV2RGB)  # 保存为 PNG
> ```
> 实测 V `0.585→0.768`、S `0.726→0.738`，颜色不褪、无失真。
>
> ```python
> from PIL import Image
> import colorsys
> im = Image.open(path).convert('RGB'); im.thumbnail((200, 200))
> hs = [colorsys.rgb_to_hsv(*[c/255 for c in p]) for p in im.getdata()]
> S = sum(h[1] for h in hs)/len(hs); V = sum(h[2] for h in hs)/len(hs)
> # 合格线：S >= 0.32 且 V >= 0.75
> ```
>
> **后期增艳只能当补救**：对同一张图调色不算「第二张插画」，不违反 F3。
> 但实测 `ImageEnhance.Color(2.0)` 只把 `S` 从 0.074 抬到 0.144，
> HSV 只提 S 通道（`S*1.9 + 0.10`）也只到 0.234，都拉不出真正的鲜艳、还容易发脏。
> 所以**优先在生图阶段解决**；仅当旧图必须复用时才轻调，不要拿它当常规手段：
>
> ```python
> h, s, v = Image.open(src).convert('HSV').split()
> s = s.point(lambda x: min(255, int(x*1.6 + 0.06*255)))
> Image.merge('HSV', (h, s, v)).convert('RGB').save(dst, quality=95)
> ```
> 调完走 `jy_draft.py set-bg -s <书名> -i <增艳图>`，再 `fix-cover` / `covers` / `reopen`。

### F4. 把背景图 / BGM 对齐到字幕与配音总时长

用户手动做完 TTS 后，字幕与配音会变成几百个片段、总时长远超模板，
而背景图、贴纸、顶部标题、BGM 仍停在模板的 9.5 分钟，导出后后半段黑屏且无音乐。
用 `fit-duration`（别名 `fit`）一次对齐：

```bash
# 先预览（不写盘、不退出剪映）
python3 "$SK" fit-duration -s "明朝那些事儿" --dry-run

# 执行：自动退出剪映 → 改两份工程 JSON → 自动重开置顶
python3 "$SK" fit-duration -s "明朝那些事儿"
```

行为：

- **基准** = 动态定位「片段最多的 text 轨 + 真正的配音 audio 轨」的最晚结束时间
  （TTS 后轨道会重排，禁止写死下标），并同步顶层 `duration`、内层 meta 与
  外层索引的 `tm_duration`。
  **配音轨必须先按素材类型排除 BGM**：优先取引用 `.wav` 且路径不含
  `downloads` 的 audio 轨，多条时选结束时间最接近字幕轨的；识别不到才退回
  「片段最多的 audio 轨」（兼容 TTS 分段配音）。
  2026-11-14《住小房子的女人》实测：配音是 1 段外部旁白 wav、BGM 是 34 段 mp3，
  若按片段数选会把 BGM 当基准（57 分钟）并把旁白轨拉长到 57 分钟，
  导出后半段全是静音。
- 单段背景图 / 贴纸 / 标题 → `target_timerange.duration` 延长到基准。
- 多段 BGM 音频轨 → 按原循环单元（实测 106800000 us 一首钢琴曲）继续循环补齐；
  **每个新增片段都生成新的 segment id、material id 与 `extra_material_refs`
  对应的素材条目**，否则剪映打开时 id 撞车会丢片段。
- 超出基准的片段 → 裁短 / 删除，因此「裁减」与「延长」两个方向都覆盖。
- 字幕轨与配音轨**完全不动**。

参数：`--target` 手动指定微秒时长；`--no-bgm-loop` 不让 BGM 循环（只拉长末段，
会出现静音，一般不推荐）；`--dry-run` 只预览。

### F5. 对齐字幕样式（字号 / 缩放 / 位置 / 行间距 / 预设）

用户做完 TTS 后，剪映会**重建字幕并把样式重置为默认值**（实测
`scale=1.0`、`transform=(0,0)`、`line_spacing=0.02`，还会丢失描边、
字体路径、背景色等字段）。以已调好的《小王子》为参照批量套回：

```bash
# 预览（不写盘、不退出剪映）
python3 "$SK" fix-subtitles -s "明朝那些事儿" --dry-run

# 执行：自动退出剪映 → 改两份工程 JSON → 自动重开置顶
python3 "$SK" fix-subtitles -s "明朝那些事儿"
```

参照草稿《小王子》的实测样式（画布 6600×3712）：

| 项 | 值 | 存储位置 |
|---|---|---|
| 缩放 | 21% | `clip.scale.{x,y}=0.21` |
| 位置 | X=1146 / Y=364 | `clip.transform = px / 画布` |
| 字号 | 15.0 | `content.styles[0].size` |
| 行间距 | 面板 4 | `line_spacing=0.2089` |
| 预设样式 | 白字 + 黑描边 0.08 + 阴影 | `styles[0].fill/strokes`、`shadow_*`、`border_*`、`font_path` |

**导入型字幕多一个 `font_size` 字段**（实测默认 5.0），TTS 字幕和参照草稿
《小王子》都没有。剪映可能优先读它，所以 `apply_subtitle_style` 会把
`font_size` 一并设成与 `styles[0].size` 相同的值，否则字号设置看起来不生效。

坐标公式是 **`transform = px / 画布`**，不是 `2px/W-1`（早期踩过坑）。
`--size` / `--scale` / `--x` / `--y` / `--line-spacing` 可单独覆盖，
`--from` 换参照草稿。命令动态定位字幕轨（`type=text` 且片段数 > 1、
取最多的那条），顶部单段书名标题不会被误改；`content.text`、`words`、
`text_to_audio_ids` 等业务字段一律不动，避免破坏字幕与配音的关联。

### F6. 字幕文本形态与宽度（默认：一整句一行、保留标点）

**现行规则（用户 2026-11-16 更新，覆盖 11-15 的「去标点」版）：自动生成的
字幕「完全去掉硬换行、一整句一行」，并且保留标点。** 沿革：11-14 按 23 字
硬插 `\n` 会把「鸡尾酒」劈成「鸡\n尾酒」被否定 → 11-15 改为 flat 去换行，
但连标点一起去掉 → 11-16 用户反馈「当前字幕没有标点符号」，故恢复标点。
现在标点必须保留，只有显式 `--strip-punct` 才去标点。

- **`fix-subtitles` 默认 = `flat` 模式**：只去掉全部硬换行 `\n`（中文直接
  连接、不留空格），**保留所有标点**，一整句一行。`fixed_width` **保持不变**
  （仍防遮挡光盘）。加 `--strip-punct` 才额外去掉标点（中文 `：，。「」《》
  ——？！` 等 + 英文标点，用 Unicode `P*` 类别判定，另加 `PUNCT_EXTRA`）。
  《咸的玩笑》2026-11-16 实测：291 段全部 1 行、最长单行 80 字，标点完整。
- **只对无逐字绑定的导入型字幕动文本**：`strip_subtitle_punct()` /
  `flatten_subtitle()` 在 `jy_draft.py`；`plan_subtitle_layout` 用
  `subtitle_has_word_binding()` 判断——有 `words`/`text_to_audio_ids` 的 TTS
  原生字幕一律只拍平换行、保留标点（不改字符数），避免破坏逐字配音下标。
  这批书都是 agent 全流程生成的导入型字幕（`inject_srt.py` 设 `words={}`、删
  `text_to_audio_ids`），配音按整段 wav + segment 时间轴对齐，改标点/换行
  完全不影响配音。
- **旧折行仍可用（显式指定才启用）**：`--max-chars 23` 走旧 23 字折行，
  `--max-lines N` 压缩到最多 N 行；`--no-flat` 完全不碰字幕文本（保留原样）。
  宽度 `fixed_width = 1105.0487 × max_chars / 22`（23 字 → 1155.28），
  `--max-width` 显式指定、`--auto-width` 删除、`--keep-width` 不动。
- 同一个 plan 应用到根目录与 Timeline 两份 `draft_info.json`，保证一致。

```bash
# 默认（不必传参）：去硬换行 + 保留标点，一整句一行，宽度不变
python3 "$SK" fix-subtitles -s "<草稿>" --dry-run   # 预览
python3 "$SK" fix-subtitles -s "<草稿>"             # 执行

# 显式去标点（一般不用）：python3 "$SK" fix-subtitles -s "<草稿>" --strip-punct
# 旧规则（仅在用户明确要折行时用）：python3 "$SK" fix-subtitles -s "<草稿>" --max-chars 23
```

**给已去标点的旧草稿恢复标点**（`fix-subtitles` 无反向功能，须从 SRT 原文按段
写回）：解析 `<书>_字幕.srt` 得带标点文本；按段顺序校验「当前文本 == SRT 文本
去标点」全通过（段顺序与 SRT 一一对应，start 有毫秒偏移不可拿来做 key）；
退出剪映后以 Timeline 副本为基准把每段 `content.text` 写成 SRT 原文并把
`styles[0].range=[0,len(text)]`，两份 `draft_info.json` 写同一份数据，再重开。
《咸的玩笑》实测 291 段全部吻合，222 段含标点，两份工程一致。

**一小句一条字幕（用户 2026-11-16 晚最终规则，覆盖上面的「超长才拆」）**：
用户反馈「一大句一大句、字幕经常折行」，改为**每条字幕就是一个小分句**——
按中文标点 `，。！？；：、`（含半角 `,!?;:`）把每条 cue 切开，空句丢弃；
**切开后再去掉每条小句尾部的断句标点**（分行本身即停顿，用户 2026-11-16 晚确认：
「一小句一条后句尾标点不需要了」）——注意只 rstrip 断句标点，**成对的引号 `""`、
书名号 `《》`、括号等保留**（是内容的一部分）。无标点长句超过 69 字才在 69 处硬切。时间轴按各小句**字数比例**
从原段时长分配（配音是独立整段 wav，拆字幕不影响声音）。做法见 `/tmp/split_clauses.py`
（临时脚本，必要时按此重写）：以 Timeline 工程为基准，遍历每条字幕的
`content.text` 切成小句；每条新建 text material / segment / animation id，
`styles[0].range=[0,len(part)]`、`target_timerange={start:原start+累计,duration:原dur*len(part)/总字数}`，
两份 `draft_info.json` 写**同一份** base（UUID 只生成一次），最后按 start 排序
重排 `render_index` 保证唯一，清理旧 material/animation。改前 `open_draft.py --quit-only`
完全退出剪映，改后 `open_draft.py <草稿名>` 重开置顶。
去掉每条小句尾部断句标点用 `/tmp/strip_tail_punct.py`（同类做法：遍历 material
content.text 做 `rstrip("，。！？；：、,!?;:")`，`styles[0].range` 重算，不动段结构/
时间轴/配音，两份工程写同一 base）。《咸的玩笑》实测 293→698 段、平均 8.3 字/条、
最长 28 字、407 条去掉句尾标点、无空串、时间轴零重叠、两份工程一致。

历史：超长（>69 字 = 3 行）才按标点拆两条是 11-16 早先规则（`/tmp/split_long.py`，
咸的玩笑 291→293 段），已被上面的「一小句一条」覆盖，仅回溯保留。

**坐标模板（用户 2026-11-16 在《活着》草稿手动调好，确认为以后所有新书的模板）**：
三条轨道的 `clip.transform`（在 segment 的 `clip` 里，面板坐标 = transform×画布6600×3712）：
- 字幕轨（type=text 且片段数最多）：scale `{0.21,0.21}`，transform `{x:0.1616243516,y:-0.0229360965}`
- 标题轨（type=text 且仅 1 段，顶部书名）：scale `{0.3504791069,0.3504791069}`，
  transform `{x:-0.0346906847,y:0.3870542764}`
- 播放器装饰轨（type=sticker 且 scale.x≈0.61）：transform `{x:0.1645219307,y:-0.4317739389}`
（相对旧模板《住小房子的女人》：字幕 y 0.098→-0.023、标题 y 0.759→0.387、
播放器 x 0.138→0.165 / y -0.375→-0.432。）
正式脚本 `scripts/apply_layout_template.py <草稿名> [--dry-run] [--no-quit]`：按上述识别
规则给三轨套坐标，两份工程写同一 base。标准链路里放在 `split_subtitles.py` 之后、
`set-bg` 之前。`fix-subtitles --from` 只覆盖字幕轨（不含标题/播放器轨），故必须再
单独跑本脚本才能三轨齐全。《活着》已按新坐标就位。

历史（11-14 旧规则，已被上面覆盖，仅供回溯）：当时硬约束「一行约 23 字 +
最大宽度」，是因「压到 2 行 + 宽度放大 2267」会遮住左侧光盘而退回；宽度
`fixed_width=1155.28` 这一防遮挡底线**在现行 flat 模式下依然保留**。

《明朝那些事儿》最终结果：440 段 `1行×141 / 2行×175 / 3行×95 / 4行×29`，
最长单行 **23 字**，`fixed_width=1155.28`，位置仍 X1146/Y364、缩放 21%。
业务字段（去空白文字、片段 ID、时间范围、配音关联、样式 range/size、
时长、轨道结构）sha256 执行前后一致 `829a07f8…`。

《住小房子的女人》结果（导入型，2026-11-14）：91 段改前全是单行、最长 67 字，
64 段超 23 字 → `1行×27 / 2行×46 / 3行×18`，最长单行 **23 字**；
`fixed_width=1155.28`，`styles[0].size=15.0` 且 `font_size=15.0`，
缩放 0.21、X1146/Y364、行间距 0.2089。业务字段 sha256 前后一致
`c72164e57ff97e88`。

### F7. 封面必须全量同步（草稿里藏着一个独立的封面编辑工程）

**根因（2026-11-14 二次实测）**：剪映的「封面编辑」不是简单展示
`draft_cover.jpg`，而是打开**内嵌在 `draft_info.json` 里的一个 composition
草稿工程**：

```
draft_info.json
├─ cover.cover_draft_id → "D5A17AE0-…_material"
└─ materials.drafts[].draft          ← 独立封面工程
   ├─ tracks[0] 图片轨 → Resources/cover/<uuid>.png   （模板底图，无字）
   ├─ tracks[1] 文字轨 → content.text "《小王子》"     （模板书名）
   └─ 渲染结果缓存 → Resources/cover/<uuid>.jpg        （带书名的成品）
```

用户点开「封面编辑」再点「取消」，剪映会把这套模板的缓存封面写回
`draft_cover.jpg` —— 所以只改根目录的 jpg 一定会被打回上一本书的封面。
`copy` 出来的新草稿会把整套模板配置、底图 png、候选 jpg 一起带过来。

`make_cover()` 现已统一负责**全量同步**（`copy -t` / `retitle` / `set-bg` /
`fix-cover` 都会走）：

| 文件 | 处理 |
|---|---|
| `draft_cover.jpg` | 用当前底图 + 书名重新生成（1920×1080） |
| `draft_local_cover.jpg` | 320×180 缩略图（草稿箱缓存之一） |
| `draft_cover.jpg.bak` | 覆盖成新封面，防止旧图回流 |
| `Timelines/<content_id>/draft_cover.jpg` | 时间线副本，按原尺寸同步 |
| `Resources/cover/*.jpg` | 封面候选/缓存，**全部**覆盖成新封面 |
| `Resources/cover/*.png` | 封面编辑器底图，换成本书主题插画（等比居中裁切） |
| 两份 `draft_info.json` 的 `materials.drafts[].draft.materials.texts[]` | 模板书名改为《当前书名》，同步 `styles.range`；字色按底图亮度自动选白字 / 深墨字 |
| **两份 `root_meta_info.json` 的 `all_draft_store[].draft_cover`** | **草稿箱缩略图读它**，必须指向本草稿目录的 `draft_cover.jpg`（`sync_cover_index()`） |
| **加密 `draft_meta_info.json` 的 `draft_cover`** | **编辑页 / 封面编辑器读它**，同样必须指向本草稿目录；剪映会用它回写外层索引（见四次实测） |

```bash
python3 "$SK" fix-cover -s "明朝那些事儿"          # 用当前底图/书名全量重做
python3 "$SK" fix-cover -s "新书" -t "新书" --base /path/bg.jpg
```

`fix-cover` 额外把 `materials.videos[].material_name` / `name` 同步成实际
文件名，否则时间线上仍显示 `xiaowangzi_disc_bg.jpg`（path 已换但显示名
没换）。改完重开剪映，草稿箱、草稿内、封面编辑器三者都应是本书内容。

**三次实测（2026-11-14 19:45，屏幕截图确认）**：用户「另存为草稿」或从
别的草稿导入字幕时，索引条目的 `draft_cover` 会**继承源草稿的绝对路径**。
《住小房子的女人》的该字段仍是
`<root>/明朝那些事儿/draft_cover.jpg`，草稿箱直接读这个路径显示缩略图，
所以本书目录里 8 个 jpg 副本、缩略图、内嵌工程全部改成新书封面后，
草稿箱**依然显示「明朝那些事儿」封面**。磁盘全文扫描「明朝」命中 0 次，
说明不是缓存文件残留，而是索引指错路径。
`sync_cover_index(fold)` 现在会在每次 `make_cover()` 收尾把主索引与容器
索引里该条目的 `draft_cover` 校正回本书目录（两份索引实测是同一 inode）。

> 结论：**不要再只改一两个 jpg**。只要草稿里还留着任何一份旧书封面
> （尤其是 `Resources/cover/` 与内嵌 composition 的文字），用户一点封面
> 编辑就会回退；索引 `draft_cover` 指错目录时，连草稿箱都一直是上一本。
> 判据：所有封面 jpg 与基准的缩放像素差 < 3、`materials.drafts` 里的 text
> 是本书书名、两份索引的 `draft_cover` 都落在本书目录。
**四次实测（2026-11-14 20:25，用户编辑页截图）**：修好外层索引后草稿箱
已是本书封面，但**编辑页「点击编辑封面」/ 播放器封面预览仍是上一本**。
根因是**内层加密 `draft_meta_info.json` 里的 `draft_cover` 也指向
`明朝那些事儿/draft_cover.jpg`** —— 剪映有两套独立封面路径：
外层索引 `all_draft_store[].draft_cover` 供草稿箱，内层 meta 的
`draft_cover` 供编辑页/封面编辑器。用户「另存为草稿」时两份都继承了源草稿；
且剪映启动会用内层 meta 回写外层索引，所以只改外层过一会儿又会被打回。
`sync_cover_index(fold)` 现在同时校正外层两份索引 + 内层 meta（只改
`draft_cover` 一个字段并重新加密，不调用会重分配 id 的 `sync_inner_meta()`）。
判据：重开剪映后外层索引与内层 meta 的 `draft_cover` 都仍指向本书目录。

> **界面验证**：现在 `screencapture -x -t png /tmp/x.png` 可读（无需辅助功能
> 权限），改完重开后截图看草稿箱第一位封面，比只查文件可靠。辅助功能权限
> 仍未授予，无法自动双击进入编辑页，编辑页封面需用户目视确认。

### G. 手动重开并置顶

```bash
python3 "$SK" reopen "明朝那些事儿"
```

### H. 收尾：生成公众号文章封面双图（用户 2026-11-14 明确，每次处理完必做）

> 用户原话：「以后每次处理完之后调用
> `手机封片图片.py` 以及 `横版电脑封面.py` 生成封面图，两张图片的位置和 markdown 同文件夹」。

**这是文章仓库的封面，不是剪映草稿封面**，两者互不替代：

| 项目 | 值 |
|---|---|
| 脚本目录 | `$BOOK_ROOT/scripts/`（**用户 2026-11-14 21:02 从上一级目录移入**，连同模板图与历史输出一起搬；根目录已无这两个脚本） |
| 手机竖版 | `scripts/手机封片图片.py` → `<书名>_封面.png`，1080×1920 |
| 电脑横版 | `scripts/横版电脑封面.py` → `<书名>.png`，2176×1024 |
| 模板图 | 同在 `scripts/` 下的 `生成横版图片_原.png`（浅色水彩冥想女子）与 `生成竖版背景_临时.png`；竖版脚本首次运行会自动从横版中央裁 1024×1024 拉伸成 1080×1920 |
| 依赖 | `magick`（Homebrew ImageMagick）+ `/System/Library/Fonts/Supplemental/Songti.ttc` |
| 调用签名 | `python3 <脚本> "书名" "作者(可选)" <输出目录>` |
| 作者参数 | 系列既有封面（`霍乱时期的爱情.png` 等）**只叠书名、不带作者**，默认传空字符串；用户明确要求时才加 |
| 输出位置 | **必须与该书 `.md` 同目录**，例如 `.../2026-11/20261114_住小房子的女人/`；不要放进子目录或脚本目录 |

一键命令（`covers` 自动按书名定位 markdown 目录、调用两个脚本、校验输出）：

```bash
python3 "$SK" covers -s "住小房子的女人"
# 可选：--author "〔中国〕纪静蓉"   --md <指定 md 路径/目录>
#       --article-root <仓库根>      --dry-run
```

定位规则：在文章仓库下找**目录名含书名且含 `.md`** 的目录，优先取文件名也含书名的 md，
多个候选按修改时间取最新；找不到会**显式报错**，不要静默输出到脚本目录。
脚本位置由 `cover_script_path()` 解析：优先 `<文章根>/scripts/`，回退旧的 `<文章根>/`，
两处都没有就报错。`covers` 不退出剪映、不改草稿，可安全放在重开置顶之后执行。

> **脚本与模板图必须一起搬**：两个脚本用 `SCRIPT_DIR = dirname(__file__)` 拼模板路径，
> 只把 `.py` 移进 `scripts/` 而不带 `生成横版图片_原.png`，会直接报
> `找不到原始模板图`。2026-11-14 用户这次是整套搬过去的，脚本内容无需改动。

> 中文路径在部分 shell 调用里会出现 `No such file or directory`（Unicode 规范化差异），
> 用 Python `os.walk` / `subprocess` 传参可稳定工作，`covers` 已按此实现。

## 四、实测结论（勿重复调研）

- 剪映 10.3.0 运行时会锁草稿并回写；`osascript quit` 常只缩到托盘，
  必须 `pkill -f VideoFusion-macOS` 兜底。
- **封面路径有两套，各管一个界面**：草稿箱缩略图读外层索引
  `all_draft_store[].draft_cover`，编辑页/封面编辑器读加密内层
  `draft_meta_info.json` 的 `draft_cover`；都不是固定读
  `draft_local_cover.jpg`。`copy` / 用户「另存为草稿」会让两份都指向源草稿，
  此时改本书所有 jpg 都无效，且剪映会用内层把外层回写回去（§F7 三/四次实测）。
  另外还要同步 `Timelines/*/draft_cover.jpg`、`Resources/cover/*.jpg/*.png`
  以及**内嵌封面编辑工程**的模板书名，否则点开封面编辑再取消会被写回旧封面。
- **截图校验可用**：`screencapture -x -t png /tmp/x.png` 在本机可读（此前
  以为没有屏幕录制权限）；改完重开后直接看草稿箱，能确认封面是否真的刷新。
  辅助功能权限仍未授予，故不能按 UI 名字点击 / 自动打开草稿。
- 时间线显示的图片文件名来自 `materials.videos[].material_name`（还有
  `name` / `file_name`），与 `path` 无关；`set-bg` 换图后必须同步显示名，
  否则画面已是新图、轨道上还写着旧名。
- 字幕文本框过宽会向左溢出遮住画面左侧光盘图案。`fixed_width≈1155` 的
  宽度上限必须保留（「压到 2 行 + 宽度 2267」已被用户否定）。文本形态
  按用户 2026-11-16 现行规则：flat 去硬换行、保留标点、一整句一行（长句
  可达 80+ 字，由固定宽度约束其显示区）；旧的 23 字/行硬折行已被否定、
  勿再自动套用。
- 无法通过命令行参数让剪映「直达」某草稿：`open -a --args` 参数被
  LaunchServices 丢弃，`launchctl setenv` 被沙箱拒绝。可靠方案只有
  「退出 → 刷新 `tm_draft_modified` 置顶 → `open -a` 启动 → Quartz 只读校验窗口」。
- 无辅助功能权限（System Events 恒 `-10004`）、无屏幕录制权限
  （`CGWindowListCreateImage` 返回 None），不能按 UI 名字点击或截屏定位。
- 加密文件用 `jy-draftc-mac decrypt/encrypt`，需
  `DYLD_LIBRARY_PATH=/Applications/VideoFusion-macOS.app/Contents/Frameworks`；
  解密用空 context。二进制 59K，已随 skill 自带。
- `Timelines/project.json` 实测仅 433 B、无素材路径；素材引用在加密工程包内。
- `draft_meta_info.json` 解密后含 `draft_id` / `draft_name` / `draft_fold_path` /
  `tm_draft_cloud_entry_id` 等字段，剪映会读取 → 必须同步。
- 画布 6600×3712；面板 X/Y = `clip.transform × 画布`；字幕样式见
  `line_spacing`≈0.2089（面板 4）、`scale`=0.21、`transform`=1146/6600, 364/3712。

## 五、失败排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 剪映里看不到新草稿 | 索引未写入 / 剪映运行中被回写 / JSON 损坏 | 校验 JSON，恢复 `.bak.<时间戳>` 后重试 |
| 新草稿打开空白或报错 | 复制不完整（漏 `crypto_key_store.dat` / `Timelines/` / `textReading/`） | 删掉副本目录重新复制 |
| 两条草稿互相覆盖 / 改名被改回 | 只改了外层索引，内层加密 meta 仍是旧 id 和旧名 | 本版 `copy`/`rename` 已自动同步；旧副本可用 `rename` 重新对齐 |
| 草稿列表出现两条同名 | 目录名与 `draft_name` 不一致 | 用 `rename` 对齐 |
| 标题文字显示不全 | `styles[].range` 还是旧长度 | `retitle` 会自动更新；或重跑一次 |
| 图片/音频报媒体丢失 | 外部中文绝对路径或占位符被破坏 | 素材放草稿内 `Resources/` 并用 draftpath 占位符引用 |
| `root_meta_info.json` 空/截断 | 非原子写入被中断 | 用 `.bak.<时间戳>` 覆盖恢复，重启剪映 |
| `jy-draftc` 报 dylib 找不到 | 剪映 App 不在 `/Applications/VideoFusion-macOS.app` | 修正 `APP_FRAMEWORKS` 常量 |

## 六、二次校准：双索引与 draft_id 重分配（2026-11-14 实测）

这一节修正第 二.5 条与「关键修正」段里关于 id 的表述，**以本节为准**。

1. **`root_meta_info.json` 有两份**，内容实测完全一致：
   - `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/root_meta_info.json`
   - `~/Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/root_meta_info.json`

   剪映启动时会以容器副本为准并回写主索引。脚本的 `save_index` / `backup_index`
   与 `open_draft.touch_draft` 已做**双写**，只写一份可能被旧副本覆盖。

2. **剪映启动时会给所有草稿重新分配外层 `draft_id`**。实测 6 个草稿的
   外层 id 与内层 `draft_meta_info.json` 的 id 全都不相等，这是常态而非故障：
   剪映靠 `draft_fold_path` 定位草稿，不依赖内外 id 相等。
   因此：
   - 不要因为「脚本写入的 id 被剪映换掉」就判定失败或反复重写；
   - 真正必须保证的是 **副本内层 id 不能与源草稿内层 id 相同**（否则两个草稿撞 id），
     `sync_inner_meta` 负责这件事；
   - 校验是否成功应看：草稿是否出现在两份索引里、`draft_fold_path` 是否正确、
     内层 `draft_name` 是否为新名、云字段是否清空、素材是否 0 缺失。

3. **草稿箱排序按 `tm_draft_modified` 倒序，不看数组顺序**。脚本仍 `insert(0)`
   便于阅读，但判断是否置顶要用
   `sorted(arr, key=lambda e: e["tm_draft_modified"], reverse=True)`，
   或直接跑 `python3 scripts/open_draft.py --check` 看「草稿箱序」一行。
   数组第一项不是最新草稿 ≠ 置顶失败。

4. 剪映重启不会覆盖已改好的两份 `draft_info.json` 标题文本，也不会改动源草稿；
   但会刷新封面缩略图与外层时间戳，属正常行为。

## 七、输出要求

- 报告实际执行结果：源草稿、新草稿名、新 `draft_id`、索引备份绝对路径、
  新草稿目录绝对路径、`draft_ids` 变化。
- 涉及生成的文件（封面、备份目录）用 `present_files` 给出可点击路径。
- 明确说明自动退出/重开剪映的结果，以及哪些内容仍是占位（未替换的字幕/配音）。
- 任何一步失败如实说明卡点，不要用「已完成」掩盖。

## 八、批量：从讲稿直接生成语音 + 成品草稿（2026-11-15 实测）

触发：用户拿来一批只有 `.md` 讲稿的目录，要求「生成语音和草稿」并选择
「全套成品草稿」。此时**由 agent 完成 TTS 与字幕生成**（这是对该次任务的
明确授权，覆盖 §三 固定分工里「音频/字幕由用户做」的默认约定）。

### 讲稿写作约束（2026-11-15 用户明确）
- 字数：**正文含标点 4500-5000**（去掉 markdown 标题与所有空白后统计；段数约 28-30、每段约 170 字）。
- **正文聚焦作品本身**：作者生平、出版社/刊物传播史、写作轶事**不得连续成段**（曾一次写了 4 段约 800 字讲路遥生平被用户指出）。作者信息只允许必要时压成**一小段带过**（如「为写准十年翻遍报纸、住进煤矿、写完扔笔、四十二岁离世」这类最有分量的细节），篇幅主要留给情节、人物、金句与对普通人的启发。
- 固定口播结构：开头直接进入「今天想跟你聊的这本书，它叫《书名》」，结尾「十分钟读完一本书，我们下本见」；纯段落无 markdown 小标题。（开场白已去掉，不要写「大家好我是燕麦粥」。）

### 参与脚本

| 脚本 | 位置 | 作用 |
|---|---|---|
| `make_jy_draft.py` | 文章仓库 `scripts/` | 按句末标点切分讲稿，调 SAMI「夏雨嫣·情感」逐句合成 ogg（强制 `backend="sami"`、禁降级、按音色+文本哈希缓存到 `~/.cache/jianying_tts/`），产出**明文** `draft_content.json` 中间草稿 |
| `export_jy_assets.py` | 同上 | 解码 ogg 拼成整段 wav（48k/mono/s16le），导出 `<书名>_旁白.wav/.mp3` 与严格对齐的 `<书名>_字幕.srt` 到该书 md 同目录 |
| `inject_srt.py` | 本 skill `scripts/` | 把 SRT + wav 注入加密草稿（见下） |
| `jy_draft.py` | 本 skill `scripts/` | `copy` / `fit-duration` / `fix-subtitles` / `set-bg` / `fix-cover` / `covers` / `reopen` |

### 标准链路（每本）

```bash
SCR=${BOOK_ROOT:-$HOME/Product/WeChatArticle/十分钟读完一本书}/scripts
SK=${SKILL_DIR:-$HOME/.workbuddy/skills/capcut-draft-manager}/scripts
STAGE=/tmp/jy_tts_stage           # 中间草稿暂存区，绝不写进剪映草稿库

# 0. 先备份两份 root_meta_info.json（批量 copy 会多次写索引）
# 1. 语音 + 素材（中间草稿放暂存区，避免与正式草稿同名冲突）
python3 "$SCR/make_jy_draft.py" "<md>" --name "<书名>" --drafts-root "$STAGE"
python3 "$SCR/export_jy_assets.py" "<书名>" --draft-root "$STAGE"

# 2. 退出剪映 → 复制模板 → 注入 → 收尾
python3 "$SK/open_draft.py" --quit-only
python3 "$SK/jy_draft.py" copy -s "住小房子的女人" -n "<书名>" -t "<书名>" --no-reopen
python3 "$SK/inject_srt.py" -s "<书名>" --srt "<书名>_字幕.srt" --wav "<书名>_旁白.wav"
python3 "$SK/jy_draft.py" fit-duration -s "<书名>" --no-quit --no-reopen
python3 "$SK/jy_draft.py" fix-subtitles -s "<书名>" --from "小王子" --no-quit --no-reopen
# 字幕「一小句一条」：按标点切小分句 + 去句尾标点（见 §F6，用户 2026-11-16 最终规则）
python3 "$SK/split_subtitles.py" "<书名>" --no-quit
# 坐标模板（用户 2026-11-16 在《活着》调好：字幕/标题/播放器三轨位置，见 §F6 末）
python3 "$SK/apply_layout_template.py" "<书名>" --no-quit
python3 "$SK/jy_draft.py" set-bg -s "<书名>" -i "<新插画>" --no-clean-mark --no-quit --no-reopen
python3 "$SK/jy_draft.py" fix-cover -s "<书名>" -t "<书名>" --no-quit --no-reopen
python3 "$SK/jy_draft.py" covers -s "<书名>"        # §H 文章封面双图

# 3. 全部做完后统一重开置顶
python3 "$SK/jy_draft.py" reopen "<书名>"
```

### 铁律（本次踩过的坑）

1. **中间草稿必须另存**。`JyProject` 默认把明文 `draft_content.json` 写进剪映草稿库
   `<草稿名>/`，既会与后面 `copy` 出的正式加密草稿撞目录，也会让草稿箱出现
   「草稿内容已损坏」的 0.0B 条目。已给两个仓库脚本新增
   `--drafts-root` / `--draft-root`（不传时行为不变）。
2. **两份工程 JSON 只能生成一次随机 id**。`inject_srt.py` 与 `fit-duration`
   都必须「以时间线副本 `Timelines/*/draft_info.json` 为基准解密 → 改一份数据 →
   同一份写两处」。若两份各自调用，新增字幕段 / BGM 段的 `segment.id`、
   `material_id`、`beats` / `speeds` / `vocal_separations` 会各自生成不同 uuid，
   两份虽各自自洽但不一致（2026-11-15 实测 39 处差异），`fit-duration` 已修。
3. `inject_srt.py` 按 SRT 条数重建字幕轨：每段新建 `id` / `material_id` /
   `extra_material_refs` 及对应 `material_animations` 条目，`styles[].range`
   重算为 `[0, len(text)]`，并清空 `words` / `current_words` /
   `text_to_audio_ids` → 后续 `fix-subtitles` 会判定「无逐字关联」而启用
   flat 去硬换行、保留标点、一整句一行（旧规则才是 23 字/行折行）。旧字幕素材与动画条目一并移除。
4. 顶层 `duration` 与旁白 `source/target_timerange` 用 wav 精确帧长，
   不要拿 SRT 末条的开始时间当总长。
   **不要沿用旧版「旁白轨外部绝对路径实测可用」的结论**：`inject_srt.py`
   写回工程后会自动调 `J.fix_media_one(fold)`，把 wav/BGM 搬进草稿内
   `Resources/media/` 并重建加密 meta 的链接媒体登记表（见 §九）。
   跳过这步，剪映打开一定弹「链接媒体丢失」，导出的片子可能没有旁白。
5. 一本书一张亮色插画，`clean_ai_mark.py` 现按整图平均亮度自动分流：
   >140 用大核中值（亮底白色水印，克隆会搬来水彩边界留下水平错位线），
   ≤140 用原「邻近克隆 + 亮度匹配」。深色/亮色都不要整块 inpaint。
6. 封面路径三处（主索引 / 容器索引 / 内层加密 meta）由 `make_cover()` 的
   `sync_cover_index()` 自动校正，批量链路里 `set-bg` / `fix-cover` 都会带上。

### 校验清单

两份工程 JSON 完全一致；字幕段数 = SRT 条数；字幕文本无 `\n`、**保留标点**、
一整句一行（逐条文字应与 SRT 原文逐段一致，含标点）；缩放 0.21 / X1146 Y364 /
字号 15 / 行间距 0.2089 / `fixed_width` 1155.28（宽度保持不变）；非基准轨
end 全等于顶层 `duration`；素材 0 缺失、
segment id 0 重复；旁白与配图路径存在且属本书；工程内无上一本书名；
三处 `draft_cover` 指向本书；封面副本用**缩放像素差**判断（不同尺寸 md5
本就不同，别拿 md5 判一致）；标题与内嵌封面工程书名正确。

> 剪映启动会按自身规则回写 `tm_draft_modified`，批处理多本时
> `reopen <某本>` 未必能把它固定在第一位；只要目标草稿都在草稿箱前列即可，
> 以 `open_draft.py --check` 的「草稿箱序」为准，如实报告。

## 九、链接媒体丢失的真正根因 + 批量导出（2026-11-15 实测）

### 9.1 「音频地址看着都对，却提示链接媒体丢失」

剪映校验的**不只是** `draft_info.json` 的 `materials.audios[].path`。
加密的 `draft_meta_info.json` 里还有一张独立的**链接媒体登记表**：

```text
draft_meta_info.json
└─ draft_materials[type=0].value[]
   ├─ file_Path      绝对路径
   ├─ id             与工程 audio material 的 id / local_material_id 对应
   ├─ extra_info     文件名
   └─ duration       微秒
```

`copy` 生成新草稿时这张表会**继承源草稿**；`inject_srt.py` 早期只改工程
path、不改这张表 → 登记表要么只登记 BGM（本书旁白没登记），要么仍写着
上一本书的 wav 与旧 ID / 旧时长，和工程里的新 wav 对不上 → 弹「链接媒体丢失」。
四本草稿还共用模板的 `music_id` / `resource_id` / `local_material_id`
（实测 `5495b5ef…` / `34de1f4d…`），进一步加重冲突。

判据（**不要只看 path 文件是否存在**）：

- 工程 `materials.audios[].path` 还原后文件存在 ✅ 仍可能报丢失；
- 登记表 `file_Path` 的文件名集合必须**等于**工程音频的文件名集合；
- 登记表 `id` 必须能对上工程的 `id` / `local_material_id`。

```bash
python3 "$SK" fix-media -s "三体" -s "整理人生" --dry-run  # 诊断，不写盘
python3 "$SK" fix-media -s "三体" -s "整理人生"           # 修复并重开置顶
```

`fix-media` 做三件事：① 所有外部绝对路径音频复制到
`<草稿>/Resources/media/`；② 工程 `path` 与登记表 `file_Path` 写成
**同一个草稿内绝对路径**（两边字符串一致很关键，占位符与绝对路径混用会
再次不一致）；③ 按文件分组重生成 `music_id` / `resource_id` /
`local_material_id`，并按「素材 id + local_material_id」重建登记表两条。
两份 `draft_info.json` 仍写同一份数据。

> 剪映启动后可能把工程 path 规范化成
> `##_draftpath_placeholder_…##/Resources/media/xxx.wav`，这是正常行为，
> 只要登记表仍指向同一物理文件即可。

`inject_srt.py` 现已在写回后自动调用 `fix_media_one(fold)`，批量链路无需
额外步骤；旧草稿用 `fix-media` 补修。

### 9.2 批量导出成片（无辅助功能权限下的可行方案）

剪映**没有**命令行导出参数（主程序只有 `--draft_path` / `--draft_from` /
`--open_timestamp`），没有 AppleScript 字典，也没有独立渲染可执行文件。
本机仍无辅助功能权限（System Events `-10004`），但 2026-11-15 实测：

- `Quartz.CGEventPost(kCGHIDEventTap, …)` **可用且精度 0**（历史记为
  「不稳定」已过时），可发送鼠标移动 / 单击 / 双击；
- `CGDisplayCreateImage` / `screencapture -x -R` 可截任意显示器；
- `CGWindowListCopyWindowInfo` 可只读拿窗口 bounds。**必须用
  `kCGWindowListOptionOnScreenOnly` 过滤**：`OptionAll` 会混入隐藏/
  后台窗口，导致「已进入编辑页」误判。

每本的自动流程：

```text
退出剪映 → reopen <书名>（置顶草稿箱第一位）
→ 双击第一位卡片 → 等全屏编辑页 → 点右上「导出」
→ 等「导出-<书名>」面板（640×720 设置态）→ 点右下「导出」
→ 轮询成片文件稳定 + ffprobe 校验音轨 → 复制到 md 同目录
```

坐标必须由**窗口 bounds 动态计算**，不要写死（窗口会在主屏/扩展屏之间漂移，
实测同一台机器重开后从 `(2401,309)` 漂到 `(2208,245)` 再到 `(172,119)`）：

| 目标 | 相对窗口 |
|---|---|
| 草稿箱第一位卡片 | `(winX+294, winY+602)`（草稿箱窗口 1168×780） |
| 编辑页右上「导出」 | `(winX+W-41, winY+17)`（全屏编辑页） |
| 导出面板确认「导出」 | `(panelX+588, panelY+693)`（面板 640×720） |

第二屏原点可能是 `(1512,-54)`，全局坐标可为负，CGEvent 能正常接受。
导出参数沿用系列既有成片：**1920×1080 / 30fps / MOV(H.264+AAC)**。

剪映记住的导出目录是上次用过的 `<…>/20261109_小王子/`，并会在其下建
`<书名>/<书名>.mov`（含 `-封面.jpg`）与
`.__jianying_export_temp_folder_*` 临时目录。**轮询要同时看正式子目录和
临时目录**，只盯临时目录会等超时（第一本从临时目录取、第二三本从正式
子目录取）。成片用 `shutil.copy2` 复制到该书 md 同目录，原始副本不删。

2026-11-15 三本实测结果（均 1920×1080 / 30fps / H.264+AAC，音轨完整，
时长与各自旁白精确吻合）：

| 书名 | 时长 | 大小 | 输出 |
|---|---|---|---|
| 三体 | 969.53s (16:10) | 513.6MB | `20261114_三体/三体.mov` |
| 整理人生 | 929.38s (15:29) | 785.6MB | `20261114_整理人生/整理人生.mov` |
| 遥远的救世主 | 834.97s (13:55) | 592.5MB | `20261114_遥远的救世主/遥远的救世主.mov` |

> 导出期间剪映需保持前台，用户不要动鼠标键盘；若授予一次辅助功能权限，
> 可改成按 UI 名字点击，稳定性会明显更好。
