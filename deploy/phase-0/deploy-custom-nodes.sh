#!/bin/bash
# deploy-custom-nodes.sh
#
# Salin semua custom node ke dalam container n8n yang sedang berjalan.
# Jalankan ini setiap kali:
#   1. Baru saja docker compose up -d (tanpa --build)
#   2. Mengubah kode node dan sudah pnpm build di packages/nodes-base
#
# Penggunaan:
#   chmod +x deploy-custom-nodes.sh
#   ./deploy-custom-nodes.sh
#   ./deploy-custom-nodes.sh my-custom-container-name  (opsional)

set -e  # stop jika ada perintah yang error

CONTAINER_NAME="${1:-phase-0-n8n-1}"

# Path relatif dari lokasi script ini ke root repo
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NODES_BASE="$REPO_ROOT/packages/nodes-base"
CLI_DIST="$REPO_ROOT/packages/cli/dist"
CONTAINER_BASE="/usr/local/lib/node_modules/n8n/node_modules/n8n-nodes-base"
CONTAINER_CLI="/usr/local/lib/node_modules/n8n/dist"

# ===== Warna output =====
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
RED='\033[0;31m'
NC='\033[0m'  # No Color

echo ""
echo -e "${CYAN}Deploy custom nodes ke $CONTAINER_NAME ...${NC}"

# ===== Cek container running =====
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}ERROR: Container '$CONTAINER_NAME' tidak running.${NC}"
    echo "Jalankan dulu: docker compose up -d"
    exit 1
fi

# ===== Cek dist sudah ada =====
if [ ! -f "$NODES_BASE/dist/nodes/AgentMST/AgentMST.node.js" ]; then
    echo -e "${RED}ERROR: File dist tidak ditemukan.${NC}"
    echo "Jalankan dulu di packages/nodes-base:"
    echo "  cd $NODES_BASE && pnpm build"
    exit 1
fi

# ===== Copy AgentMST node =====
echo -e "${GRAY}  Membuat folder di container ...${NC}"
docker exec -u root "$CONTAINER_NAME" mkdir -p "$CONTAINER_BASE/dist/nodes/AgentMST"

echo -e "${GRAY}  Copying AgentMST.node.js ...${NC}"
docker cp "$NODES_BASE/dist/nodes/AgentMST/AgentMST.node.js" \
    "$CONTAINER_NAME:$CONTAINER_BASE/dist/nodes/AgentMST/AgentMST.node.js"

echo -e "${GRAY}  Copying AgentMST.node.json ...${NC}"
docker cp "$NODES_BASE/dist/nodes/AgentMST/AgentMST.node.json" \
    "$CONTAINER_NAME:$CONTAINER_BASE/dist/nodes/AgentMST/AgentMST.node.json"

echo -e "${GRAY}  Copied: AgentMST JS + JSON${NC}"

# ===== Copy node-definitions =====
DEF_SRC="$NODES_BASE/dist/node-definitions/nodes/n8n-nodes-base/agentMST"
DEF_DEST="$CONTAINER_BASE/dist/node-definitions/nodes/n8n-nodes-base/agentMST"

if [ -d "$DEF_SRC" ]; then
    docker exec -u root "$CONTAINER_NAME" mkdir -p "$DEF_DEST"
    for f in "$DEF_SRC"/*; do
        fname=$(basename "$f")
        docker cp "$f" "$CONTAINER_NAME:$DEF_DEST/$fname"
    done
    echo -e "${GRAY}  Copied: node-definitions${NC}"
fi

# ===== Sync package.json =====
docker cp "$NODES_BASE/package.json" "$CONTAINER_NAME:$CONTAINER_BASE/package.json"
echo -e "${GRAY}  Copied: package.json${NC}"

# ===== Copy chat-hub services (misikaAi provider fix) =====
for f in chat-hub-workflow.service.js chat-hub.service.js mst-agent.service.js; do
    src="$CLI_DIST/modules/chat-hub/$f"
    if [ -f "$src" ]; then
        docker cp "$src" "$CONTAINER_NAME:$CONTAINER_CLI/modules/chat-hub/$f"
        echo -e "${GRAY}  Copied: $f${NC}"
    fi
done

# ===== Copy LmChatMistikaAi (x-api-key fix + URL rewrite + model fallback) =====
LANGCHAIN_SRC="$REPO_ROOT/packages/@n8n/nodes-langchain/dist"
LANGCHAIN_DEST="/usr/local/lib/node_modules/n8n/node_modules/@n8n/n8n-nodes-langchain"
if [ -f "$LANGCHAIN_SRC/nodes/llms/LmChatMistikaAi/LmChatMistikaAi.node.js" ]; then
    docker exec -u root "$CONTAINER_NAME" mkdir -p "$LANGCHAIN_DEST/dist/nodes/llms/LmChatMistikaAi"
    docker cp "$LANGCHAIN_SRC/nodes/llms/LmChatMistikaAi/LmChatMistikaAi.node.js" \
        "$CONTAINER_NAME:$LANGCHAIN_DEST/dist/nodes/llms/LmChatMistikaAi/LmChatMistikaAi.node.js"
    echo -e "${GRAY}  Copied: LmChatMistikaAi.node.js${NC}"
fi
if [ -f "$LANGCHAIN_SRC/credentials/MistikaAiApi.credentials.js" ]; then
    docker exec -u root "$CONTAINER_NAME" mkdir -p "$LANGCHAIN_DEST/dist/credentials"
    docker cp "$LANGCHAIN_SRC/credentials/MistikaAiApi.credentials.js" \
        "$CONTAINER_NAME:$LANGCHAIN_DEST/dist/credentials/MistikaAiApi.credentials.js"
    echo -e "${GRAY}  Copied: MistikaAiApi.credentials.js${NC}"
fi

# ===== Restart container =====
echo -e "${YELLOW}  Restart $CONTAINER_NAME ...${NC}"
docker restart "$CONTAINER_NAME" > /dev/null

# ===== Tunggu sampai n8n ready =====
echo -e "${GRAY}  Menunggu n8n siap ...${NC}"
for i in $(seq 1 30); do
    sleep 2
    if docker logs "$CONTAINER_NAME" --tail 5 2>&1 | grep -q "accessible via"; then
        break
    fi
done

echo ""
echo -e "${GREEN}Selesai! n8n siap di http://localhost:5678${NC}"
echo -e "${GREEN}Buka workflow baru dan cari node 'MST Agent'${NC}"
echo ""
