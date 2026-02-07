#!/bin/bash
# 容器启动脚本：升级 pip 和 edge-tts 到最新版本

set -e

echo "🔄 升级 pip 到最新版本..."
pip install --upgrade pip

echo "🔄 升级 edge-tts 到最新版本..."
pip install --upgrade edge-tts

echo "✅ 依赖升级完成"

# 运行数据库迁移
echo "🔄 正在应用数据库迁移..."
alembic upgrade head
echo "✅ 数据库迁移完成"

# 修复权限（确保 appuser 可以写入 /app/media）
if [ -d "/app/media" ]; then
    echo "🔧 修复 /app/media 权限..."
    chown -R appuser:appuser /app/media
fi

# 切换到普通用户并运行应用
echo "🚀 启动 FastAPI 应用..."
exec gosu appuser uvicorn app.main:app --host 0.0.0.0 --port 8000
