#!/bin/bash
# Verify all Docker services are healthy.
# Usage: bash scripts/healthcheck.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

PASS=0
FAIL=0

check_service() {
    local name="$1"
    local url="$2"

    if curl -sf -o /dev/null -w "%{http_code}" "$url" | grep -q "200"; then
        echo -e "  ${GREEN}[PASS]${NC} $name ($url)"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}[FAIL]${NC} $name ($url)"
        FAIL=$((FAIL + 1))
    fi
}

check_postgres() {
    if docker compose exec -T postgres pg_isready -U agents -d corporate_agents > /dev/null 2>&1; then
        echo -e "  ${GREEN}[PASS]${NC} postgres (pg_isready)"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}[FAIL]${NC} postgres (pg_isready)"
        FAIL=$((FAIL + 1))
    fi
}

check_tables() {
    local count
    count=$(docker compose exec -T postgres psql -U agents -d corporate_agents -t -c \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')

    if [ "$count" = "7" ]; then
        echo -e "  ${GREEN}[PASS]${NC} postgres tables (${count}/7)"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}[FAIL]${NC} postgres tables (${count:-0}/7)"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "=== Corporate AI Agents — Health Check ==="
echo ""

echo "Infrastructure:"
check_postgres
check_tables
check_service "qdrant" "http://localhost:6333/healthz"
check_service "minio" "http://localhost:9000/minio/health/live"
check_service "nginx" "http://localhost:8080/health"

echo ""
echo "Application:"
check_service "gateway" "http://localhost:3000/health"

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}Some checks failed!${NC}"
    exit 1
else
    echo -e "${GREEN}All checks passed!${NC}"
fi
