# AudioBook Reader - 云服务器部署手册 (集成版)

> **适用环境**: 现有 Ubuntu 服务器 (已安装 Nginx + SSL)
> **最后更新**: 2026-02-06
> **说明**: 本文档专门针对将应用部署到已运行 Nginx 和 HTTPS 的现有服务器。

---

## 目录

1. [准备工作 (无需 Root)](#1-准备工作)
2. [配置项目 (无需 Root)](#2-配置项目)
3. [集成 Nginx (需要 Root)](#3-集成-nginx)
4. [启动服务 (无需 Root)](#4-启动服务)
5. [运维命令 (无需 Root)](#5-运维命令)

> **权限说明**: 文档中所有 `sudo` 开头的命令需要 Root 权限，其他命令建议使用普通用户执行。

---

## 1. 准备工作

### 1.1 确认环境

确保服务器已安装 Docker 和 Docker Compose。

```bash
docker compose version
# 如果未安装，请先安装 Docker
```

### 1.2 克隆项目

```bash
# 创建项目目录
mkdir -p ~/apps
cd ~/apps

# 克隆项目 (替换为你的实际仓库地址)
git clone https://github.com/YOUR_USERNAME/Audiobook_web_APP.git
cd Audiobook_web_APP
```

### 1.3 创建数据目录

```bash
mkdir -p media/books
mkdir -p pgdata
mkdir -p logs
```

---

## 2. 配置项目

### 2.1 配置环境变量 (.env)

创建并编辑 `.env` 文件：

```bash
cp .env.example .env
vim .env
```

**关键配置项 (请务必修改)**：

我们将在 Docker 内部运行一个 Nginx，监听本地端口 **8123** (避免占用主服务器的 80/443)，然后配置主服务器的 Nginx 转发流量过去。

```ini
# ========== 端口配置 ==========
# 核心设置：将 Docker 内部 Nginx 映射到本地 8123 端口
HTTP_PORT=8123
# HTTPS 端口留空或随意，因为我们使用主服务器处理 SSL
HTTPS_PORT=8443

# ========== 数据库 ==========
DB_USER=audiobook
DB_PASSWORD=YOUR_STRONG_PASSWORD_HERE
DB_NAME=audiobook

# ========== 安全 ==========
# 生成方式：openssl rand -hex 32
SECRET_KEY=YOUR_GENERATED_SECRET_KEY

# ========== 域名 ==========
DOMAIN=strollunreal.com
CORS_ORIGINS=https://strollunreal.com
PUBLIC_API_URL=https://strollunreal.com/api

# ========== 邮件服务 (可选) ==========
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@your-domain.com
SMTP_PASSWORD=YOUR_SMTP_PASSWORD
SMTP_FROM=noreply@your-domain.com

# ========== 管理员 ==========
ADMIN_EMAIL=admin@strollunreal.com
ADMIN_PASSWORD=YOUR_ADMIN_PASSWORD
```

### 2.2 修改 docker-compose.yml (可选)

由于主服务器处理 SSL，我们可以禁用 Docker 内的 Certbot 服务以节省资源（可选，不改也没关系，只是会报错提示证书无法更新）。

打开 `docker-compose.yml`，修改如下：

```
version: "3.9"

services:
  # PostgreSQL 17 数据库
  db:
    image: postgres:17-alpine
    container_name: audiobook_db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${DB_USER:-audiobook}
      POSTGRES_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD is required}
      POSTGRES_DB: ${DB_NAME:-audiobook}
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - ./pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-audiobook} -d ${DB_NAME:-audiobook}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - audiobook_network

  # FastAPI 后端
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: audiobook_backend
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql+asyncpg://${DB_USER:-audiobook}:${DB_PASSWORD}@db:5432/${DB_NAME:-audiobook}
      - SECRET_KEY=${SECRET_KEY:?SECRET_KEY is required}
      - CORS_ORIGINS=${CORS_ORIGINS:-https://yourdomain.com}
      - MEDIA_PATH=/app/media
      - SMTP_HOST=${SMTP_HOST}
      - SMTP_PORT=${SMTP_PORT:-587}
      - SMTP_USER=${SMTP_USER}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
      - SMTP_FROM=${SMTP_FROM}
      - ADMIN_EMAIL=${ADMIN_EMAIL}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
    volumes:
      - ./media:/app/media
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - audiobook_network

  # SvelteKit 前端
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - PUBLIC_API_URL=${PUBLIC_API_URL:-/api}
    container_name: audiobook_frontend
    restart: unless-stopped
    depends_on:
      - backend
    networks:
      - audiobook_network

  # Nginx 反向代理 (内部网关)
  nginx:
    image: nginx:1.27-alpine
    container_name: audiobook_nginx
    restart: unless-stopped
    ports:
      # 只暴露 HTTP 端口供宿主机 Nginx 反向代理
      - "${HTTP_PORT:-80}:80"
      # - "${HTTPS_PORT:-443}:443" # 不需要 HTTPS，由宿主机处理
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./media:/var/www/media:ro
      # 不需要 Certbot 卷
      # - ./certbot/conf:/etc/letsencrypt:ro
      # - ./certbot/www:/var/www/certbot:ro
    depends_on:
      - frontend
      - backend
    networks:
      - audiobook_network

  # Let's Encrypt 证书 (已移除，使用宿主机证书)
  # certbot:
  #   image: certbot/certbot
  #   ...


networks:
  audiobook_network:
    driver: bridge

volumes:
  pgdata:
  media:

```

---

## 3. 集成 Nginx

这是最关键的一步。我们需要修改服务器上现有的 Nginx 配置，将主域名的流量转发到我们的 Docker 应用（运行在 8123 端口）。

### 3.1 编辑配置文件

编辑你当前的 Nginx 配置文件：

```bash
sudo vim /etc/nginx/conf.d/v2rayssl_site.conf
```

### 3.2 配置文件内容 (直接覆盖或修改)

请使用以下配置替换或修改原有内容。**注意保留你的 SSL 路径和现有特殊 `location` 块**。

```nginx
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name strollunreal.com;

    # ========== SSL 配置 (保持不变) ==========
    ssl_certificate       /nginxweb/cert/server_fullchain.cert;
    ssl_certificate_key   /nginxweb/cert/server.key;
    ssl_protocols         TLSv1.2 TLSv1.3;
    ssl_ciphers           TLS-AES-256-GCM-SHA384:TLS-CHACHA20-POLY1305-SHA256:TLS-AES-128-GCM-SHA256:TLS-AES-128-CCM-8-SHA256:TLS-AES-128-CCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES256-SHA384:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256;

    ssl_early_data on;
    ssl_stapling on;
    ssl_stapling_verify on;
    add_header Strict-Transport-Security "max-age=31536000";

    # ========== 上传限制优化 ==========
    # 允许上传最大 500M 的文件 (书籍/音频)
    client_max_body_size 500M;

    # ========== 现有应用路由 (保持不变) ==========

    # 现有业务 1
    location /pm1dsl {
        proxy_pass http://127.0.0.1:21215;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 现有业务 2 (gRPC)
    location /8f252770 {
        grpc_pass grpc://127.0.0.1:35297;
        grpc_connect_timeout 60s;
        grpc_read_timeout 720m;
        grpc_send_timeout 720m;
        grpc_set_header X-Real-IP $remote_addr;
        grpc_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # ========== Audiobook App 主路由 (新加) ==========
    # 将其他所有请求转发给 Docker 容器 (端口 8123)
    location / {
        proxy_pass http://127.0.0.1:8123;

        # 必要的代理头
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTP 自动跳转 HTTPS (保持不变)
server {
    listen 80;
    listen [::]:80;
    server_name strollunreal.com;
    return 301 https://strollunreal.com$request_uri;
}
```

### 3.3 测试并重载 Nginx

```bash
# 检查配置语法是否正确
sudo nginx -t

# 如果显示 successful，重载配置
sudo systemctl reload nginx
```

---

## 4. 启动服务

回到应用目录启动 Docker 容器：

```bash
cd ~/apps/Audiobook_web_APP

# 构建并启动后台运行
sudo docker compose up -d --build

# 查看运行状态
sudo docker compose ps
```

你应该能看到 `audiobook_nginx` 正在运行并监听 `0.0.0.0:8123->80/tcp`。

现在访问 `https://strollunreal.com`，应该能看到你的有声书应用了！
原有的 `https://strollunreal.com/pm1dsl` 等链接也可以正常访问。

---

## 5. 运维命令

### 查看日志

```bash
# 查看所有日志
docker compose logs -f

# 查看后端日志
docker compose logs -f backend

# 查看 Nginx 访问日志
docker compose logs -f nginx
```

### 更新应用

```bash
# 拉取最新代码
git pull

# 重启服务 (会自动重新构建)
docker compose up -d --build
```

### 备份数据

```bash
# 备份数据库
docker compose exec -T db pg_dump -U audiobook audiobook > backup_$(date +%Y%m%d).sql

# 备份书籍文件
tar -czf media_backup_$(date +%Y%m%d).tar.gz media/
```
