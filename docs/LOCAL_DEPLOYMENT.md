# AudioBook Reader - macOS 本地开发部署手册

> **适用环境**: macOS (Apple Silicon M1/M2/M3)  
> **最后更新**: 2026-01-30

---

## 目录

1. [系统要求](#1-系统要求)
2. [环境准备](#2-环境准备)
3. [项目初始化](#3-项目初始化)
4. [数据准备工具](#4-数据准备工具)
5. [后端开发](#5-后端开发)
6. [前端开发](#6-前端开发)
7. [Docker 开发环境](#7-docker-开发环境)
8. [常用命令速查](#8-常用命令速查)
9. [故障排除](#9-故障排除)

---

## 1. 系统要求

| 软件    | 最低版本 | 推荐版本 | 用途            |
| ------- | -------- | -------- | --------------- |
| macOS   | 13.0     | 14.0+    | 操作系统        |
| Python  | 3.11     | 3.12     | 后端 + 数据准备 |
| Node.js | 20.0     | 22.0+    | 前端开发        |
| Docker  | 24.0     | 27.0+    | 容器化          |
| pnpm    | 8.0      | 9.0+     | 前端包管理      |
| Git     | 2.0      | 最新     | 版本控制        |

---

## 2. 环境准备

### 2.1 安装 Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2.2 安装必要软件

```bash
# Python 3.12
brew install python@3.12

# Node.js 22
brew install node@22

# pnpm
corepack enable
corepack prepare pnpm@latest --activate

# Git
brew install git

# Docker Desktop（需手动下载安装）
# 下载地址: https://www.docker.com/products/docker-desktop/

# FFmpeg（音频处理）
brew install ffmpeg
```

### 2.3 验证安装

```bash
python3 --version    # 应显示 Python 3.11+ 或 3.12+
node --version       # 应显示 v20+ 或 v22+
pnpm --version       # 应显示 8+ 或 9+
docker --version     # 应显示 Docker version 24+
ffmpeg -version      # 应显示 ffmpeg version
```

---

## 3. 项目初始化

### 3.1 克隆项目

```bash
cd ~/dev
git clone https://github.com/YOUR_USERNAME/Audiobook_web_APP.git
cd Audiobook_web_APP
```

### 3.2 创建环境配置

```bash
# 从模板创建 .env 文件
cp .env.example .env

# 编辑配置（开发环境可使用默认值）
nano .env
```

### 3.3 创建必要目录

```bash
# 创建媒体和数据目录
mkdir -p media/books
mkdir -p pgdata
mkdir -p certbot/conf certbot/www
```

---

## 4. 数据准备工具

> 用于在 MacBook 本地生成音频-文本对齐数据

### 4.1 设置 Python 虚拟环境

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r scripts/requirements.txt
```

### 4.2 验证 MLX GPU 加速

```bash
# 验证 MLX 安装
python -c "import mlx.core as mx; print(f'MLX 版本: {mx.__version__}')"

# 验证 stable-ts 安装
python -c "import stable_whisper; print(f'stable-ts 版本: {stable_whisper.__version__}')"
```

### 4.3 准备音频文件

```bash
# 创建测试目录（如需要）
mkdir -p audiobook_files

# 文件命名格式:
# audiobook_files/
# ├── 001.mp3
# ├── 001.txt
# ├── 002.mp3
# ├── 002.txt
# └── ...
```

### 4.4 配置对齐脚本

编辑 `scripts/prepare_alignment.py` 顶部的配置区域:

```python
# 输入文件夹路径
INPUT_FOLDER = "/Users/max/dev/Audiobook_web_APP/audiobook_files"

# 输出文件（会保存在 INPUT_FOLDER 中）
OUTPUT_ALIGNMENT_JSON = "alignment.json"
OUTPUT_MERGED_AUDIO = "merged_book.mp3"

# 模型设置
MODEL_SIZE = "medium"  # tiny, base, small, medium, large
LANGUAGE = "zh"        # zh, en, ja, etc.

# 是否合并音频
MERGE_AUDIO = True
```

### 4.5 运行对齐脚本

```bash
# 激活虚拟环境
source .venv/bin/activate

# 运行脚本
python scripts/prepare_alignment.py
```

脚本会输出:

- `alignment.json` - 音频对齐数据
- `merged_book.mp3` - 合并后的完整音频（如启用）

---

## 5. 后端开发

### 5.1 安装后端依赖

```bash
cd backend

# 创建虚拟环境（与 scripts 独立）
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 5.2 配置数据库（需先启动 Docker）

```bash
# 返回项目根目录
cd ..

# 启动数据库容器
docker compose -f docker-compose.dev.yml up -d db

# 等待数据库就绪（约 10 秒）
sleep 10

# 验证数据库连接
docker compose -f docker-compose.dev.yml exec db psql -U audiobook -d audiobook -c "SELECT 1;"
```

### 5.3 运行数据库迁移

```bash
cd backend
source .venv/bin/activate

# 初始化 Alembic（首次）
alembic init alembic

# 生成迁移文件
alembic revision --autogenerate -m "initial"

# 运行迁移
alembic upgrade head
```

### 5.4 启动后端服务

```bash
cd backend
source .venv/bin/activate

# 开发模式（热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# 后端 API 文档: http://localhost:8001/docs
```

---

## 6. 前端开发

### 6.1 安装前端依赖

```bash
cd frontend

# 安装依赖
pnpm install
```

### 6.2 配置 API 代理

确认 `frontend/vite.config.ts` 中的代理配置:

```typescript
server: {
  port: 5173,
  proxy: {
    '/api': {
      target: 'http://localhost:8001',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, '')
    }
  }
}
```

### 6.3 启动前端开发服务器

```bash
cd frontend

# 开发模式（热重载）
pnpm dev

# 前端地址: http://localhost:5173
```

### 6.4 构建生产版本

```bash
cd frontend

# 构建
pnpm build

# 预览构建结果
pnpm preview
```

---

## 7. Docker 开发环境

### 7.1 启动完整开发环境

```bash
# 返回项目根目录
cd ~/dev/Audiobook_web_APP

# 启动数据库和后端
docker compose -f docker-compose.dev.yml up -d

# 查看状态
docker compose -f docker-compose.dev.yml ps

# 查看日志
docker compose -f docker-compose.dev.yml logs -f
```

### 7.2 服务端口

| 服务       | 端口 | 说明             |
| ---------- | ---- | ---------------- |
| PostgreSQL | 5433 | 数据库           |
| FastAPI    | 8001 | 后端 API         |
| SvelteKit  | 5173 | 前端（本地运行） |

### 7.3 停止服务

```bash
# 停止所有容器
docker compose -f docker-compose.dev.yml down

# 停止并删除数据卷（清除数据）
docker compose -f docker-compose.dev.yml down -v
```

---

## 8. 常用命令速查

### 项目管理

```bash
# 使用 Makefile 快捷命令
make dev          # 启动开发环境
make down         # 停止所有服务
make logs         # 查看日志
make migrate      # 运行数据库迁移
make clean        # 清理数据（危险！）
```

### 数据准备

```bash
# 激活脚本虚拟环境
source .venv/bin/activate

# 运行对齐脚本
python scripts/prepare_alignment.py

# 退出虚拟环境
deactivate
```

### 后端开发

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

### 前端开发

```bash
cd frontend
pnpm dev
```

### Git 操作

```bash
git status
git add .
git commit -m "feat: add new feature"
git push origin main
```

---

## 9. 故障排除

### 问题: MLX GPU 加速不可用

**症状**: 脚本显示 "FP16 is not supported on CPU"

**解决**:

```bash
# 确保安装了 mlx-whisper
pip install --upgrade mlx-whisper

# 验证 MLX
python -c "import mlx.core as mx; print(mx.default_device())"
# 应显示: gpu
```

### 问题: Docker 容器无法启动

**症状**: `docker compose up` 失败

**解决**:

```bash
# 检查 Docker Desktop 是否运行
docker info

# 清理旧容器
docker compose down
docker system prune -f

# 重新启动
docker compose -f docker-compose.dev.yml up -d
```

### 问题: 端口被占用

**症状**: "address already in use"

**解决**:

```bash
# 查找占用端口的进程
lsof -i :5433  # PostgreSQL
lsof -i :8001  # FastAPI
lsof -i :5173  # SvelteKit

# 终止进程
kill -9 <PID>
```

### 问题: Node.js 版本不对

**症状**: 前端构建失败

**解决**:

```bash
# 使用 nvm 管理 Node 版本
brew install nvm
nvm install 22
nvm use 22
```

### 问题: pnpm 命令不存在

**解决**:

```bash
corepack enable
corepack prepare pnpm@latest --activate
```

---

## 附录: 项目目录结构

```
Audiobook_web_APP/
├── .env                    # 环境变量（不提交到 Git）
├── .env.example            # 环境变量模板
├── .gitignore              # Git 忽略文件
├── .venv/                  # Python 虚拟环境（数据准备工具）
├── Makefile                # 快捷命令
├── docker-compose.yml      # 生产环境
├── docker-compose.dev.yml  # 开发环境
│
├── scripts/                # 数据准备工具（MacBook 本地）
│   ├── prepare_alignment.py
│   └── requirements.txt
│
├── backend/                # FastAPI 后端
│   ├── .venv/              # 后端虚拟环境
│   ├── app/
│   └── requirements.txt
│
├── frontend/               # SvelteKit 前端
│   ├── node_modules/
│   ├── src/
│   └── package.json
│
├── nginx/                  # Nginx 配置
├── media/                  # 媒体文件（挂载卷）
├── pgdata/                 # 数据库数据（挂载卷）
└── audiobook_files/        # 测试音频文件（本地，不提交）
```
