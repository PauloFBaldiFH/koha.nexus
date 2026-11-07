# syntax=docker/dockerfile:1.7
ARG SOLR_IMAGE
FROM ${SOLR_IMAGE} AS runtime
ARG DSPACE_VERSION
ARG SOURCE_REVISION
LABEL org.opencontainers.image.title="Nexus DSpace Solr" \
      org.opencontainers.image.version="${DSPACE_VERSION}" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.source="https://github.com/DSpace/DSpace" \
      org.opencontainers.image.licenses="BSD-3-Clause AND Apache-2.0"
COPY --from=backend-source --chown=8983:8983 /dspace/solr /opt/nexus-solr
COPY --from=backend-source /LICENSE /usr/share/licenses/dspace/LICENSE
COPY --from=backend-source /NOTICE /usr/share/licenses/dspace/NOTICE
COPY --chmod=0555 solr-entrypoint.sh /usr/local/bin/nexus-solr
ENV SOLR_OPTS="-Dsolr.config.lib.enabled=true" SOLR_HEAP=512m
USER 8983:8983
ENTRYPOINT ["docker-entrypoint.sh", "/usr/local/bin/nexus-solr"]
