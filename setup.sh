#!/bin/bash

# ISEKDAPP Setup Script
# This script installs all dependencies for frontend, backend, and server components

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check system requirements
check_requirements() {
    log_info "Checking system requirements..."
    
    # Check Node.js
    if command_exists node; then
        NODE_VERSION=$(node --version | sed 's/v//')
        log_info "Node.js version: $NODE_VERSION"
        
        # Check if version is >= 22.17.0
        if [[ $(echo "$NODE_VERSION 22.17.0" | tr " " "\n" | sort -V | head -n1) != "22.17.0" ]]; then
            log_warning "Node.js version should be >= 22.17.0. Current: $NODE_VERSION"
            log_info "Please update Node.js: https://nodejs.org/"
        fi
    else
        log_error "Node.js is not installed. Please install Node.js >= 22.17.0"
        log_info "Download from: https://nodejs.org/"
        exit 1
    fi
    
    # Check npm
    if command_exists npm; then
        NPM_VERSION=$(npm --version)
        log_info "npm version: $NPM_VERSION"
    else
        log_error "npm is not installed. Please install npm"
        exit 1
    fi
    
    # Check Python
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        log_info "Python version: $PYTHON_VERSION"
        
        # Check if version is >= 3.10.0
        if [[ $(echo "$PYTHON_VERSION 3.10.0" | tr " " "\n" | sort -V | head -n1) != "3.10.0" ]]; then
            log_warning "Python version should be >= 3.10.0. Current: $PYTHON_VERSION"
        fi
    else
        log_error "Python 3 is not installed. Please install Python >= 3.10.0"
        exit 1
    fi
    
    # Check pip
    if command_exists pip3; then
        PIP_VERSION=$(pip3 --version | cut -d' ' -f2)
        log_info "pip version: $PIP_VERSION"
    elif command_exists pip; then
        PIP_VERSION=$(pip --version | cut -d' ' -f2)
        log_info "pip version: $PIP_VERSION"
    else
        log_error "pip is not installed. Please install pip"
        exit 1
    fi
    
    log_success "System requirements check completed"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies..."
    
    # Check if we should use pip or pip3
    PIP_CMD="pip3"
    if ! command_exists pip3 && command_exists pip; then
        PIP_CMD="pip"
    fi
    
    # Upgrade pip first
    log_info "Upgrading pip..."
    $PIP_CMD install --upgrade pip
    
    # Install from requirements.txt
    if [ -f "requirements.txt" ]; then
        log_info "Installing from requirements.txt..."
        $PIP_CMD install -r requirements.txt
        log_success "Python dependencies installed successfully"
    else
        log_error "requirements.txt not found"
        exit 1
    fi
    
    # Verify a2a-sdk installation
    log_info "Verifying a2a-sdk installation..."
    if $PIP_CMD show a2a-sdk >/dev/null 2>&1; then
        A2A_VERSION=$($PIP_CMD show a2a-sdk | grep Version | cut -d' ' -f2)
        log_success "a2a-sdk version $A2A_VERSION installed"
    else
        log_warning "a2a-sdk not found, attempting to install..."
        $PIP_CMD install a2a-sdk==0.2.14
    fi
    
    # Verify ISEK package installation
    log_info "Verifying ISEK package installation..."
    if $PIP_CMD show isek >/dev/null 2>&1; then
        ISEK_VERSION=$($PIP_CMD show isek | grep Version | cut -d' ' -f2)
        log_success "ISEK package version $ISEK_VERSION installed"
    else
        log_error "ISEK package not installed properly"
        exit 1
    fi
}

# Install Node.js dependencies  
install_node_deps() {
    log_info "Installing Node.js dependencies..."
    
    # Frontend dependencies
    if [ -d "agent_client/client_ui" ]; then
        log_info "Installing frontend dependencies..."
        cd agent_client/client_ui
        
        # Clear cache if npm install fails
        if ! npm install; then
            log_warning "npm install failed, trying with legacy peer deps..."
            npm install --legacy-peer-deps
        fi
        
        log_success "Frontend dependencies installed"
        cd ../..
    else
        log_error "Frontend directory not found: agent_client/client_ui"
        exit 1
    fi
}

# Verify installations
verify_installation() {
    log_info "Verifying installations..."
    
    # Check Python packages
    log_info "Checking Python packages..."
    PYTHON_PACKAGES=("fastapi" "uvicorn" "aiohttp" "a2a-sdk" "requests" "python-dotenv" "isek")
    
    PIP_CMD="pip3"
    if ! command_exists pip3 && command_exists pip; then
        PIP_CMD="pip"
    fi
    
    for package in "${PYTHON_PACKAGES[@]}"; do
        if $PIP_CMD show "$package" >/dev/null 2>&1; then
            VERSION=$($PIP_CMD show "$package" | grep Version | cut -d' ' -f2)
            log_success "$package: $VERSION"
        else
            log_error "$package: NOT INSTALLED"
        fi
    done
    
    # Check Node.js packages
    log_info "Checking Node.js packages..."
    if [ -d "agent_client/client_ui/node_modules" ]; then
        cd agent_client/client_ui
        
        # Check key packages
        NODE_PACKAGES=("next" "react" "electron" "@ai-sdk/openai")
        for package in "${NODE_PACKAGES[@]}"; do
            if [ -d "node_modules/$package" ]; then
                VERSION=$(npm list "$package" --depth=0 2>/dev/null | grep "$package" | sed 's/.*@//' | sed 's/ .*//')
                log_success "$package: $VERSION"
            else
                log_error "$package: NOT INSTALLED"
            fi
        done
        
        cd ../..
    fi
}

# Check configuration files
check_configs() {
    log_info "Checking configuration files..."
    
    CONFIG_FILES=(
        "agent_client/client_backend/config.json"
        "agent_server/config.json"
    )
    
    for config in "${CONFIG_FILES[@]}"; do
        if [ -f "$config" ]; then
            log_success "Found: $config"
        else
            log_error "Missing: $config"
        fi
    done
}

# Display next steps
show_next_steps() {
    log_info "Setup completed! Next steps:"
    echo ""
    echo "1. Start the components:"
    echo "   Frontend: cd agent_client/client_ui && npm run dev"
    echo "   Backend:  cd agent_client/client_backend && python -m uvicorn app:app --host 0.0.0.0 --port 5001"
    echo "   Server:   cd agent_server && python app.py"
    echo ""
    echo "2. Or use the quick-start script:"
    echo "   ./quick-start.sh"
    echo ""
    echo "3. For production build:"
    echo "   cd agent_client/client_ui && npm run dist:mac"
    echo ""
    echo "4. Verify the setup by checking:"
    echo "   - Frontend: http://localhost:3000"
    echo "   - Backend API: http://localhost:5001"
    echo "   - etcd registry connectivity to 47.236.116.81:2379"
    echo ""
    log_success "ISEKDAPP setup completed successfully!"
}

# Main execution
main() {
    echo "=========================================="
    echo "       ISEKDAPP Setup Script"
    echo "=========================================="
    echo ""
    
    # Get script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR"
    
    log_info "Starting setup in: $(pwd)"
    echo ""
    
    # Run setup steps
    check_requirements
    echo ""
    
    install_python_deps
    echo ""
    
    install_node_deps  
    echo ""
    
    verify_installation
    echo ""
    
    check_configs
    echo ""
    
    show_next_steps
}

# Handle script interruption
trap 'log_error "Setup interrupted"; exit 1' INT TERM

# Run main function
main "$@"