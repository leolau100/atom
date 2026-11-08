# Requirements Document

## Introduction

微信公众号 AI 写作工作流是一套面向内容创作者（尤其是互联网职场领域博主）的结构化 AI 辅助写作系统。该工作流将公众号文章的创作过程拆解为五个清晰阶段：选题、大纲、分节初稿、风格改写、人工打磨，并通过工作流文件、写作风格 Skill、排版脚本和模板等组件，帮助创作者系统性地产出符合自身风格的高质量内容。

目标用户为互联网职场人士，内容方向涵盖职场、技术、个人成长与 AI 话题，写作风格追求口语化、短句、像真人在聊天。

---

## Glossary

- **Workflow**：主流程指令文件，定义五步写作流程的 AI 提示词模板集合
- **Skill**：可复用的 AI 提示词模块，本文中特指写作风格改写技能（`writing-style.md`）
- **Creator**：使用本工作流进行内容创作的博主或作者
- **AI_Assistant**：与 Creator 进行对话交互、执行各阶段任务的 AI 系统
- **Draft**：由 AI_Assistant 生成的文章初稿内容（按节输出）
- **Section**：文章的一个独立小节，字数目标为 200-300 字
- **Format_Script**：执行微信公众号排版的自动化脚本（`format.js`）
- **Cover_Script**：生成封面图的自动化脚本（`cover.js`）
- **Publish_Script**：将文章推送至微信公众号草稿箱的自动化脚本（`publish.js`）
- **Style_Guide**：写作风格指南文件（`writing-style.md`），定义博主的个人写作风格
- **Topic**：经 Creator 确认的文章选题方向
- **Outline**：经 Creator 确认的文章大纲，包含 6-8 个节标题及核心内容说明

---

## Requirements

### Requirement 1: 选题生成

**User Story:** 作为 Creator，我希望在提供身份背景和主题方向后，AI_Assistant 能给出多个差异化的选题方向，以便我快速找到最适合当前创作的切入点。

#### Acceptance Criteria

1. WHEN Creator 提供身份描述和主题方向，THE AI_Assistant SHALL 生成恰好 5 个选题方向
2. THE AI_Assistant SHALL 为每个选题方向提供一句话说明，内容包含切入点和读者收益两个要素
3. THE AI_Assistant SHALL 确保 5 个选题方向彼此角度不重复，覆盖至少 3 种不同叙事视角（如：问题驱动、方法论、故事型、观点型、工具型）
4. WHEN Creator 对某个选题方向提出修改意见，THE AI_Assistant SHALL 根据反馈替换或调整对应选题，并重新输出完整的 5 个方向
5. IF Creator 未提供身份描述，THEN THE AI_Assistant SHALL 提示 Creator 补充身份信息后再继续

---

### Requirement 2: 大纲生成

**User Story:** 作为 Creator，我希望在确定选题后先获得一份完整大纲而非直接全文，以便我在正式写作前调整文章结构和方向。

#### Acceptance Criteria

1. WHEN Creator 确认 Topic，THE AI_Assistant SHALL 输出包含 6 到 8 个 Section 的 Outline
2. THE AI_Assistant SHALL 为 Outline 中每个 Section 提供一句话的核心内容说明
3. THE Outline SHALL 包含场景引入节（位于第一节）、具体方法节（至少 2 节）和互动环节节（位于最后一节）
4. WHEN Creator 要求调整 Outline 中的某节，THE AI_Assistant SHALL 修改对应节并保持其余节不变
5. WHEN Creator 要求重新生成整份 Outline，THE AI_Assistant SHALL 基于同一 Topic 输出一份结构不同的新 Outline
6. IF Creator 尚未确认 Topic，THEN THE AI_Assistant SHALL 拒绝生成 Outline，并提示 Creator 先完成选题步骤

---

### Requirement 3: 分节初稿生成

**User Story:** 作为 Creator，我希望 AI 每次只写一节内容，以便我在每节完成后审阅并保持前后衔接，避免整篇跑偏。

#### Acceptance Criteria

1. WHEN Creator 指示开始写作某一 Section，THE AI_Assistant SHALL 仅输出该 Section 的 Draft，字数严格控制在 200 到 300 字之间，超过 300 字的 Draft 不得输出
2. THE Draft SHALL 使用口语化语言，以「你」「我」作为人称代词，语感接近朋友间的日常对话
3. THE Draft SHALL 避免使用书面化套语，包括但不限于「此外」「综上所述」「希望对你有帮助」「总体而言」
4. WHEN Creator 确认当前 Section 的 Draft 后，THE AI_Assistant SHALL 在生成下一节 Draft 时保持与上一节的主题衔接和语气一致
5. IF Creator 要求修改当前 Section，THEN THE AI_Assistant SHALL 重新输出该 Section 的 Draft，字数严格控制在 200 到 300 字之间，超过 300 字须自行压缩后再输出
6. WHEN Creator 请求生成所有 Section 的 Draft，THE AI_Assistant SHALL 拒绝一次性输出全文，并告知 Creator 需按节逐步推进

---

### Requirement 4: 写作风格改写

**User Story:** 作为 Creator，我希望将初稿一键改写为符合我个人风格的版本，以便文章读起来像我写的而非 AI 生成的。

#### Acceptance Criteria

1. WHEN Creator 触发风格改写并提供完整初稿，THE AI_Assistant SHALL 依据 Style_Guide 对全文进行风格改写，输出改写后的完整文章
2. THE AI_Assistant SHALL 在改写过程中将长句拆分为短句，确保单个段落不超过 3 行
3. THE AI_Assistant SHALL 在改写过程中删除或替换书面化套语（如「此外」「综上所述」「希望对你有帮助」）
4. WHERE Style_Guide 未加载或不可用，THE AI_Assistant SHALL 提示 Creator 在对话中直接描述风格偏好，并依据描述执行改写
5. THE AI_Assistant SHALL 保留改写前后文章的核心信息和主要论点，不得删减实质内容
6. WHEN Creator 对改写结果提出具体修改意见，THE AI_Assistant SHALL 对指定段落重新改写并保持全文风格一致

---

### Requirement 5: 人工打磨指引

**User Story:** 作为 Creator，我希望在 AI 完成改写后获得清晰的人工打磨指引，以便我知道哪些地方需要亲自动手，让文章更有个人温度。

#### Acceptance Criteria

1. WHEN 风格改写完成，THE AI_Assistant SHALL 输出人工打磨检查清单，包含以下三项：加入真实案例或个人经历、调整开头和结尾、删除冗余内容
2. THE AI_Assistant SHALL 在检查清单中标注文章中适合插入个人经历的具体位置（如第 N 节第 M 段）
3. THE AI_Assistant SHALL 识别文章中「正确但不必要」的段落，并以注释形式标注，供 Creator 决策是否删除
4. THE AI_Assistant SHALL 对文章开头第一段进行评分（1-5 分），并说明是否具备足够的抓人效果，如评分低于 4 分，则提供 2 个替代开头供 Creator 参考
5. IF Creator 要求跳过人工打磨指引，THEN THE AI_Assistant SHALL 直接进入后续排版或发布流程

---

### Requirement 6: 写作风格 Skill 管理

**User Story:** 作为 Creator，我希望有一个可维护的写作风格文件，以便在不同文章的创作中保持风格一致，并随时更新我的个人风格偏好。

#### Acceptance Criteria

1. THE Style_Guide SHALL 包含公众号基本信息（账号名称、目标读者、内容方向）
2. THE Style_Guide SHALL 定义至少两种写作模式，包括「正常模式」（稳健、信息密度高）和「放飞模式」（更口语、更随性、更有梗）
3. WHEN Creator 更新 Style_Guide 中的风格规则，THE AI_Assistant SHALL 在后续所有改写任务中使用更新后的规则
4. THE Style_Guide SHALL 包含禁用词列表，列举不得在文章中出现的书面化表达
5. WHEN Creator 切换写作模式，THE AI_Assistant SHALL 确认当前使用的模式并在改写时严格遵循对应模式的风格规则

---

### Requirement 7: 排版与发布自动化

**User Story:** 作为 Creator，我希望文章完成后能通过脚本自动完成排版、封面生成和推送草稿箱，以便减少重复的手动操作，专注于内容本身。

#### Acceptance Criteria

1. WHEN Creator 执行 Format_Script，THE Format_Script SHALL 将文章内容应用至排版模板（`format-template.html`）并输出符合微信公众号格式的 HTML 文件
2. WHEN Creator 执行 Cover_Script，THE Cover_Script SHALL 基于封面模板（`cover-template.html`）和文章标题生成封面图文件
3. WHEN Creator 执行 Publish_Script，THE Publish_Script SHALL 将排版后的文章和封面图推送至微信公众号草稿箱
4. IF Format_Script 执行过程中发生错误，THEN THE Format_Script SHALL 输出包含错误原因和建议操作的错误信息，并终止执行
5. IF Publish_Script 推送失败（如 API Token 过期或网络错误），THEN THE Publish_Script SHALL 输出包含失败原因的错误信息，并保留本地排版文件不删除
6. THE Publish_Script SHALL 在推送成功后输出草稿箱链接或成功确认信息

---

### Requirement 8: 工作流文件结构与可维护性

**User Story:** 作为 Creator，我希望工作流的所有文件按清晰的目录结构组织，以便我能快速找到、更新和复用各个组件。

#### Acceptance Criteria

1. THE Workflow SHALL 遵循以下目录结构：根目录包含 `workflow.md`，`skills/` 子目录包含 `writing-style.md`，`scripts/` 子目录包含 `format.js`、`cover.js`、`publish.js`，`templates/` 子目录包含 `format-template.html` 和 `cover-template.html`
2. THE `workflow.md` SHALL 包含五个写作阶段的完整 AI 提示词模板，每个阶段单独成节，并注明输入参数和预期输出格式
3. WHEN Creator 修改任意组件文件，THE Workflow 中其他组件不得因该修改而失效（各组件之间保持松耦合）
4. THE `workflow.md` SHALL 在文件顶部包含快速参考索引，列明五个阶段的名称和对应文件位置
