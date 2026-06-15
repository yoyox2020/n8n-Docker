# Asuralab custom n8n image — Phase 0
# Extends the official n8n image with a rebranded login page.
#
# Build context: n8n repo root  (cd n8n-Docker && docker build -f deploy/phase-0/Dockerfile .)
# The frontend must be compiled first:
#   pnpm --filter=n8n-editor-ui... build
#
FROM n8nio/n8n:latest

USER root

# Replace the compiled frontend dist with our custom build.
# The official image bundles editor-ui as a local pnpm workspace package;
# the path below is where pnpm places its compiled output inside the image.
COPY packages/frontend/editor-ui/dist/ \
     /usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-editor-ui@file+packages+frontend+editor-ui/node_modules/n8n-editor-ui/dist/

USER node
