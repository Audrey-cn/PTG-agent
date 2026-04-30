#!/usr/bin/env bash

# Prometheus (PTG) 一键安装脚本
# 安装方式: curl -fsSL https://raw.githubusercontent.com/Audrey-cn/PTG-agent/main/scripts/install.sh | bash

set -e  # 出错时退出
set -o pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 输出函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}
log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}
log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}
log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 欢迎信息
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔥 Prometheus — Teach-To-Grow 种子基因编辑器 一键安装      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# 检查依赖
log_info "检查依赖..."
if ! command -v python3 &> /dev/null; then
    log_error "未找到 python3，请先安装 Python 3.11+"
    exit 1
fi
if ! command -v git &> /dev/null; then
    log_error "未找到 git，请先安装 Git"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
log_info "检测到 Python ${PYTHON_VERSION}"

# 询问安装位置
DEFAULT_DIR="$HOME/ptg-agent"
read -p "请输入安装目录 (默认: ${DEFAULT_DIR}): " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-$DEFAULT_DIR}

# 检查目录是否已存在
if [ -d "$INSTALL_DIR" ]; then
    log_warning "目录 ${INSTALL_DIR} 已存在！"
    read -p "是否要更新现有安装？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "安装已取消"
        exit 0
    fi
    # 更新现有仓库
    log_info "更新仓库..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    # 克隆仓库
    log_info "克隆仓库到 ${INSTALL_DIR}..."
    git clone https://github.com/Audrey-cn/PTG-agent.git "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
log_info "进入目录: ${INSTALL_DIR}"

# 安装方式选择
echo ""
echo "请选择安装方式:"
echo "  1) pip 开发模式安装（推荐，可实时修改代码）"
echo "  2) Shell 别名方式（快速，不修改 Python 环境）"
read -p "请选择 (1 或 2，默认 1): " INSTALL_CHOICE
INSTALL_CHOICE=${INSTALL_CHOICE:-1}

if [ "$INSTALL_CHOICE" = "1" ]; then
    # pip 安装
    log_info "尝试 pip 安装..."
    if python3 -m pip install -e . 2>/dev/null; then
        log_success "pip 安装成功！"
    else
        log_warning "pip 安装失败，降级到 Shell 别名方式"
        INSTALL_CHOICE=2
    fi
fi

if [ "$INSTALL_CHOICE" = "2" ]; then
    # Shell 别名安装
    log_info "配置 Shell 别名..."
    
    ALIAS_CMD="alias ptg='cd ${INSTALL_DIR} && python3 -m prometheus.cli.main'"
    ALIAS_CMD_FULL="alias prometheus='ptg'"
    
    # 检测 shell 类型
    SHELL_TYPE=$(basename "$SHELL")
    RC_FILE=""
    
    if [ "$SHELL_TYPE" = "zsh" ]; then
        RC_FILE="$HOME/.zshrc"
    elif [ "$SHELL_TYPE" = "bash" ]; then
        if [ -f "$HOME/.bash_profile" ]; then
            RC_FILE="$HOME/.bash_profile"
        else
            RC_FILE="$HOME/.bashrc"
        fi
    fi
    
    if [ -z "$RC_FILE" ]; then
        log_warning "未检测到 Shell 配置文件，请手动添加别名"
    else
        # 检查是否已存在
        if grep -Fq "alias ptg=" "$RC_FILE"; then
            log_warning "ptg 别名已存在，跳过添加"
        else
            echo "" >> "$RC_FILE"
            echo "# Prometheus (PTG) 配置" >> "$RC_FILE"
            echo "$ALIAS_CMD" >> "$RC_FILE"
            echo "$ALIAS_CMD_FULL" >> "$RC_FILE"
            log_success "已添加别名到 ${RC_FILE}"
        fi
    fi
fi

# 完成提示
echo ""
log_success "══════════════════════════════════════════════════════════════"
log_success "安装成功！"
log_success "══════════════════════════════════════════════════════════════"
echo ""

if [ "$INSTALL_CHOICE" = "2" ] && [ -n "$RC_FILE" ]; then
    log_info "请运行以下命令来立即生效："
    echo "    source ${RC_FILE}"
    echo ""
fi

log_info "快速开始："
echo "    ptg --help           # 查看帮助"
echo "    ptg setup            # 初始化配置"
echo "    ptg skill list       # 查看技能"
echo ""
echo "详细文档请查看: ${INSTALL_DIR}/INSTALL.md"
echo ""
