#!/bin/bash
# ============================================================================
# Prometheus (PTG) Installer
# ============================================================================
# Installation script for Linux, macOS.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Audrey-cn/PTG-agent/main/scripts/install.sh | bash
#
# Or with options:
#   curl -fsSL ... | bash -s -- --skip-setup
#
# ============================================================================
set -e
set -o pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
REPO_URL_SSH="git@github.com:Audrey-cn/PTG-agent.git"
REPO_URL_HTTPS="https://github.com/Audrey-cn/PTG-agent.git"
PROMETHEUS_HOME="${PROMETHEUS_HOME:-$HOME/.prometheus}"
PYTHON_VERSION="3.11"

# Options
RUN_SETUP=true
BRANCH="main"
if [ -n "${PTG_INSTALL_DIR:-}" ]; then
    INSTALL_DIR="$PTG_INSTALL_DIR"
    INSTALL_DIR_EXPLICIT=true
else
    INSTALL_DIR=""
    INSTALL_DIR_EXPLICIT=false
fi

# Detect non-interactive mode (e.g. curl | bash)
# When stdin is not a terminal, read -p will fail with EOF,
# causing set -e to silently abort the entire script.
if [ -t 0 ]; then
    IS_INTERACTIVE=true
else
    IS_INTERACTIVE=false
fi

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-setup)
            RUN_SETUP=false
            shift
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --dir)
            INSTALL_DIR="$2"
            INSTALL_DIR_EXPLICIT=true
            shift 2
            ;;
        --prometheus-home)
            PROMETHEUS_HOME="$2"
            shift 2
            ;;
        -h|--help)
            echo "Prometheus (PTG) Installer"
            echo ""
            echo "Usage: install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-setup        Skip interactive setup wizard"
            echo "  --branch NAME       Git branch to install (default: main)"
            echo "  --dir PATH          Installation directory (default: ~/ptg-agent)"
            echo "  --prometheus-home PATH  Data directory (default: ~/.prometheus, or \$PROMETHEUS_HOME)"
            echo "  -h, --help          Show this help"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ============================================================================
# Helper functions
# ============================================================================
print_banner() {
    echo ""
    echo -e "${MAGENTA}${BOLD}"
    echo "┌─────────────────────────────────────────────────────────┐"
    echo "│              🔥 Prometheus Installer                     │"
    echo "├─────────────────────────────────────────────────────────┤"
    echo "│  An AI agent for creating & editing agents by Audrey.    │"
    echo "└─────────────────────────────────────────────────────────┘"
    echo -e "${NC}"
}

log_info() {
    echo -e "${CYAN}→${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

prompt_yes_no() {
    local question="$1"
    local default="${2:-yes}"
    local prompt_suffix
    local answer=""
    
    # Use case patterns (not ${var,,}) so this works on bash 3.2 (macOS /bin/bash).
    case "$default" in
        [yY]|[yY][eE][sS]|[tT][rR][uU][eE]|1) prompt_suffix="[Y/n]" ;;
        *) prompt_suffix="[y/N]" ;;
    esac
    
    if [ "$IS_INTERACTIVE" = true ]; then
        read -r -p "$question $prompt_suffix " answer || answer=""
    elif [ -r /dev/tty ] && [ -w /dev/tty ]; then
        printf "%s %s " "$question" "$prompt_suffix" > /dev/tty
        IFS= read -r answer < /dev/tty || answer=""
    else
        answer=""
    fi
    
    answer="${answer#"${answer%%[![:space:]]*}"}"
    answer="${answer%"${answer##*[![:space:]]}"}"
    
    if [ -z "$answer" ]; then
        case "$default" in
            [yY]|[yY][eE][sS]|[tT][rR][uU][eE]|1) return 0 ;;
            *) return 1 ;;
        esac
    fi
    
    case "$answer" in
        [yY]|[yY][eE][sS]) return 0 ;;
        *) return 1 ;;
    esac
}

# ============================================================================
# System detection
# ============================================================================
detect_os() {
    case "$(uname -s)" in
        Linux*)
            OS="linux"
            if [ -f /etc/os-release ]; then
                . /etc/os-release
                DISTRO="$ID"
            else
                DISTRO="unknown"
            fi
            ;;
        Darwin*)
            OS="macos"
            DISTRO="macos"
            ;;
        CYGWIN*|MINGW*|MSYS*)
            OS="windows"
            DISTRO="windows"
            log_error "Windows detected. Prometheus works best on macOS/Linux."
            log_info "We recommend using WSL2 for the best experience."
            ;;
        *)
            OS="unknown"
            DISTRO="unknown"
            log_warn "Unknown operating system"
            ;;
    esac
    log_success "Detected: $OS ($DISTRO)"
}

# ============================================================================
# Dependency checks & auto-install
# ============================================================================
has_sudo() {
    if command -v sudo &> /dev/null; then
        if sudo -n true 2>/dev/null; then
            return 0
        else
            return 1
        fi
    else
        return 1
    fi
}

install_git_apt() {
    log_info "Installing Git via apt..."
    if has_sudo; then
        sudo apt update
        sudo apt install -y git
    else
        apt update
        apt install -y git
    fi
}

install_git_dnf() {
    log_info "Installing Git via dnf..."
    if has_sudo; then
        sudo dnf install -y git
    else
        dnf install -y git
    fi
}

install_git_pacman() {
    log_info "Installing Git via pacman..."
    if has_sudo; then
        sudo pacman -S --noconfirm git
    else
        pacman -S --noconfirm git
    fi
}

install_git_brew() {
    log_info "Installing Git via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install git
    else
        log_warn "Homebrew not found"
        return 1
    fi
}

install_python_apt() {
    log_info "Installing Python $PYTHON_VERSION via apt..."
    if has_sudo; then
        sudo apt update
        sudo apt install -y python$PYTHON_VERSION python3-pip python$PYTHON_VERSION-venv
    else
        apt update
        apt install -y python$PYTHON_VERSION python3-pip python$PYTHON_VERSION-venv
    fi
}

install_python_dnf() {
    log_info "Installing Python $PYTHON_VERSION via dnf..."
    if has_sudo; then
        sudo dnf install -y python$PYTHON_VERSION python3-pip
    else
        dnf install -y python$PYTHON_VERSION python3-pip
    fi
}

install_python_pacman() {
    log_info "Installing Python via pacman..."
    if has_sudo; then
        sudo pacman -S --noconfirm python python-pip
    else
        pacman -S --noconfirm python python-pip
    fi
}

install_python_brew() {
    log_info "Installing Python $PYTHON_VERSION via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install python@$PYTHON_VERSION
    else
        log_warn "Homebrew not found"
        return 1
    fi
}

show_python_install_guide() {
    echo ""
    log_info "Please install Python $PYTHON_VERSION:"
    case "$OS" in
        macos)
            echo "  1. Using Homebrew (recommended):"
            echo "     brew install python@$PYTHON_VERSION"
            echo ""
            echo "  2. From python.org:"
            echo "     https://www.python.org/downloads/"
            ;;
        linux)
            case "$DISTRO" in
                ubuntu|debian|linuxmint)
                    echo "  sudo apt update"
                    echo "  sudo apt install python$PYTHON_VERSION python3-pip python$PYTHON_VERSION-venv"
                    ;;
                fedora|rhel|centos)
                    echo "  sudo dnf install python$PYTHON_VERSION python3-pip"
                    ;;
                arch|manjaro)
                    echo "  sudo pacman -S python python-pip"
                    ;;
                *)
                    echo "  Use your package manager to install Python $PYTHON_VERSION"
                    ;;
            esac
            ;;
        *)
            echo "  https://www.python.org/downloads/"
            ;;
    esac
    echo ""
}

show_git_install_guide() {
    echo ""
    log_info "Please install Git:"
    case "$OS" in
        macos)
            echo "  1. Using Homebrew (recommended):"
            echo "     brew install git"
            echo ""
            echo "  2. From git-scm.com:"
            echo "     https://git-scm.com/downloads/mac"
            ;;
        linux)
            case "$DISTRO" in
                ubuntu|debian|linuxmint)
                    echo "  sudo apt update"
                    echo "  sudo apt install git"
                    ;;
                fedora|rhel|centos)
                    echo "  sudo dnf install git"
                    ;;
                arch|manjaro)
                    echo "  sudo pacman -S git"
                    ;;
                *)
                    echo "  Use your package manager to install Git"
                    ;;
            esac
            ;;
        *)
            echo "  https://git-scm.com/downloads"
            ;;
    esac
    echo ""
}

try_auto_install_git() {
    case "$OS" in
        linux)
            case "$DISTRO" in
                ubuntu|debian|linuxmint)
                    if command -v apt &> /dev/null; then
                        if prompt_yes_no "Git not found. Install it automatically?" "yes"; then
                            install_git_apt
                            return 0
                        fi
                    fi
                    ;;
                fedora|rhel|centos)
                    if command -v dnf &> /dev/null; then
                        if prompt_yes_no "Git not found. Install it automatically?" "yes"; then
                            install_git_dnf
                            return 0
                        fi
                    fi
                    ;;
                arch|manjaro)
                    if command -v pacman &> /dev/null; then
                        if prompt_yes_no "Git not found. Install it automatically?" "yes"; then
                            install_git_pacman
                            return 0
                        fi
                    fi
                    ;;
            esac
            ;;
        macos)
            if command -v brew &> /dev/null; then
                if prompt_yes_no "Git not found. Install it automatically via Homebrew?" "yes"; then
                    install_git_brew
                    return 0
                fi
            fi
            ;;
    esac
    return 1
}

try_auto_install_python() {
    case "$OS" in
        linux)
            case "$DISTRO" in
                ubuntu|debian|linuxmint)
                    if command -v apt &> /dev/null; then
                        if prompt_yes_no "Python not found. Install it automatically?" "yes"; then
                            install_python_apt
                            return 0
                        fi
                    fi
                    ;;
                fedora|rhel|centos)
                    if command -v dnf &> /dev/null; then
                        if prompt_yes_no "Python not found. Install it automatically?" "yes"; then
                            install_python_dnf
                            return 0
                        fi
                    fi
                    ;;
                arch|manjaro)
                    if command -v pacman &> /dev/null; then
                        if prompt_yes_no "Python not found. Install it automatically?" "yes"; then
                            install_python_pacman
                            return 0
                        fi
                    fi
                    ;;
            esac
            ;;
        macos)
            if command -v brew &> /dev/null; then
                if prompt_yes_no "Python not found. Install it automatically via Homebrew?" "yes"; then
                    install_python_brew
                    return 0
                fi
            fi
            ;;
    esac
    return 1
}

check_python() {
    log_info "Checking Python $PYTHON_VERSION..."
    
    PYTHON_MISSING=0
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION_FOUND=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || echo "")
        if [ -n "$PYTHON_VERSION_FOUND" ]; then
            log_success "Python $PYTHON_VERSION_FOUND found"
            
            # Check Python version
            PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])' 2>/dev/null || echo 0)
            PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])' 2>/dev/null || echo 0)
            if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
                log_warn "Python $PYTHON_VERSION_FOUND may be old, recommended: $PYTHON_VERSION+"
            fi
        fi
    else
        PYTHON_MISSING=1
    fi
    
    if [ "$PYTHON_MISSING" -eq 1 ]; then
        log_error "Python not found"
        if try_auto_install_python; then
            log_success "Python installed successfully!"
            # Verify again
            if command -v python3 &> /dev/null; then
                PYTHON_VERSION_FOUND=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || echo "")
                log_success "Python $PYTHON_VERSION_FOUND is ready"
            else
                log_error "Python installation seems to have failed"
                show_python_install_guide
                exit 1
            fi
        else
            show_python_install_guide
            exit 1
        fi
    fi
}

check_git() {
    log_info "Checking Git..."
    
    GIT_MISSING=0
    
    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version | awk '{print $3}')
        log_success "Git $GIT_VERSION found"
    else
        GIT_MISSING=1
    fi
    
    if [ "$GIT_MISSING" -eq 1 ]; then
        log_error "Git not found"
        if try_auto_install_git; then
            log_success "Git installed successfully!"
            # Verify again
            if command -v git &> /dev/null; then
                GIT_VERSION=$(git --version | awk '{print $3}')
                log_success "Git $GIT_VERSION is ready"
            else
                log_error "Git installation seems to have failed"
                show_git_install_guide
                exit 1
            fi
        else
            show_git_install_guide
            exit 1
        fi
    fi
}

# ============================================================================
# Main installation
# ============================================================================

print_banner
detect_os

# Check dependencies
check_python
check_git

# Resolve install directory
if [ "$INSTALL_DIR_EXPLICIT" = true ]; then
    log_info "Install directory: $INSTALL_DIR (explicit)"
else
    INSTALL_DIR="$HOME/ptg-agent"
    log_info "Install directory: $INSTALL_DIR"
fi

# Clone or update repository
if [ -d "$INSTALL_DIR/.git" ]; then
    log_warn "Directory $INSTALL_DIR already exists"
    if prompt_yes_no "Update existing installation?" "yes"; then
        log_info "Updating repository..."
        cd "$INSTALL_DIR"
        git pull origin "$BRANCH"
        log_success "Repository updated"
    else
        log_info "Installation cancelled by user"
        exit 0
    fi
else
    log_info "Cloning repository..."
    git clone "$REPO_URL_HTTPS" "$INSTALL_DIR" --branch "$BRANCH"
    log_success "Repository cloned to $INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Try pip install first, fall back to alias
echo ""
log_info "Installing Prometheus..."

PTG_COMMAND=""

if python3 -m pip install -e . >/dev/null 2>&1; then
    log_success "Installed via pip (editable mode)"
    PTG_COMMAND="ptg"
else
    log_warn "pip install failed, using shell alias instead"
    
    # Set up shell alias
    ALIAS_CMD="alias ptg='cd $INSTALL_DIR && python3 -m prometheus.cli.main'"
    ALIAS_CMD_FULL="alias prometheus='ptg'"
    
    # Detect shell type
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
        log_warn "Could not detect shell config file"
        log_info "Please add these lines manually:"
        echo "  $ALIAS_CMD"
        echo "  $ALIAS_CMD_FULL"
    else
        if grep -Fq "alias ptg=" "$RC_FILE"; then
            log_warn "ptg alias already exists in $RC_FILE"
        else
            echo "" >> "$RC_FILE"
            echo "# Prometheus (PTG) configuration" >> "$RC_FILE"
            echo "$ALIAS_CMD" >> "$RC_FILE"
            echo "$ALIAS_CMD_FULL" >> "$RC_FILE"
            log_success "Added aliases to $RC_FILE"
        fi
    fi
    
    PTG_COMMAND="cd $INSTALL_DIR && python3 -m prometheus.cli.main"
fi

# ============================================================================
# Success & post-install guide
# ============================================================================
echo ""
echo -e "${GREEN}${BOLD}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                    Installation Complete!                       ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Reload shell config reminder
if [ -n "$RC_FILE" ]; then
    log_info "To use the 'ptg' command immediately, run:"
    echo "  source $RC_FILE"
    echo ""
fi

# Quick start guide
log_info "Quick start commands:"
echo "  ptg --help              Show help"
echo "  ptg setup               Configure Prometheus"
echo "  ptg repl                Start interactive REPL"
echo ""

# Run setup wizard if not skipped
if [ "$RUN_SETUP" = true ]; then
    if prompt_yes_no "Would you like to run the setup wizard now?" "yes"; then
        echo ""
        log_info "Starting setup wizard..."
        cd "$INSTALL_DIR"
        if [ -n "$RC_FILE" ] && [ -z "$PTG_COMMAND" ]; then
            # If we have aliases but haven't sourced yet, run directly
            python3 -m prometheus.cli.main setup
        else
            eval "$PTG_COMMAND setup"
        fi
        
        # After setup, prompt to start REPL
        echo ""
        if prompt_yes_no "Setup complete! Would you like to start the REPL now?" "yes"; then
            echo ""
            log_info "Starting Prometheus REPL..."
            cd "$INSTALL_DIR"
            if [ -n "$RC_FILE" ] && [ -z "$PTG_COMMAND" ]; then
                python3 -m prometheus.cli.main repl
            else
                eval "$PTG_COMMAND repl"
            fi
        fi
    fi
else
    log_info "Setup skipped. Run 'ptg setup' when ready."
fi

echo ""
log_success "All done! Enjoy Prometheus 🎉"
echo ""
