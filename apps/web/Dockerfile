# Frontend image. Built from the repo root so the workspace packages resolve:
#   docker build -f apps/web/Dockerfile .

FROM node:22-alpine AS deps
WORKDIR /repo
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/
COPY packages/types/package.json ./packages/types/
COPY packages/ui/package.json ./packages/ui/
RUN npm ci


FROM node:22-alpine AS builder
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/apps/web/node_modules ./apps/web/node_modules
COPY package.json package-lock.json ./
COPY packages ./packages
COPY apps/web ./apps/web
RUN npm run build --workspace apps/web


FROM node:22-alpine AS runner
WORKDIR /repo
ENV NODE_ENV=production

COPY --from=builder /repo/node_modules ./node_modules
COPY --from=builder /repo/packages ./packages
COPY --from=builder /repo/package.json ./package.json
COPY --from=builder /repo/apps/web ./apps/web

# Run as a non-root user (the `node` user ships with the base image).
USER node

WORKDIR /repo/apps/web
EXPOSE 3000
CMD ["npx", "next", "start", "--port", "3000", "--hostname", "0.0.0.0"]
