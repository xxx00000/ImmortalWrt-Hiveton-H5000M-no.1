FROM node:24-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates && rm -rf /var/lib/apt/lists/* && mkdir /data && chown node:node /data
WORKDIR /app
COPY --chown=node:node package.json policy.json ./
COPY --chown=node:node shared ./shared
COPY --chown=node:node server ./server
COPY --chown=node:node public ./public
USER node
ENV NODE_ENV=production PORT=8787 HOST=0.0.0.0 DATA_DIR=/data
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s CMD node -e "fetch('http://127.0.0.1:8787/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server/main.mjs"]
