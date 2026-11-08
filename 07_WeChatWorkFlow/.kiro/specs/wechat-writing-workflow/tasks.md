# Implementation Plan

## Overview

本实现计划将微信公众号 AI 写作工作流按照设计文档分解为 9 个独立任务，涵盖项目目录结构、workflow 主文件、写作风格 Skill、HTML 模板、Node.js 脚本和 README 文档的创建。

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1"] },
    { "wave": 2, "tasks": ["2", "3", "4", "5"] },
    { "wave": 3, "tasks": ["6", "7", "8"] },
    { "wave": 4, "tasks": ["9"] }
  ],
  "dependencies": {
    "2": ["1"],
    "3": ["1"],
    "4": ["1"],
    "5": ["1"],
    "6": ["4", "5"],
    "7": ["4", "5"],
    "8": ["5"],
    "9": ["1", "2", "3", "4", "5", "6", "7", "8"]
  }
}
```

## Tasks

- [x] 1. 创建项目目录结构
  - 在项目根目录创建 `skills/`、`scripts/`、`templates/`、`output/`、`articles/` 子目录
  - 创建 `.gitignore` 文件，忽略 `output/`、`.env`、`node_modules/`
  - _Requirements: 8_

- [x] 2. 创建写作风格 Skill 文件 skills/writing-style.md
  - 依赖 Task 1
  - 创建 `skills/writing-style.md`，包含公众号基本信息节（账号名称、目标读者、内容方向）
  - 添加「正常模式」定义（稳健、信息密度高的风格规则）和「放飞模式」定义（口语化、随性、有梗）
  - 添加「当前激活模式」字段，默认设为「正常模式」
  - 添加禁用词列表：「此外」「综上所述」「希望对你有帮助」「总体而言」等书面化套语
  - _Requirements: 6_

- [x] 3. 创建工作流主文件 workflow.md
  - 依赖 Task 1
  - 创建 `workflow.md`，文件顶部添加快速参考索引，列明五个阶段名称和对应文件位置
  - 添加 Stage 1（选题生成）提示词模板：输入参数 `{identity}`、`{topic_direction}`，输出 5 个差异化选题方向
  - 添加 Stage 2（大纲生成）提示词模板：输入参数 `{confirmed_topic}`，输出 6-8 节大纲
  - 添加 Stage 3（分节初稿）提示词模板：输入参数 `{outline}`、`{section_index}`、`{previous_section_summary}`，输出 200-300 字单节草稿
  - 添加 Stage 4（风格改写）提示词模板：显式引用 `skills/writing-style.md`，输入参数 `{full_draft}`
  - 添加 Stage 5（人工打磨指引）提示词模板：输入参数 `{rewritten_article}`，输出打磨检查清单、标注位置和开头评分
  - _Requirements: 1, 2, 3, 4, 5, 8_

- [x] 4. 创建 HTML 模板文件
  - 依赖 Task 1
  - 创建 `templates/format-template.html`，包含微信公众号兼容的基础 HTML 结构、内联 CSS 样式和占位符 `{{title}}`、`{{content}}`、`{{author}}`
  - 创建 `templates/cover-template.html`，包含封面图生成所需的 HTML 结构和标题占位符 `{{title}}`
  - _Requirements: 7, 8_

- [x] 5. 初始化 Node.js 项目
  - 依赖 Task 1
  - 创建 `package.json`，定义项目名称、版本、描述和脚本命令（`format`、`cover`、`publish`）
  - 添加生产依赖声明：`marked`（Markdown 解析）、`puppeteer`（封面图渲染）、`axios`（HTTP 请求）、`dotenv`（环境变量）
  - 创建 `.env.example`，包含 `WECHAT_APP_ID` 和 `WECHAT_APP_SECRET` 占位符说明
  - _Requirements: 7, 8_

- [x] 6. 实现排版脚本 scripts/format.js
  - 依赖 Task 4, Task 5
  - 创建 `scripts/format.js`，实现命令行参数解析（`article_path`、`--output`）
  - 实现读取 Markdown 文件并使用 `marked` 解析为 HTML，注入 `templates/format-template.html` 占位符，写入 `output/article.html`
  - 实现错误处理：文件不存在或模板解析失败时输出含错误原因和建议操作的错误信息，以非零状态码退出
  - _Requirements: 7_

- [x] 7. 实现封面生成脚本 scripts/cover.js
  - 依赖 Task 4, Task 5
  - 创建 `scripts/cover.js`，实现命令行参数解析（`title`、`--output`）
  - 实现读取 `templates/cover-template.html`，注入标题，使用 `puppeteer` 渲染为图片并保存至 `output/cover.png`
  - 实现错误处理：模板不存在或渲染失败时输出错误信息并以非零状态码退出
  - _Requirements: 7_

- [x] 8. 实现发布脚本 scripts/publish.js
  - 依赖 Task 5
  - 创建 `scripts/publish.js`，实现命令行参数解析（`--article`、`--cover`）
  - 使用 `dotenv` 加载 `.env` 配置，实现获取微信 Access Token、上传封面图至素材库、推送文章至草稿箱的完整流程
  - 实现错误处理：API Token 过期或网络错误时输出含失败原因的错误信息，保留本地文件不删除；推送成功后输出草稿箱链接
  - _Requirements: 7_

- [x] 9. 创建项目 README.md
  - 依赖 Task 1, Task 2, Task 3, Task 4, Task 5, Task 6, Task 7, Task 8
  - 创建 `README.md`，说明项目用途、目标用户和目录结构
  - 添加快速上手指南：Node.js 版本要求、安装依赖、配置 `.env` 步骤
  - 添加五步写作流程说明，指引 Creator 如何在 AI 工具中加载 `workflow.md` 和 `writing-style.md`
  - 添加脚本使用示例（format、cover、publish 命令）
  - _Requirements: 8_

## Notes

- Task 6、Task 7 依赖 Task 4（模板文件）和 Task 5（package.json），需在这两个任务完成后执行
- Task 8 仅依赖 Task 5（package.json）
- Task 9 在所有其他任务完成后执行，确保文档描述的内容均已实现
- scripts/ 目录下的脚本需要先执行 `npm install` 安装依赖才能运行
- 微信公众号 API 需要认证，发布脚本依赖有效的 AppID 和 AppSecret
