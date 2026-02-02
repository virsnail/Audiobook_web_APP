# AudioBook Reader - 云服务器部署手册

> **适用环境**: Oracle Cloud / AWS (Ubuntu 22.04 / Debian 12)  
> **最后更新**: 2026-01-30

---

## 目录

1. [服务器要求](#1-服务器要求)
2. [服务器初始化](#2-服务器初始化)
3. [安装 Docker](#3-安装-docker)
4. [部署应用](#4-部署应用)
5. [SSL 证书配置](#5-ssl-证书配置)
6. [防火墙配置](#6-防火墙配置)
7. [域名配置](#7-域名配置)
8. [运维管理](#8-运维管理)
9. [备份与恢复](#9-备份与恢复)
10. [监控与日志](#10-监控与日志)
11. [故障排除](#11-故障排除)
12. [安全加固](#12-安全加固)

---

## 1. 服务器要求

### 1.1 推荐配置

| 配置项 | 最低要求     | 推荐配置                 |
| ------ | ------------ | ------------------------ |
| CPU    | 2 核         | 4 核+                    |
| 内存   | 4 GB         | 8 GB+                    |
| 存储   | 50 GB SSD    | 100 GB+ SSD              |
| 带宽   | 100 Mbps     | 1 Gbps                   |
| 系统   | Ubuntu 22.04 | Ubuntu 22.04 / Debian 12 |

### 1.2 云服务商选择

| 服务商       | 推荐实例            | 月费用 | 备注               |
| ------------ | ------------------- | ------ | ------------------ |
| Oracle Cloud | VM.Standard.A1.Flex | 免费   | ARM 架构，永久免费 |
| AWS          | t3.medium           | ~$30   | x86 架构           |
| Vultr        | High Frequency      | ~$12   | 高性能             |
| DigitalOcean | Droplet 4GB         | ~$24   | 简单易用           |

---

## 2. 服务器初始化

### 2.1 SSH 连接服务器

```bash
# 本地机器执行
ssh -i ~/.ssh/your_key.pem ubuntu@YOUR_SERVER_IP
```

### 2.2 系统更新

```bash
# 更新软件包列表
sudo apt update

# 升级系统
sudo apt upgrade -y

# 安装必要工具
sudo apt install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    ufw \
    fail2ban \
    unzip \
    ca-certificates \
    gnupg \
    lsb-release
```

### 2.3 创建部署用户（推荐）

```bash
# 创建用户
sudo adduser deploy

# 添加到 sudo 组
sudo usermod -aG sudo deploy

# 添加到 docker 组（稍后安装 Docker 后）
# sudo usermod -aG docker deploy

# 配置 SSH 密钥
sudo mkdir -p /home/deploy/.ssh
sudo cp ~/.ssh/authorized_keys /home/deploy/.ssh/
sudo chown -R deploy:deploy /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys

# 切换到 deploy 用户
su - deploy
```

### 2.4 设置时区

```bash
sudo timedatectl set-timezone America/Los_Angeles
# 或 Asia/Shanghai
```

---

## 3. 安装 Docker

### 3.1 安装 Docker Engine

```bash
# 添加 Docker 官方 GPG 密钥
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 添加软件源
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 验证安装
docker --version
docker compose version
```

### 3.2 配置 Docker 权限

```bash
# 将当前用户添加到 docker 组
sudo usermod -aG docker $USER

# 重新登录以生效
exit
ssh -i ~/.ssh/your_key.pem deploy@YOUR_SERVER_IP

# 验证无需 sudo
docker ps
```

### 3.3 配置 Docker 日志限制

```bash
# 创建 Docker 守护进程配置
sudo vim /etc/docker/daemon.json
```

添加以下内容:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

```bash
# 重启 Docker
sudo systemctl restart docker
```

---

## 4. 部署应用

### 4.1 克隆项目

```bash
# 创建项目目录
mkdir -p ~/apps
cd ~/apps

# 克隆项目
git clone https://github.com/YOUR_USERNAME/Audiobook_web_APP.git
cd Audiobook_web_APP
```

### 4.2 配置环境变量

```bash
# 从模板创建配置
cp .env.example .env

# 编辑配置
vim .env
```

**重要配置项**:

```bash
# 数据库（使用强密码！）
DB_USER=audiobook
DB_PASSWORD=YOUR_STRONG_PASSWORD_HERE
DB_NAME=audiobook

# 安全密钥（生成方式：openssl rand -hex 32）
SECRET_KEY=YOUR_64_CHAR_HEX_STRING

# 域名
DOMAIN=your-domain.com
CORS_ORIGINS=https://your-domain.com
PUBLIC_API_URL=https://your-domain.com/api

# 邮件（推荐 Mailgun 或 SendGrid）
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@your-domain.com
SMTP_PASSWORD=YOUR_SMTP_PASSWORD
SMTP_FROM=noreply@your-domain.com

# 管理员账户
ADMIN_EMAIL=admin@your-domain.com
ADMIN_PASSWORD=YOUR_ADMIN_PASSWORD
```

### 4.3 创建必要目录

```bash
mkdir -p media/books
mkdir -p pgdata
mkdir -p certbot/conf certbot/www
mkdir -p backups
```

### 4.4 配置 Nginx（修改域名）

```bash
# 编辑 Nginx 配置
vim nginx/conf.d/app.conf
```

将所有 `yourdomain.com` 替换为你的实际域名。

### 4.5 首次部署（无 SSL）

首次部署时需要先获取 SSL 证书:

```bash
# 临时修改 Nginx 配置，只监听 80 端口
# 注释掉 SSL 相关配置

# 启动服务
docker compose up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f
```

---

## 5. SSL 证书配置

### 5.1 获取 Let's Encrypt 证书

```bash
# 停止 Nginx
docker compose stop nginx

# 获取证书
docker run -it --rm \
  -v $(pwd)/certbot/conf:/etc/letsencrypt \
  -v $(pwd)/certbot/www:/var/www/certbot \
  -p 80:80 \
  certbot/certbot certonly \
  --standalone \
  --email admin@your-domain.com \
  --agree-tos \
  --no-eff-email \
  -d your-domain.com \
  -d www.your-domain.com
```

### 5.2 更新 Nginx 配置

```bash
# 取消 SSL 配置的注释
vim nginx/conf.d/app.conf

# 重启 Nginx
docker compose up -d nginx
```

### 5.3 配置自动续期

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天凌晨 3 点检查续期）
0 3 * * * cd ~/apps/Audiobook_web_APP && docker compose run --rm certbot renew && docker compose restart nginx
```

---

## 6. 防火墙配置

### 6.1 使用 UFW

```bash
# 启用 UFW
sudo ufw enable

# 允许 SSH
sudo ufw allow 22/tcp

# 允许 HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 查看状态
sudo ufw status verbose
```

### 6.2 Oracle Cloud 安全列表

在 Oracle Cloud 控制台:

1. 进入 **网络** → **虚拟云网络**
2. 选择你的 VCN → **安全列表**
3. 添加入站规则:

| 源 CIDR   | 协议 | 目标端口 |
| --------- | ---- | -------- |
| 0.0.0.0/0 | TCP  | 80       |
| 0.0.0.0/0 | TCP  | 443      |

### 6.3 AWS 安全组

在 AWS 控制台:

1. 进入 **EC2** → **安全组**
2. 编辑入站规则:

| 类型  | 端口 | 源        |
| ----- | ---- | --------- |
| HTTP  | 80   | 0.0.0.0/0 |
| HTTPS | 443  | 0.0.0.0/0 |
| SSH   | 22   | 你的 IP   |

---

## 7. 域名配置

### 7.1 DNS 记录

在你的域名注册商（如 Cloudflare、Namecheap）添加:

| 类型 | 名称 | 值             | TTL |
| ---- | ---- | -------------- | --- |
| A    | @    | YOUR_SERVER_IP | 300 |
| A    | www  | YOUR_SERVER_IP | 300 |

### 7.2 验证 DNS

```bash
# 检查 DNS 解析
nslookup your-domain.com
dig your-domain.com

# 等待 DNS 生效（可能需要几分钟到几小时）
```

---

## 8. 运维管理

### 8.1 服务管理

```bash
# 启动所有服务
docker compose up -d

# 停止所有服务
docker compose down

# 重启单个服务
docker compose restart backend
docker compose restart frontend
docker compose restart nginx

# 查看服务状态
docker compose ps

# 查看资源使用
docker stats
```

### 8.2 更新部署

```bash
# 进入项目目录
cd ~/apps/Audiobook_web_APP

# 拉取最新代码
git pull origin main

# 重新构建并部署
docker compose build --no-cache
docker compose up -d

# 运行数据库迁移（如有）
docker compose exec backend alembic upgrade head
```

### 8.3 查看日志

```bash
# 所有服务日志
docker compose logs -f

# 单个服务日志
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f nginx
docker compose logs -f db

# 最近 100 行
docker compose logs --tail 100 backend
```

---

## 9. 备份与恢复

### 9.1 手动备份

```bash
# 创建备份目录
mkdir -p ~/backups

# 备份数据库
docker compose exec -T db pg_dump -U audiobook audiobook > ~/backups/db_$(date +%Y%m%d_%H%M%S).sql

# 备份媒体文件
tar -czf ~/backups/media_$(date +%Y%m%d_%H%M%S).tar.gz media/

# 备份配置
cp .env ~/backups/env_$(date +%Y%m%d_%H%M%S).bak
```

### 9.2 自动备份

```bash
# 创建备份脚本
cat > ~/scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=~/backups
DATE=$(date +%Y%m%d_%H%M%S)
cd ~/apps/Audiobook_web_APP

# 备份数据库
docker compose exec -T db pg_dump -U audiobook audiobook > $BACKUP_DIR/db_$DATE.sql

# 备份媒体（增量）
rsync -av --delete media/ $BACKUP_DIR/media/

# 删除 7 天前的备份
find $BACKUP_DIR -name "db_*.sql" -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chmod +x ~/scripts/backup.sh

# 添加定时任务（每天凌晨 2 点）
crontab -e
# 添加: 0 2 * * * ~/scripts/backup.sh >> ~/logs/backup.log 2>&1
```

### 9.3 恢复数据

```bash
# 恢复数据库
cat ~/backups/db_YYYYMMDD_HHMMSS.sql | docker compose exec -T db psql -U audiobook audiobook

# 恢复媒体文件
tar -xzf ~/backups/media_YYYYMMDD_HHMMSS.tar.gz
```

---

## 10. 监控与日志

### 10.1 系统监控

```bash
# 安装 htop
sudo apt install htop

# 查看系统资源
htop

# 查看磁盘使用
df -h

# 查看 Docker 资源
docker system df
```

### 10.2 应用健康检查

```bash
# 检查后端 API
curl -s http://localhost:8000/health

# 检查前端
curl -s http://localhost:3000

# 外部检查
curl -s https://your-domain.com/api/health
```

### 10.3 日志管理

```bash
# 配置日志轮转
sudo vim /etc/logrotate.d/audiobook
```

内容:

```
/home/deploy/apps/Audiobook_web_APP/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    copytruncate
}
```

---

## 11. 故障排除

### 问题: 容器无法启动

```bash
# 查看详细日志
docker compose logs backend

# 检查配置
docker compose config

# 重新构建
docker compose build --no-cache backend
```

### 问题: 数据库连接失败

```bash
# 检查数据库状态
docker compose ps db

# 进入数据库容器
docker compose exec db psql -U audiobook -d audiobook

# 检查连接字符串
echo $DATABASE_URL
```

### 问题: SSL 证书过期

```bash
# 手动续期
docker compose run --rm certbot renew

# 重启 Nginx
docker compose restart nginx
```

### 问题: 磁盘空间不足

```bash
# 查看磁盘使用
df -h

# 清理 Docker
docker system prune -a

# 清理旧备份
find ~/backups -mtime +30 -delete
```

### 问题: 内存不足

```bash
# 查看内存使用
free -h

# 创建交换分区
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 永久启用
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 12. 安全加固

### 12.1 SSH 安全

```bash
sudo vim /etc/ssh/sshd_config

# 禁用密码登录
PasswordAuthentication no

# 禁用 root 登录
PermitRootLogin no

# 重启 SSH
sudo systemctl restart sshd
```

### 12.2 Fail2Ban

```bash
# 启用 Fail2Ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# 查看状态
sudo fail2ban-client status
```

### 12.3 定期更新

```bash
# 创建更新脚本
cat > ~/scripts/update.sh << 'EOF'
#!/bin/bash
sudo apt update
sudo apt upgrade -y
sudo apt autoremove -y
EOF

chmod +x ~/scripts/update.sh

# 添加定时任务（每周日凌晨 4 点）
# 0 4 * * 0 ~/scripts/update.sh >> ~/logs/update.log 2>&1
```

---

## 附录: 常用命令速查

```bash
# 部署
docker compose up -d              # 启动
docker compose down               # 停止
docker compose restart            # 重启
docker compose logs -f            # 日志

# 更新
git pull && docker compose build --no-cache && docker compose up -d

# 备份
docker compose exec -T db pg_dump -U audiobook audiobook > backup.sql

# 证书
docker compose run --rm certbot renew

# 监控
docker stats
htop
df -h
```

---

## 附录: 服务架构图

```
                     ┌──────────────────┐
                     │     用户请求      │
                     │  your-domain.com │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │      Nginx       │
                     │    (443/80)      │
                     │   SSL 终止       │
                     └────────┬─────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
   ┌───────────┐       ┌───────────┐       ┌───────────┐
   │   /api/*  │       │ /media/*  │       │   其他    │
   │  FastAPI  │       │  静态文件  │       │ SvelteKit │
   │   :8000   │       │  直接服务  │       │   :3000   │
   └─────┬─────┘       └───────────┘       └───────────┘
         │
         ▼
   ┌───────────┐
   │ PostgreSQL│
   │   :5432   │
   └───────────┘
```
