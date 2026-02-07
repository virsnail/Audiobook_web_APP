FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libmagic1 \
    curl \
    ffmpeg \
    gosu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 设置启动脚本权限
RUN chmod +x start.sh

# 创建用户但不切换（将在 start.sh 中切换）
RUN useradd -m -u 1000 appuser

EXPOSE 8000

# 使用启动脚本
CMD ["./start.sh"]
