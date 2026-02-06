#!/bin/bash
# 容器启动脚本：升级 pip 和 edge-tts 到最新版本

set -e

echo "🔄 升级 pip 到最新版本..."
pip install --upgrade pip

echo "🔄 升级 edge-tts 到最新版本..."
pip install --upgrade edge-tts

echo "✅ 依赖升级完成"

# 启动 FastAPI 应用
echo "🚀 启动 FastAPI 应用..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
