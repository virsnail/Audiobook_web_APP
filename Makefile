.PHONY: help dev prod up down logs clean backup migrate

help:
	@echo "AudioBook Reader 命令"
	@echo ""
	@echo "  make dev      - 启动开发环境"
	@echo "  make prod     - 启动生产环境"
	@echo "  make down     - 停止所有服务"
	@echo "  make logs     - 查看日志"
	@echo "  make clean    - 清理数据（危险！）"
	@echo "  make backup   - 备份数据"
	@echo "  make migrate  - 运行数据库迁移"

dev:
	docker compose -f docker-compose.dev.yml up -d
	@echo "后端运行在 http://localhost:8001"
	@echo "请启动前端: cd frontend && pnpm dev"

prod:
	docker compose up -d --build
	@echo "服务已启动"

down:
	docker compose down
	docker compose -f docker-compose.dev.yml down

logs:
	docker compose logs -f

migrate:
	docker compose exec backend alembic upgrade head

backup:
	@mkdir -p backups
	@echo "备份数据库..."
	docker compose exec db pg_dump -U audiobook audiobook > backups/db_$$(date +%Y%m%d_%H%M%S).sql
	@echo "备份媒体文件..."
	tar -czf backups/media_$$(date +%Y%m%d_%H%M%S).tar.gz media/
	@echo "备份完成"

clean:
	@read -p "确定要删除所有数据吗？[y/N] " confirm; \
	if [ "$$confirm" = "y" ]; then \
		docker compose down -v; \
		rm -rf pgdata media; \
		echo "已清理"; \
	fi
