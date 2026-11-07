# syntax=docker/dockerfile:1.7
ARG MAVEN_IMAGE
ARG JAVA_IMAGE
FROM ${MAVEN_IMAGE} AS schema-guard
WORKDIR /guard-source
COPY NexusSchemaGuard.java ./
RUN mkdir /guard && javac -encoding UTF-8 -d /guard NexusSchemaGuard.java

FROM scratch AS schema-guard-artifact
COPY --from=schema-guard /guard/ /

FROM ${MAVEN_IMAGE} AS build
WORKDIR /src
COPY --from=backend-source / /src/
# The CA is optional for ordinary builders, and never enters the runtime image.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
      apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca update; \
    else apt-get update; fi \
    && apt-get install -y --no-install-recommends ant \
    && rm -rf /var/lib/apt/lists/*
RUN --mount=type=secret,id=proxy_ca --mount=type=secret,id=maven_settings \
    --mount=type=cache,id=nexus-dspace-maven,target=/root/.m2 \
    set -eu; \
    if [ -f /run/secrets/proxy_ca ]; then \
      cp "$JAVA_HOME/lib/security/cacerts" /tmp/build-cacerts; \
      keytool -importcert -noprompt -alias build-proxy -storepass changeit \
        -keystore /tmp/build-cacerts -file /run/secrets/proxy_ca; \
      export MAVEN_OPTS="-Djavax.net.ssl.trustStore=/tmp/build-cacerts -Djavax.net.ssl.trustStorePassword=changeit"; \
    fi; \
    if [ -f /run/secrets/maven_settings ]; then set -- --settings /run/secrets/maven_settings; else set --; fi; \
    mvn "$@" --batch-mode --no-transfer-progress package -P-test-environment \
      -DskipUnitTests=true -DskipIntegrationTests=true \
      -Dcheckstyle.skip=true -Dlicense.skip=true -Dxml.skip=true; \
    cd /src/dspace/target/dspace-installer; \
    ant install_code update_webapps; \
    test -s /dspace/webapps/server-boot.jar; \
    test -s /dspace/config/config-definition.xml; \
    test -s /dspace/config/dspace.cfg; \
    test -s /dspace/config/log4j2-cli.xml; \
    chmod 0555 /dspace/bin/*; \
    rm -rf /dspace/webapps/server /dspace/*.bak-* /tmp/build-cacerts; \
    rm -f /dspace/config/local.cfg

FROM ${JAVA_IMAGE} AS runtime
ARG DSPACE_VERSION
ARG SOURCE_REVISION
ARG RELEASE_LOCK_SHA256
LABEL org.opencontainers.image.title="Nexus DSpace backend" \
      org.opencontainers.image.version="${DSPACE_VERSION}" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.koha-nexus.dspace.release-lock="${RELEASE_LOCK_SHA256}" \
      org.opencontainers.image.source="https://github.com/DSpace/DSpace" \
      org.opencontainers.image.licenses="BSD-3-Clause AND GPL-3.0-or-later"
RUN groupadd --gid 10001 dspace && useradd --uid 10001 --gid 10001 \
      --home-dir /dspace --no-create-home --shell /usr/sbin/nologin dspace
COPY --from=build --chown=0:0 /dspace /dspace
COPY --from=backend-source /LICENSE /usr/share/licenses/dspace/LICENSE
COPY --from=backend-source /NOTICE /usr/share/licenses/dspace/NOTICE
COPY --from=backend-source /LICENSES_THIRD_PARTY /usr/share/licenses/dspace/LICENSES_THIRD_PARTY
COPY --chmod=0555 backend-entrypoint.sh /usr/local/bin/nexus-dspace
COPY --from=schema-guard /guard/ /usr/local/lib/nexus-dspace/
COPY NexusSchemaGuard.java /usr/share/licenses/nexus-dspace/NexusSchemaGuard.java
COPY --from=nexus-license /LICENSE /usr/share/licenses/nexus-dspace/LICENSE
RUN mkdir -p /dspace/assetstore /dspace/log /dspace/var /dspace/upload \
      /dspace/reports /dspace/exports /dspace/imports /dspace/handle-server \
    && chown -R 10001:10001 /dspace/assetstore /dspace/log /dspace/var \
      /dspace/upload /dspace/reports /dspace/exports /dspace/imports /dspace/handle-server \
      /dspace/solr/search/conf
ENV dspace__P__dir=/dspace \
    NEXUS_DSPACE_RELEASE_LOCK=${RELEASE_LOCK_SHA256} \
    JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=65.0 -Dfile.encoding=UTF-8" \
    JAVA_OPTS="-Xmx512m -Dfile.encoding=UTF-8"
WORKDIR /dspace
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/nexus-dspace"]
CMD ["server"]
