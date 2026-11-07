# DSpace foundation and experimental lifecycle (PRs 1–2 of 6)

This is an **experimental image recipe and build contract**, not a DSpace
production installer. The existing panel still reports DSpace as unsupported.
PR 2 adds an explicit experimental CLI adapter; it does not run unless requested.
Installation remains blocked until reviewed immutable runtime images are published
and their catalog is configured. See [PR2-installer.md](../../docs/dspace/PR2-installer.md).
Nothing automatically starts a service, creates an account, publishes an address
or changes a Koha/Tainacan backup.

## Locked inputs

`release.json` records schema/recipe versions, upstream release tags and commits,
the matching UI release and complete base image references including sha256.
`contract.json` records internal ports, runtime users, Solr cores and data classes.
It explicitly says installation, backup and restore are not available yet.

| Component | Candidate for integration tests |
|---|---|
| DSpace backend | 10.1, Java 21 |
| Angular UI | 10.1.0, Node 22, production build |
| PostgreSQL | 15 (upstream example major), separately pinned image |
| Solr | 9.8.1, configsets from the exact backend release |
| Architectures | linux/amd64 only in this first CI |

The backend/UI sources were released together on 2026-09-14. Their tags are
checked against full commits before exporting tracked files. The reviewed
`ui-dependencies.json` then updates only package.json/package-lock.json: Angular
framework patches stay on 20.3, while build-angular, CLI and ngtools/webpack share
the upstream 20.3.36 toolchain. The original graph is preserved where possible,
instead of broadly updating unrelated dependencies. Patch bytes, input files and output files are sha256-checked;
an old prepared source directory must be recreated. No `--force`, peer-dependency
bypass, application-code patch or live dependency update during image startup.
Digests were
resolved on 2026-11-06. Neither a stable tag nor a digest is a security assessment:
this matrix remains a candidate until integration, vulnerability review and
recovery testing are complete. ARM64 support is deliberately not advertised.

Upstream explicitly marks its Docker examples as development/testing resources:
<https://github.com/DSpace/DSpace/blob/dspace-10.1/dspace/src/main/docker/README.md>.
These recipes borrow the assembly process, not the sample deployment, default
passwords or published database/Solr ports.

## Image behavior

* Backend: Maven/Ant assembly in a build stage, executable server JAR and CLI in
  the runtime, UID/GID 10001. No source checkout, Maven, Ant or build proxy trust
  store in the final image. Application code/config defaults are root-owned;
  data/work directories have explicit write permissions.
* Startup requires installation-specific `/dspace/config/local.cfg`. The image
  never silently falls back to the example database credentials. `server` starts
  a JDBC-only schema guard before Java; `cli COMMAND ...` runs DSpace's CLI.
  Upstream DSpace Context can automatically migrate: recipe 2 therefore requires
  a receipt of the exact release lock and successful Flyway history, recorded by
  the explicit installer operation. Missing/changed history refuses startup before
  loading DSpace, including after a Docker/host restart. The guard performs only
  SELECT in a read-only transaction; it never calls DSpace or Flyway itself.
* UI: `npm ci` with upstream lockfile, compiled production SSR bundle, direct
  Node execution as UID 1000. No PM2 cluster with a worker per host CPU and no
  development server/recompilation. Canonical public and internal API settings
  are mandatory; it cannot silently connect to the upstream sandbox.
* UI needs a writable browser distribution because upstream generates hashed
  configuration and `index.html` at startup. The server bundle remains root-owned.
  A completely read-only filesystem is not promised.
* Solr: non-root UID 8983, all seven upstream configsets, initial creation only.
  An existing core's configuration is not overwritten during a restart. Later
  upgrades must explicitly migrate configsets. Statistics/audit are not treated
  as disposable search caches.
* No default credentials, implicit installation migration, Docker socket,
  host mounts, sudo, systemd or host networking in these recipes. `EXPOSE` only
  documents internal ports; it does not publish them.

Java heap settings are actually consumed (`JAVA_TOOL_OPTIONS` for the server,
`JAVA_OPTS` for the upstream CLI). Application/container resource budgets will be
measured during integration. UI build memory and runtime memory are separate.

## Build and inspect (engineering workstation, not production)

Run from the repository root with Git, Python >=3.9 and Docker/Buildx. Builds use
the local Docker socket explicitly and never silently select a remote context.

```sh
python3 tools/dspace_images.py validate
python3 tools/dspace_images.py prepare /tmp/nexus-dspace-sources
python3 tools/dspace_images.py build /tmp/nexus-dspace-sources --image backend --metadata /tmp/dspace-results/backend.json
python3 tools/dspace_images.py build /tmp/nexus-dspace-sources --image ui --metadata /tmp/dspace-results/ui.json
python3 tools/dspace_images.py build /tmp/nexus-dspace-sources --image solr --metadata /tmp/dspace-results/solr.json
python3 tools/dspace_smoke.py backend
python3 tools/dspace_smoke.py ui
python3 tools/dspace_smoke.py solr
```

`prepare` requires a new destination, refuses a moved release tag and exports only
tracked regular files, without `.git` or local credentials. Source versions and
checksums are verified before each build. Do not edit the prepared directory;
recipe changes belong in this repository, source changes need a reviewed patch
strategy in a future PR.

Builds need internet access to the pinned registries, GitHub, Maven repositories
including `handle.net`, npm and OS package repositories. They may require several
GiB of temporary space; Docker's vfs driver uses substantially more disk than
overlayfs. The tool never removes unrelated images, caches or volumes to make
space. Maven/OS dependency resolution is not claimed to produce bit-identical
images; OS package patches and transitive Maven inputs still require auditing.
Record the resulting image digest and SBOM, not just its input tag.

In a managed proxy environment the inherited proxy is preserved. An optional
`CODEX_PROXY_CERT` is mounted as a BuildKit secret; Maven proxy settings are
passed as another temporary secret because Maven ignores HTTP_PROXY. The same
configured proxy endpoint is resolved for nested containers when necessary.
Neither proxy credentials nor the session CA is copied to a runtime image. TLS
verification stays enabled. A destination blocked by policy requires access to
be granted; this tool does not bypass it.

## CI and limits of validation

`.github/workflows/dspace-images.yml` checks inputs on Python 3.9/3.13, then builds
backend, UI and Solr separately on amd64 runners. It runs disposable, non-public
smoke containers and records build metadata, image configuration and SPDX SBOM.
It does **not** push images to any registry or deploy to a user's server.
The separate production-dependency audit job blocks high/critical advisories;
the original upstream lock failed that gate. The reviewed patch passes locally
with 0 high/critical, 6 moderate and 2 low advisories (2026-11-06 client date).
The dependency graph is still subject to future advisories and runtime review.

Smoke checks deliberately have different meanings:

* backend: assembled JAR/CLI, non-root Java, licenses and refusal of missing
  private configuration; **not** database startup/migration;
* UI: starts as non-root and serves a real static asset; **not** backend/API/SSR
  integration or login;
* Solr: starts as non-root with all expected cores; **not** repository recovery.

Only a passing workflow proves those jobs passed. A workflow file or an input
unit test does not prove a build or a functional repository. This PR must remain
draft while any build/startup check is unresolved.

Before releasing an installer, later PRs must test PostgreSQL+Solr+backend+UI
together, configuration/permissions, administrative access, submission/publication,
privacy, restart/reboot, checksum-preserving restore and update recovery. A
successful image build is not a production-readiness declaration.

## Next PRs

1. This PR: foundation, recipes and CI; keep DSpace unavailable in the panel.
2. Installer: owned Docker project/network/volumes, generated private config,
   explicit migration, proxy, resumable installation and lifecycle diagnostics.
3. Panel and admin: group, dashboard tab, setup assistant and real browser flow.
4. Consistent backup and isolated restore, including historical Solr data.
5. Shared backup sets and schedules, preserving existing plan participants.
6. Publication, broker capability, tested updates and operational documentation.

The architecture study in `docs/dspace/implementation-plan.pt-BR.md` contains the
full constraints and acceptance matrix. No Keycloak, portal, AtoM, new search
service or changes to the current Koha/Tainacan behavior are part of this PR.
