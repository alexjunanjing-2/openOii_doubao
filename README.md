# openOii - AI Agent 漫剧生成平台

<div align="center">

**基于多智能体协作的漫剧创作平台，让创意变成现实**
**⭐ 如果这个项目对你有帮助，请给个 Star 支持一下！⭐**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-green.svg)](https://nodejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 项目简介

本项目基于[Xeron2000/openOii](https://github.com/Xeron2000/openOii)进行了二次开发，主要增加支持火山引擎豆包 LLM、Seedream、Seedance 等模型，同时优化修复了原项目部分逻辑bug，提升了生图、生视频的角色一致性。

openOii 是一个基于 AI Agent 的智能漫剧生成平台，通过多智能体协作流程，将用户的创意故事自动转化为完整的视频作品。每个 Agent 专注于特定任务（剧本创作、角色设计、分镜绘制、视频生成等），协同完成从创意到成品的全流程。

### 核心特性

- **多智能体协作** - 8 个专业 AI Agent 分工协作完成创作流程
- **智能剧本创作** - Director 和 Scriptwriter Agent 自动生成角色、场景和分镜脚本
- **角色形象生成** - Character Artist Agent 基于描述生成一致性角色图像
- **分镜图生成** - Storyboard Artist Agent 为每个镜头生成精美的分镜首帧
- **视频自动生成** - Video Generator Agent 支持文生视频和图生视频两种模式
- **实时反馈系统** - WebSocket 实时推送各 Agent 的生成进度
- **精准重生成** - Review Agent 处理用户反馈，支持对单个内容进行重新生成

---

## 应用场景

### 创作流程

1. **创建项目** - 输入故事创意、风格偏好
2. **AI 生成** - 多智能体协作生成完整内容
3. **实时预览** - 查看角色、分镜和视频生成进度
4. **精细调整** - 对不满意的内容进行重新生成
5. **导出作品** - 获取完整的视频作品

---

## 技术架构

### 后端技术栈

| 类别 | 技术 |
|------|------|
| 框架 | FastAPI + SQLModel |
| 数据库 | SQLite |
| 缓存 | Redis (用于跨进程信号共享) |
| AI 服务 | LLM Agent SDK、图像生成接口、视频生成接口 |
| 实时通信 | WebSocket |
| 图像处理 | Pillow |

### 前端技术栈

| 类别 | 技术 |
|------|------|
| 框架 | React 18 + TypeScript |
| 路由 | React Router v7 |
| 状态管理 | Zustand |
| 数据请求 | TanStack Query |
| 样式 | Tailwind CSS + DaisyUI |
| 画布 | tldraw |
| 构建工具 | Vite |
| 测试 | Vitest + Playwright |

### 多智能体协作流程

```
用户输入
    |
    v
OnboardingAgent (需求分析)
    |
    v
DirectorAgent (导演规划)
    |
    v
ScriptwriterAgent (剧本创作)
    |
    v
CharacterArtistAgent (角色图生成)
    |
    v
StoryboardArtistAgent (分镜图生成)
    |
    v
VideoGeneratorAgent (视频生成)
    |
    v
VideoMergerAgent (视频拼接)
    |
    v
ReviewAgent (用户反馈处理)
```

---

## 快速开始

### 环境要求

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Python | 3.10+ | 后端运行环境 |
| Node.js | 18+ | 前端运行环境 |
| Redis | 6+ | 跨进程信号共享 |
| FFmpeg | 4.0+ | 视频拼接和处理 |
| uv | 0.1.0+ | Python 包管理器（推荐） |
| pnpm | 8+ | 前端包管理器 |

### 安装 Redis

**macOS (使用 Homebrew):**

```bash
brew install redis
brew services start redis
redis-cli ping  # 验证，应返回 PONG
```

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis
redis-cli ping
```

### 安装 uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 Homebrew
brew install uv
```

### 后端部署

```bash
# 1. 进入后端目录
cd backend

# 2. 安装依赖
uv sync

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填写必要的 API Key

# 4. 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 18765
```

### 前端部署

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
pnpm install

# 3. 启动开发服务器
pnpm dev

# 4. 访问应用
# 打开浏览器访问 http://localhost:15173
```

---

## 配置说明

### 关键环境变量

```env
# 数据库
DATABASE_URL=sqlite+aiosqlite:///./openoii.db

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM 服务
LLM_PROVIDER=doubao
DOUBAO_API_KEY=your_doubao_api_key
DOUBAO_LLM_MODEL=doubao-seed-1-8-251228

# 图像生成服务
IMAGE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
IMAGE_API_KEY=your_image_api_key
IMAGE_MODEL=doubao-seedream-4-5-251128

# 视频服务
VIDEO_PROVIDER=doubao
DOUBAO_VIDEO_MODEL=doubao-seedance-1-5-pro-251215
```

### 图像生成模式

| 模式 | 配置 | 说明 |
|------|------|------|
| 文生图 | `ENABLE_IMAGE_TO_IMAGE=false` | 纯文本描述生成分镜图 |
| 图生图 | `ENABLE_IMAGE_TO_IMAGE=true` | 使用角色图作为参考，提升一致性 |

### 视频生成模式

| 模式 | 配置 | 说明 |
|------|------|------|
| 文生视频 | `ENABLE_IMAGE_TO_VIDEO=false` | 纯文本描述生成视频 |
| 图生视频 | `ENABLE_IMAGE_TO_VIDEO=true` | 使用角色图和分镜图作为参考 |

---

## 项目结构

```
openOii_trae/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── agents/            # AI Agent 模块
│   │   │   ├── prompts/       # Agent 提示词模板
│   │   │   ├── base.py        # Agent 基类
│   │   │   ├── orchestrator.py # Agent 编排器
│   │   │   └── ...
│   │   ├── api/               # API 路由
│   │   ├── models/            # 数据模型
│   │   ├── schemas/           # Pydantic 模式
│   │   ├── services/          # 业务服务
│   │   ├── ws/                # WebSocket 管理
│   │   └── main.py            # 应用入口
│   ├── tests/                 # 测试文件
│   ├── pyproject.toml         # 项目配置
│   └── .env.example           # 环境变量示例
│
├── frontend/                   # 前端应用
│   ├── app/
│   │   ├── components/        # React 组件
│   │   │   ├── canvas/        # 画布组件
│   │   │   ├── chat/          # 聊天组件
│   │   │   ├── layout/        # 布局组件
│   │   │   └── ui/            # UI 组件
│   │   ├── hooks/             # 自定义 Hooks
│   │   ├── pages/             # 页面组件
│   │   ├── services/          # API 服务
│   │   ├── stores/            # Zustand 状态
│   │   └── types/             # TypeScript 类型
│   ├── public/                # 静态资源
│   ├── tests/                 # 测试文件
│   └── package.json           # 项目配置
│
├── .gitignore                  # Git 忽略配置
└── README.md                   # 项目文档
```

---

## API 文档

启动后端服务后，访问以下地址查看完整 API 文档：

- **Swagger UI**: `http://localhost:18765/docs`
- **ReDoc**: `http://localhost:18765/redoc`

---

## 测试

### 后端测试

```bash
cd backend
pytest                    # 运行所有测试
pytest --cov             # 生成覆盖率报告
pytest -v                # 详细输出
```

### 前端测试

```bash
cd frontend
pnpm test                # 单元测试
pnpm test:ui             # 测试 UI
pnpm test:coverage       # 覆盖率报告
pnpm e2e                 # E2E 测试
```

---

## 支持的 AI 服务

### LLM 服务

- **Doubao Seed** (豆包视频服务)
- **通用 LLM 接口** (支持标准 API 协议)

### 图像生成

- **豆包 Seedream**
- 任何标准图像生成接口

### 视频生成

- **豆包 Seedance** (火山引擎 Ark API，推荐)
- 任何标准视频生成接口

---

## 常见问题

### Redis 连接失败

确保 Redis 服务正在运行：

```bash
redis-cli ping  # 应返回 PONG
```

### 数据库初始化

SQLite 数据库会在首次运行时自动创建，无需手动初始化。

### 视频生成失败

1. 检查 API Key 是否正确配置
2. 确认视频服务配额充足
3. 查看后端日志获取详细错误信息

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的 Python Web 框架
- [React](https://react.dev/) - 用于构建用户界面的 JavaScript 库
- [tldraw](https://tldraw.dev/) - 强大的画布库
- [Tailwind CSS](https://tailwindcss.com/) - 实用优先的 CSS 框架
- [豆包大模型](https://www.volcengine.com/docs/82379) - 字节跳动 AI 服务
