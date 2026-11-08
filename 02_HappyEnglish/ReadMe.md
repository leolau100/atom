# 📚 Happy English 开心英语

帮助小学生学习英语的 Web 应用。拍一张课本照片，自动识别英文内容，分句展示，点击朗读。

## 功能

- 📷 **拍照/上传图片** → OCR 自动识别英文文本
- ✏️ **句子编辑** → 识别错误的句子可以手动修改
- 🎧 **句子朗读** → 点击句子朗读整句，支持循环播放
- 🔤 **单词发音** → 点击任意单词单独发音
- 🌟 **朗读高亮** → 当前朗读内容实时高亮显示
- 🐢 **慢速模式** → 专为小学生设计的语速
- 📖 **历史记录** → 每次识别自动保存，随时复习

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + Vite + Pinia + TypeScript |
| 后端 | Python FastAPI |
| OCR | EasyOCR（离线，纯 Python） |
| TTS | gTTS（Google TTS，慢速模式） |
| 数据库 | SQLite |

## 快速启动

### 1. 启动后端

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py
```

后端运行在 `http://localhost:8000`，API 文档访问 `http://localhost:8000/docs`。

> ⚠️ 首次启动时 EasyOCR 会下载模型文件（约 100MB），需要网络，请耐心等待。

### 2. 启动前端

```bash
cd frontend

npm install
npm run dev
```

前端运行在 `http://localhost:5173`，打开浏览器访问即可。

## 项目结构

```
02_HappyEnglish/
├── backend/
│   ├── main.py          # FastAPI 入口，所有 API 路由
│   ├── ocr_service.py   # OCR 识别 + 句子分割
│   ├── tts_service.py   # 文字转语音
│   ├── models.py        # 数据库模型
│   ├── database.py      # SQLite 连接
│   └── requirements.txt
└── frontend/
    └── src/
        ├── views/
        │   ├── HomeView.vue     # 首页：拍照识别
        │   ├── ReadView.vue     # 阅读页：句子朗读
        │   └── HistoryView.vue  # 历史记录
        ├── stores/
        │   └── reading.ts       # 朗读状态管理
        └── api/
            └── index.ts         # 后端 API 调用
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ocr` | 上传图片，返回识别文本和句子 |
| GET | `/api/tts?text=&slow=` | 文字转语音，返回 MP3 |
| POST | `/api/records` | 保存识别记录 |
| GET | `/api/records` | 获取历史记录列表 |
| GET | `/api/records/{id}` | 获取单条记录 |
| PUT | `/api/records/{id}/sentences` | 更新句子 |
| DELETE | `/api/records/{id}` | 删除记录 |
