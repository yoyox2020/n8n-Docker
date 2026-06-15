#!/usr/bin/env bash
# provision.sh — Generate .env for Asuralab Phase 0
# Usage: ./scripts/provision.sh [email] [password]
# Requires: Docker (for bcrypt hash generation)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

# --- Args ---
OWNER_EMAIL="${1:-admin@asuralab.io}"
OWNER_PASSWORD="${2:-}"
OWNER_FIRST_NAME="${3:-Admin}"
OWNER_LAST_NAME="${4:-Asuralab}"

# --- Generate password if not supplied ---
if [ -z "$OWNER_PASSWORD" ]; then
  OWNER_PASSWORD=$(LC_ALL=C tr -dc 'A-Za-z0-9!@#%^&*' < /dev/urandom | head -c 20)
  echo "[provision] Generated password: $OWNER_PASSWORD"
fi

# --- Guard: don't overwrite existing .env without confirmation ---
if [ -f "$ENV_FILE" ]; then
  read -r -p "[provision] .env already exists. Overwrite? [y/N] " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "[provision] Aborted."
    exit 0
  fi
fi

echo "[provision] Generating bcrypt hash (rounds=12)..."
# Try Node.js first (fast), fall back to Docker
if command -v node &>/dev/null && node -e "require('bcryptjs')" &>/dev/null 2>&1; then
  OWNER_PASSWORD_HASH=$(PROVISION_PW="$OWNER_PASSWORD" node -e \
    "const b=require('bcryptjs'); console.log(b.hashSync(process.env.PROVISION_PW, 12))")
else
  echo "[provision] Node.js bcryptjs not found, trying Docker..."
  OWNER_PASSWORD_HASH=$(echo "$OWNER_PASSWORD" | docker run --rm -i python:3.11-alpine sh -c \
    "pip install bcrypt -q 2>/dev/null; python -c \"
import bcrypt, sys
pw = sys.stdin.read().strip().encode()
print(bcrypt.hashpw(pw, bcrypt.gensalt(12)).decode())
\"")
fi

# Docker Compose env_file also substitutes $VAR inside values, which corrupts
# bcrypt hashes ($2a$12$...). Escape each $ as $$ so Compose decodes it back
# to a single $ when passing to the container.
OWNER_PASSWORD_HASH=$(printf '%s' "$OWNER_PASSWORD_HASH" | sed 's/\$/$$/g')

echo "[provision] Generating random secrets..."
POSTGRES_PASSWORD=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)
N8N_ENCRYPTION_KEY=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)

# --- Write .env ---
cat > "$ENV_FILE" << EOF
# Asuralab Phase 0 — Auto-generated on $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# DO NOT COMMIT THIS FILE

# --- Owner ---
OWNER_EMAIL=$OWNER_EMAIL
OWNER_PASSWORD_HASH=$OWNER_PASSWORD_HASH
OWNER_FIRST_NAME=$OWNER_FIRST_NAME
OWNER_LAST_NAME=$OWNER_LAST_NAME

# --- Database ---
POSTGRES_USER=n8n
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=n8n

# --- n8n ---
N8N_ENCRYPTION_KEY=$N8N_ENCRYPTION_KEY
N8N_PORT=5678
N8N_HOST=localhost
N8N_PROTOCOL=http
WEBHOOK_URL=http://localhost:5678
N8N_LOG_LEVEL=info
N8N_PERSONALIZATION_ENABLED=false
EOF

echo ""
echo "=========================================="
echo "[provision] Done."
echo "  Owner email : $OWNER_EMAIL"
echo "  Password    : $OWNER_PASSWORD"
echo "  .env path   : $ENV_FILE"
echo "=========================================="
echo ""
echo "Next step: docker compose up -d"
