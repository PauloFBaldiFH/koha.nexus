# syntax=docker/dockerfile:1.7
ARG NODE_IMAGE
FROM ${NODE_IMAGE} AS build
WORKDIR /src
COPY --from=ui-source / /src/
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
      apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca update; \
    else apt-get update; fi \
    && apt-get install -y --no-install-recommends python3 make g++ \
    && rm -rf /var/lib/apt/lists/*
RUN --mount=type=secret,id=proxy_ca \
    set -eu; \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --strict-ssl=true; \
    NODE_OPTIONS=--max-old-space-size=4096 npm run build:prod; \
    test -s dist/server/main.js

FROM ${NODE_IMAGE} AS runtime
ARG DSPACE_VERSION
ARG SOURCE_REVISION
LABEL org.opencontainers.image.title="Nexus DSpace interface" \
      org.opencontainers.image.version="${DSPACE_VERSION}" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.source="https://github.com/DSpace/dspace-angular" \
      org.opencontainers.image.licenses="BSD-3-Clause"
WORKDIR /app
COPY --from=build --chown=0:0 /src/dist /app/dist
COPY --from=ui-source --chown=0:0 /config /app/config
COPY --from=ui-source /LICENSE /usr/share/licenses/dspace-ui/LICENSE
COPY --from=ui-source /NOTICE /usr/share/licenses/dspace-ui/NOTICE
COPY --from=ui-source /LICENSES_THIRD_PARTY /usr/share/licenses/dspace-ui/LICENSES_THIRD_PARTY
COPY --chmod=0555 ui-entrypoint.sh /usr/local/bin/nexus-dspace-ui
# Upstream generates hashed browser configuration and index.html at startup.
# The server bundle and source configuration remain root-owned.
RUN mkdir -p /app/log && chown -R node:node /app/log /app/dist/browser
ENV NODE_ENV=production \
    DSPACE_UI_HOST=0.0.0.0 \
    DSPACE_UI_SSL=false \
    DSPACE_UI_PORT=4000 \
    NODE_OPTIONS=--max-old-space-size=1024
USER node
EXPOSE 4000
ENTRYPOINT ["/usr/local/bin/nexus-dspace-ui"]
