# mstworkflow custom n8n image — Phase 0
#
# Multi-stage build from source.  ALL fork changes (backend + frontend) are
# compiled here — no patching of the official image required.
#
# Build (from repo root):
#   docker build -f deploy/phase-0/Dockerfile -t mstworkflow/n8n:phase-0 .
#
# Requirements:
#   - Docker with BuildKit enabled (default since Docker 23)
#   - ~4 GB free disk space for the build

# ─── Stage 1: Compile everything from source ──────────────────────────────────
FROM node:24-alpine AS builder

# Native-addon build tools + py3-setuptools for node-gyp@8 distutils compat
RUN apk add --no-cache python3 py3-setuptools make g++ git

# Activate the exact pnpm version declared in package.json
RUN corepack enable && corepack prepare pnpm@10.32.1 --activate

WORKDIR /build

# Copy workspace manifests first so the install layer is cached when only
# source files change.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json .npmrc tsconfig.json ./
COPY scripts/ ./scripts/
COPY patches/ ./patches/
COPY packages/ ./packages/

# pnpm install runs lifecycle scripts including:
#   preinstall  → scripts/block-npm-install.js  (needs pnpm, passes OK)
#   prepare     → scripts/prepare.mjs → pnpm lefthook install (needs .git dir)
#   postinstall → sqlite3 compile, isolated-vm compile, etc.
# We create a minimal .git so lefthook can install hooks without error.
RUN git init .
RUN pnpm install --frozen-lockfile

# Build only n8n (packages/cli) and all its transitive workspace dependencies.
# NODE_OPTIONS increases the V8 heap limit so tsc can compile packages/cli
# (the largest package) without hitting the default ~2 GB limit.
RUN NODE_OPTIONS=--max-old-space-size=3072 pnpm exec turbo run build --filter=n8n...

# Create a production-only bundle: packages/cli + all its workspace deps,
# only production node_modules, structured the way n8n expects at runtime.
RUN pnpm deploy --filter=n8n --prod --legacy /compiled

# ─── Stage 2: Rebuild native addons against the runtime libc ──────────────────
FROM node:24-alpine AS native-builder

# py3-setuptools provides the 'distutils' compatibility shim required by
# node-gyp@8.x — Python 3.12+ removed distutils from the standard library.
RUN apk add --no-cache python3 py3-setuptools make g++

COPY --from=builder /compiled /usr/local/lib/node_modules/n8n

# Rebuild sqlite3 (required for Alpine/musl)
RUN cd /usr/local/lib/node_modules/n8n && npm rebuild sqlite3

# Rebuild isolated-vm from source.
# node-gyp-build's musl detection relies on /etc/alpine-release which
# some base images omit, causing the glibc prebuilt to be loaded instead
# and segfaulting on musl pthread paths.
RUN if [ -d /usr/local/lib/node_modules/n8n/node_modules/isolated-vm ]; then \
      cd /usr/local/lib/node_modules/n8n/node_modules/isolated-vm && \
      rm -rf prebuilds && \
      npx --yes node-gyp rebuild --release -j 2; \
    fi

# ─── Stage 3: Minimal runtime image ───────────────────────────────────────────
FROM node:24-alpine

RUN apk add --no-cache \
    tini \
    su-exec \
    tzdata \
    openssl \
    git \
    openssh-client && \
    # Ensure the node user exists (node:24-alpine already has uid 1000)
    addgroup -g 1000 node 2>/dev/null || true && \
    adduser  -u 1000 -G node -D node 2>/dev/null || true

WORKDIR /home/node

# Copy the compiled + native-rebuilt n8n bundle
COPY --from=native-builder /usr/local/lib/node_modules/n8n \
                            /usr/local/lib/node_modules/n8n

# Copy entrypoint script from the repo
COPY docker/images/n8n/docker-entrypoint.sh /docker-entrypoint.sh

RUN ln -s /usr/local/lib/node_modules/n8n/bin/n8n /usr/local/bin/n8n && \
    chmod +x /docker-entrypoint.sh && \
    mkdir -p /home/node/.n8n && \
    chown -R node:node /home/node

ENV NODE_ENV=production
ENV N8N_USER_FOLDER=/home/node
ENV SHELL=/bin/sh

EXPOSE 5678/tcp
USER node

ENTRYPOINT ["tini", "--", "/docker-entrypoint.sh"]
