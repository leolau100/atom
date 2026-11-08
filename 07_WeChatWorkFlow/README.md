# 微信公众号 AI 写作工作流

一套面向内容创作者的结构化 AI 辅助写作系统，将公众号文章创作拆解为五个清晰阶段，并通过自动化脚本完成排版、封面生成和发布。

---

## 项目用途

帮助互联网职场内容创作者（博主、KOL）用 AI 系统性地产出符合个人风格的高质量公众号文章，同时通过脚本自动化搞定排版、封面和草稿箱推送。

**目标用户**：互联网职场人士，内容方向涵盖职场经验、技术认知、个人成长与 AI 工具实践。

---

## 目录结构

```
WeChatWorkFlow/
├── workflow.md              # 五步写作工作流主文件（AI 提示词模板）
├── skills/
│   └── writing-style.md     # 个人写作风格 Skill（供 AI 改写时加载）
├── scripts/
│   ├── format.js            # 排版脚本：Markdown → 微信兼容 HTML
│   ├── cover.js             # 封面生成脚本：标题 → PNG 封面图
│   └── publish.js           # 发布脚本：推送文章和封面至草稿箱
├── templates/
│   ├── format-template.html # 文章排版 HTML 模板
│   └── cover-template.html  # 封面图 HTML 模板
├── articles/                # 放置你的 Markdown 文章
├── output/                  # 脚本生成的文件（HTML、PNG）
├── package.json
├── .env.example             # 环境变量模板
└── .env                     # 你的微信公众号凭据（勿提交到 Git）
```

---

## 快速上手

### 环境要求

- **Node.js** v18 或以上（推荐 v20 LTS）
- npm v8+

### 安装依赖

```bash
npm install
```

安装完成后，`puppeteer` 会自动下载 Chromium，用于封面图渲染，耗时视网络情况而定。

### 配置 `.env`

1. 复制模板文件：

   ```bash
   cp .env.example .env
   ```

2. 编辑 `.env`，填入你的微信公众号凭据：

   ```env
   WECHAT_APP_ID=你的AppID
   WECHAT_APP_SECRET=你的AppSecret
   ```

   > AppID 和 AppSecret 在[微信公众平台](https://mp.weixin.qq.com) → 设置与开发 → 基本配置中获取。

3. `.env` 已在 `.gitignore` 中忽略，请勿将真实凭据提交到代码仓库。

---

## 五步写作流程

在你使用的 AI 工具（如 Kiro IDE）中加载工作流文件，即可开始结构化创作。

### 加载方式

1. 在 AI 工具中打开 `workflow.md`（工作流主文件）
2. 在 AI 工具中加载 `skills/writing-style.md` 作为 Skill

   > `writing-style.md` 定义了你的个人写作风格，AI 在 Stage 4 改写时会自动引用。

### 五个阶段

| 阶段 | 名称 | 输入 | 输出 |
|------|------|------|------|
| Stage 1 | 选题生成 | 身份描述 + 主题方向 | 5 个差异化选题方向 |
| Stage 2 | 大纲生成 | 确认的选题 | 6-8 节大纲 |
| Stage 3 | 分节初稿 | 大纲 + 节序号 | 单节草稿（200-300 字），每一节都要即时输出到文章中 |
| Stage 4 | 风格改写 | 完整初稿 | 符合个人风格的改写稿 |
| Stage 5 | 人工打磨指引 | 改写稿 | 打磨清单 + 开头评分 |

**典型工作流**：

```
Stage 1 → 选一个选题 → Stage 2 → 确认大纲 → Stage 3（逐节）→
将所有节汇总 → Stage 4 → Stage 5 → 保存为 articles/article.md
```

### 自定义写作风格

编辑 `skills/writing-style.md`：

- 修改「公众号基本信息」填入你自己的账号、读者和内容方向
- 在「当前激活模式」字段切换**正常模式**（干货型）或**放飞模式**（互动型）
- 维护「禁用词列表」，把你不想用的词加进去

---

## 脚本使用

文章写完并保存到 `articles/` 目录后，依次运行以下三个脚本。

### 1. 排版（format）

将 Markdown 文章转换为微信公众号兼容的 HTML：

```bash
# 使用默认路径，输出到 output/article.html
npm run format -- articles/article.md

# 自定义输出路径
npm run format -- articles/article.md --output output/my-article.html
```

等价的 node 命令：

```bash
node scripts/format.js articles/article.md
node scripts/format.js articles/article.md --output output/my-article.html
```

### 2. 生成封面（cover）

基于文章标题生成封面图（900×383 px，PNG 格式）：

```bash
# 使用默认路径，输出到 output/cover.png
npm run cover -- "职场沟通的 5 个误区"

# 自定义输出路径
npm run cover -- "职场沟通的 5 个误区" --output output/my-cover.png
```

等价的 node 命令：

```bash
node scripts/cover.js "职场沟通的 5 个误区"
node scripts/cover.js "职场沟通的 5 个误区" --output output/my-cover.png
```

### 3. 发布到草稿箱（publish）

将文章 HTML 和封面图推送至微信公众号草稿箱：

```bash
# 使用默认路径（output/article.html + output/cover.png）
npm run publish

# 指定自定义路径
npm run publish -- --article output/my-article.html --cover output/my-cover.png
```

等价的 node 命令：

```bash
node scripts/publish.js
node scripts/publish.js --article output/article.html --cover output/cover.png
```

发布成功后，脚本会输出草稿 `media_id`，前往[微信公众平台草稿箱](https://mp.weixin.qq.com)查看文章。

### 完整一键流程示例

```bash
# 假设文章已保存为 articles/article.md，标题为「5 个让你少加班的 AI 技巧」
npm run format -- articles/article.md
npm run cover -- "5 个让你少加班的 AI 技巧"
npm run publish
```

---

## 帮助信息

每个脚本均支持 `--help` 参数：

```bash
node scripts/format.js --help
node scripts/cover.js --help
node scripts/publish.js --help
```

---

## 注意事项

- 发布脚本需要有效的微信公众号 AppID 和 AppSecret（订阅号默认无法调用草稿箱接口，需申请服务号或开启开发者权限）
- `output/` 目录下的文件不会被 Git 追踪，推送失败时本地文件不会被删除
- 封面图渲染依赖 puppeteer 内置的 Chromium，首次 `npm install` 下载时间较长，请耐心等待
