#!/bin/bash

# openOii AI 漫剧生成平台 - 一键启动脚本
# 后端端口: 18765
# 前端端口: 15173
# PostgreSQL: 5432
# Redis: 6379

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🎬 openOii AI 漫剧生成平台${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# 检查依赖
check_deps() {
    echo -e "${YELLOW}检查依赖...${NC}"

    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ 未找到 docker，请先安装 Docker${NC}"
        exit 1
    fi

    if ! command -v uv &> /dev/null; then
        echo -e "${RED}❌ 未找到 uv，请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
        exit 1
    fi

    if ! command -v pnpm &> /dev/null; then
        echo -e "${RED}❌ 未找到 pnpm，请先安装: npm install -g pnpm${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ 依赖检查通过${NC}"
}

# 启动 Docker 基础设施（PostgreSQL + Redis）
start_docker() {
    echo -e "${YELLOW}启动 Docker 基础设施 (PostgreSQL + Redis)...${NC}"
    cd "$SCRIPT_DIR"

    # 检查是否已经在运行
    if docker compose -f docker-compose.dev.yml ps --status running 2>/dev/null | grep -q "postgres\|redis"; then
        echo -e "${GREEN}  基础设施已在运行${NC}"
    else
        docker compose -f docker-compose.dev.yml up -d
        echo -e "${YELLOW}  等待服务就绪...${NC}"
        sleep 3
    fi

    echo -e "${GREEN}✅ Docker 基础设施已启动${NC}"
    echo -e "  ${BLUE}PostgreSQL:${NC} localhost:5432"
    echo -e "  ${BLUE}Redis:${NC} localhost:6379"
}

# 安装后端依赖
setup_backend() {
    echo -e "${YELLOW}设置后端...${NC}"
    cd "$BACKEND_DIR"

    if [ ! -d ".venv" ]; then
        echo "  创建虚拟环境并安装依赖..."
        uv sync --extra agents
    else
        echo "  检查并更新依赖..."
        uv sync --extra agents
    fi

    if [ ! -f ".env" ]; then
        echo "  复制环境变量配置..."
        cp .env.example .env 2>/dev/null || true
    fi

    echo -e "${GREEN}✅ 后端设置完成${NC}"
}

# 安装前端依赖
setup_frontend() {
    echo -e "${YELLOW}设置前端...${NC}"
    cd "$FRONTEND_DIR"

    if [ ! -d "node_modules" ]; then
        echo "  安装依赖..."
        pnpm install
    fi

    if [ ! -f ".env.local" ]; then
        echo "  复制环境变量配置..."
        cp .env.local.example .env.local 2>/dev/null || true
    fi

    echo -e "${GREEN}✅ 前端设置完成${NC}"
}

# 启动后端
start_backend() {
    echo -e "${YELLOW}启动后端服务 (端口 18765)...${NC}"
    cd "$BACKEND_DIR"
    uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 18765 --reload &
    BACKEND_PID=$!
    echo "  后端 PID: $BACKEND_PID"
}

# 启动前端
start_frontend() {
    echo -e "${YELLOW}启动前端服务 (端口 15173)...${NC}"
    cd "$FRONTEND_DIR"
    pnpm dev &
    FRONTEND_PID=$!
    echo "  前端 PID: $FRONTEND_PID"
}

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}正在关闭服务...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}✅ 前后端服务已关闭${NC}"
    echo -e "${YELLOW}提示: Docker 基础设施仍在运行，使用 ./stop.sh 完全停止${NC}"
    exit 0
}

# 主函数
main() {
    trap cleanup SIGINT SIGTERM

    check_deps
    echo ""
    start_docker
    echo ""
    setup_backend
    echo ""
    setup_frontend
    echo ""

    start_backend
    sleep 2
    start_frontend

    echo ""
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}🎉 openOii 启动成功！${NC}"
    echo -e "${GREEN}================================${NC}"
    echo ""
    echo -e "  ${BLUE}前端地址:${NC} http://localhost:15173"
    echo -e "  ${BLUE}后端地址:${NC} http://localhost:18765"
    echo -e "  ${BLUE}API 文档:${NC} http://localhost:18765/docs"
    echo -e "  ${BLUE}PostgreSQL:${NC} localhost:5432"
    echo -e "  ${BLUE}Redis:${NC} localhost:6379"
    echo ""
    echo -e "${YELLOW}按 Ctrl+C 停止前后端服务（Docker 基础设施保持运行）${NC}"
    echo ""

    # 等待子进程
    wait
}

main "$@"
