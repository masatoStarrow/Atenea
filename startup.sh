#!/bin/bash

# =============================================================================
# CRM System Startup Script
# =============================================================================
# Este script levanta todo el sistema CRM en orden:
# 1. API Gateway (Atenea) 
# 2. Users Service (Artemisa)
# 3. Migraciones de bases de datos
# 4. Seed de datos de prueba
# =============================================================================

set -e  # Exit on any error

# Resolve script directory (works regardless of where the script is called from)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARTEMISA_DIR="$(dirname "$SCRIPT_DIR")/Artemisa"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_section() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}🚀 $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

# Check if Docker is running
check_docker() {
    if ! docker --version > /dev/null 2>&1; then
        log_error "Docker is not installed or not running"
        exit 1
    fi

    if ! docker-compose --version > /dev/null 2>&1; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    log_success "Docker and Docker Compose are available"
}

# Clean up existing containers
cleanup_containers() {
    log_section "STEP 1: CLEANUP EXISTING CONTAINERS"
    
    log_info "Stopping and removing Atenea containers..."
    cd "$SCRIPT_DIR"
    sudo docker-compose down -v > /dev/null 2>&1 || true

    log_info "Stopping and removing Artemisa containers..."
    cd "$ARTEMISA_DIR"
    sudo docker-compose down -v > /dev/null 2>&1 || true
    
    log_success "All containers cleaned up"
}

# Create Docker network
create_network() {
    log_section "STEP 2: CREATE DOCKER NETWORK"
    
    if sudo docker network inspect crm_network > /dev/null 2>&1; then
        log_info "Network 'crm_network' already exists"
    else
        log_info "Creating Docker network 'crm_network'..."
        sudo docker network create crm_network
        log_success "Network created successfully"
    fi
}

# Start Atenea (API Gateway)
start_atenea() {
    log_section "STEP 3: START ATENEA (API GATEWAY)"
    
    cd "$SCRIPT_DIR"
    log_info "Building and starting Atenea containers..."
    sudo docker-compose up --build -d
    
    log_info "Waiting for Atenea database to be ready..."
    sleep 10
    
    # Wait for database to be healthy
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if sudo docker-compose exec -T db pg_isready -U postgres > /dev/null 2>&1; then
            log_success "Atenea database is ready"
            break
        fi
        
        log_info "Waiting for database... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log_error "Atenea database failed to start"
        exit 1
    fi
}

# Run Atenea migrations
migrate_atenea() {
    log_section "STEP 4: ATENEA DATABASE MIGRATIONS"

    cd "$SCRIPT_DIR"
    log_info "Running Django migrations..."
    sudo docker-compose exec -T gateway python manage.py migrate
    
    log_success "Atenea migrations completed"
}

# Wait for Artemisa HTTP API to accept requests
wait_for_artemisa_api() {
    log_info "Waiting for Artemisa HTTP API to be ready..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -sf http://localhost:8001/api/v1/health/ > /dev/null 2>&1; then
            log_success "Artemisa API is ready"
            return 0
        fi
        log_info "Artemisa not ready yet... (attempt $attempt/$max_attempts)"
        sleep 3
        attempt=$((attempt + 1))
    done

    log_error "Artemisa API did not become ready in time"
    exit 1
}

# Seed both services with the same UUIDs via dual-write
seed_users() {
    log_section "STEP 7: SEED USERS (DUAL-WRITE — GATEWAY + ARTEMISA)"

    cd "$SCRIPT_DIR"
    log_info "Running seed_users management command (dual-write)..."
    sudo docker-compose exec -T gateway python manage.py seed_users
    log_success "Seed completed — users exist in both Gateway DB and Artemisa with matching UUIDs"
}

# Start Artemisa (Users Service)
start_artemisa() {
    log_section "STEP 6: START ARTEMISA (USERS SERVICE)"

    cd "$ARTEMISA_DIR"
    
    log_info "Building and starting Artemisa containers..."
    sudo docker-compose up --build -d
    
    log_info "Waiting for Artemisa database to be ready..."
    sleep 10
    
    # Wait for database to be healthy
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if sudo docker-compose exec -T db pg_isready -U postgres > /dev/null 2>&1; then
            log_success "Artemisa database is ready"
            break
        fi
        
        log_info "Waiting for database... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log_error "Artemisa database failed to start"
        exit 1
    fi
}

# Run Artemisa migrations
migrate_artemisa() {
    log_section "STEP 7: ARTEMISA DATABASE MIGRATIONS"

    cd "$ARTEMISA_DIR"
    log_info "Running Alembic migrations..."
    sudo docker-compose exec -T users-service alembic upgrade head

    log_success "Artemisa migrations completed"
}



# Run tests
run_tests() {
    log_section "STEP 8: RUN TESTS TO VERIFY SYSTEM"
    
    log_info "Running Atenea tests..."
    cd "$SCRIPT_DIR"
    if sudo docker-compose exec -T gateway python -m pytest tests/ -q; then
        log_success "Atenea tests passed"
    else
        log_warning "Some Atenea tests failed (check manually)"
    fi

    log_info "Running Artemisa tests..."
    cd "$ARTEMISA_DIR"
    if sudo docker-compose exec -T users-service python -m pytest tests/ -q; then
        log_success "Artemisa tests passed"
    else
        log_warning "Some Artemisa tests failed (check manually)"
    fi
}

# Show system status
show_status() {
    log_section "STEP 9: SYSTEM STATUS"
    
    echo -e "${GREEN}🎉 CRM SYSTEM STARTUP COMPLETE! 🎉${NC}"
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}🌐 ATENEA (API Gateway)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo "🔗 URL: http://localhost:8000"
    echo "📚 API Docs: http://localhost:8000/api/docs/"
    echo "🐘 PostgreSQL: port 5432"
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}🏢 ARTEMISA (Users Service)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo "🔗 URL: http://localhost:8001"
    echo "📚 API Docs: http://localhost:8001/api/docs"
    echo "👥 Users: http://localhost:8001/api/v1/users/"
    echo "🏢 Clients: http://localhost:8001/api/v1/clients/"
    echo "🐘 PostgreSQL: port 5433"
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}👤 SEED USERS (same UUID in both services)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo "📧 admin@crm.com      (password: Temporal123! | role: admin)"
    echo "📧 soporte@crm.com    (password: Temporal123! | role: soporte)"
    echo "📧 comercial@crm.com  (password: Temporal123! | role: comercial)"
    echo ""
    echo -e "${GREEN}✅ All services are running and ready!${NC}"
    echo -e "${YELLOW}💡 Use 'sudo docker-compose logs -f [service]' to view logs${NC}"
    echo -e "${YELLOW}💡 Use './startup.sh --help' for more options${NC}"
}

# Help message
show_help() {
    echo "CRM System Startup Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --skip-cleanup    Skip container cleanup step"
    echo "  --skip-tests      Skip running tests"
    echo "  --help           Show this help message"
    echo ""
    echo "This script will:"
    echo "  1. Clean up existing containers"
    echo "  2. Create Docker network"
    echo "  3. Start Atenea (API Gateway)"
    echo "  4. Run Atenea migrations"
    echo "  5. Start Artemisa (Users Service)"
    echo "  6. Run Artemisa migrations"
    echo "  7. Seed users via dual-write (same UUID in both DBs)"
    echo "  8. Run tests to verify system"
    echo "  9. Show system status"
}

# Main execution
main() {
    local skip_cleanup=false
    local skip_tests=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-cleanup)
                skip_cleanup=true
                shift
                ;;
            --skip-tests)
                skip_tests=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    log_info "Starting CRM system setup..."

    check_docker
    
    if [ "$skip_cleanup" = false ]; then
        cleanup_containers
    fi
    
    create_network
    start_atenea
    migrate_atenea
    start_artemisa
    migrate_artemisa
    wait_for_artemisa_api
    seed_users

    if [ "$skip_tests" = false ]; then
        run_tests
    fi
    
    show_status
    
    log_success "CRM system is ready to use!"
}

# Execute main function with all arguments
main "$@"