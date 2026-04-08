#!/bin/bash
# Create data zone directories for the Corporate AI Agent system.
# Run once on the DGX Spark host before starting Docker.
# Usage: sudo bash scripts/setup-data-dirs.sh

set -euo pipefail

DATA_ROOT="${DATA_ROOT:-/data}"

echo "Creating data zone directories under ${DATA_ROOT}..."

# Zone 1: Mirror (agents read from here)
mkdir -p "${DATA_ROOT}/mirror/excel"
mkdir -p "${DATA_ROOT}/mirror/documents"
mkdir -p "${DATA_ROOT}/mirror/db_snapshots"

# Zone 2: Staging (agent proposals)
mkdir -p "${DATA_ROOT}/staging/pending"
mkdir -p "${DATA_ROOT}/staging/approved"
mkdir -p "${DATA_ROOT}/staging/rejected"
mkdir -p "${DATA_ROOT}/staging/metadata"

# Zone 4: Archive (permanent audit)
mkdir -p "${DATA_ROOT}/archive"

# Set permissions (750 = owner+group only, no world access for corporate data)
chmod -R 750 "${DATA_ROOT}/mirror"
chmod -R 750 "${DATA_ROOT}/staging"
chmod -R 750 "${DATA_ROOT}/archive"

echo "Data directories created:"
find "${DATA_ROOT}" -type d | sort
echo ""
echo "Done. Ready for docker compose up."
