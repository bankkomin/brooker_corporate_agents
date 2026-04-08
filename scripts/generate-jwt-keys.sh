#!/usr/bin/env bash
# scripts/generate-jwt-keys.sh
# Generate RS256 key pair for JWT signing
set -euo pipefail

SECRETS_DIR="$(cd "$(dirname "$0")/.." && pwd)/secrets"
mkdir -p "$SECRETS_DIR"

echo "Generating RS256 key pair..."
openssl genrsa -out "$SECRETS_DIR/jwt_private.pem" 2048
openssl rsa -in "$SECRETS_DIR/jwt_private.pem" -pubout -out "$SECRETS_DIR/jwt_public.pem"
echo "Keys written to $SECRETS_DIR/"
echo "  jwt_private.pem (email-notifier only)"
echo "  jwt_public.pem  (gateway + approval-ui)"
