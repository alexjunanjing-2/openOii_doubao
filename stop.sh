#!/bin/bash

# openOii AI 漫剧生成平台 - 停止脚本
# 后端端口: 18765
# 前端端口: 15173
# PostgreSQL: 5432
# Redis: 6379

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🎬 openOii AI 漫剧生成平台 - 停止服务${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# 停止后端 (端口 18765) - 只杀监听进程，不杀客户端连接
echo -e "${YELLOW}停止后端服务 (端口 18765)...${NC}"
BACKEND_PIDS=$(lsof -ti:18765 -sTCP:LISTEN 2>/dev/null || true)
if [ -n "$BACKEND_PIDS" ]; then
    echo "$BACKEND_PIDS" | xargs kill -9 2>/dev/null || true
    echo -e "${GREEN}✅ 后端服务已停止${NC}"
else
    echo -e "${YELLOW}⚠️  后端服务未运行${NC}"
fi

# 停止前端 (端口 15173) - 只杀监听进程，不杀浏览器等客户端
echo -e "${YELLOW}停止前端服务 (端口 15173)...${NC}"
FRONTEND_PIDS=$(lsof -ti:15173 -sTCP:LISTEN 2>/dev/null || true)
if [ -n "$FRONTEND_PIDS" ]; then
    echo "$FRONTEND_PIDS" | xargs kill -9 2>/dev/null || true
    echo -e "${GREEN}✅ 前端服务已停止${NC}"
else
    echo -e "${YELLOW}⚠️  前端服务未运行${NC}"
fi

# 停止 Docker 基础设施
echo -e "${YELLOW}停止 Docker 基础设施 (PostgreSQL + Redis)...${NC}"
cd "$SCRIPT_DIR"
if docker compose -f docker-compose.dev.yml ps --status running 2>/dev/null | grep -q "postgres\|redis"; then
    docker compose -f docker-compose.dev.yml down
    echo -e "${GREEN}✅ Docker 基础设施已停止${NC}"
else
    echo -e "${YELLOW}⚠️  Docker 基础设施未运行${NC}"
fi

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}🛑 所有服务已停止${NC}"
echo -e "${GREEN}================================${NC}"
