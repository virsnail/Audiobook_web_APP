# 构建阶段
FROM node:22-slim AS builder

WORKDIR /app

# 安装 pnpm
RUN npm install -g pnpm

# 复制依赖文件
COPY package.json pnpm-lock.yaml ./

# 设置 CI 环境变量以避免 pnpm 交互式检查
ENV CI=true

# 安装依赖
RUN pnpm install --frozen-lockfile

# 复制源代码
COPY . .

# 构建应用
# 设置环境变量以确保 adapter-node 正确构建
ENV NODE_ENV=production
RUN pnpm run build
RUN pnpm prune --prod

# 运行阶段
FROM node:22-slim

WORKDIR /app

# 从构建阶段复制构建产物和生产依赖
COPY --from=builder /app/build ./build
COPY --from=builder /app/package.json ./package.json

# 如果 pruned node_modules 包含 adapter-node 需要的运行时依赖，应该复制它
# 但是 adapter-node build 的产物通常包含独立的 server，或者依赖 node_modules
# SvelteKit adapter-node 生成的 build 目录包含 index.js, assets 等
# 它通常需要 node_modules 中的依赖 (如 polites, etc) 除非 bundle 了
# adapter-node default builds to a standalone server but might rely on some packages?
# Let's verify standard SvelteKit Dockerfile patterns.
# Usually: copy build, copy node_modules (production only)
COPY --from=builder /app/node_modules ./node_modules

# 设置环境变量
ENV NODE_ENV=production
ENV PORT=3000
ENV HOST=0.0.0.0

EXPOSE 3000

# 启动应用
CMD ["node", "build/index.js"]
