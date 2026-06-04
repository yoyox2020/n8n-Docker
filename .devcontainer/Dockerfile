ARG NODE_VERSION=24

FROM node:${NODE_VERSION}-alpine

ARG NODE_VERSION

RUN apk add --no-cache \
    openssh sudo shadow bash libc-utils \
    git openssl graphicsmagick tini tzdata ca-certificates libc6-compat
RUN echo node ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/node && chmod 0440 /etc/sudoers.d/node
RUN mkdir /workspaces && chown node:node /workspaces
RUN corepack enable

USER node
ENV PNPM_HOME=/home/node/.local/share/pnpm
ENV PNPM_STORE_PATH=/home/node/.pnpm-store
RUN mkdir -p /home/node/.pnpm-store
