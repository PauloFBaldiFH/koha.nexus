# PR 1: versioned DSpace image foundation

Base: koha.nexus 1.5.180 (`1d34ee8`). This change does not alter the panel version,
installer checksum, Koha, Tainacan, existing backups or broker. It adds engineering
assets only. DSpace remains unavailable in the platform catalog.

## Delivered

* Matching DSpace 10.1 backend/UI source commits and digest-pinned base images.
* An experimental platform contract with isolated services, internal ports,
  runtime users, Solr cores and recovery data classes.
* Three multi-stage/runtime image recipes: backend with CLI, compiled production
  UI and Solr with upstream configsets. Migrations are not run at startup.
* Source preparation and validation tool, including moved-tag refusal and source
  checksums, optional secret-mounted proxy/CA configuration, no registry writes.
* Python 3.9/3.13 validation, image build and disposable runtime smoke CI, plus
  metadata and SPDX component inventory. No deployment/publishing permissions.
* The architecture study and remaining integration/acceptance requirements.

## Local verification

* Source fetch: both official release tags resolved to the locked commits.
* Input tests: 14 passed on Python 3.9 and 14 passed on Python 3.13.
* Existing platform/core regression selection: 148 passed, 1 skipped.
* Entrypoint shell syntax and workflow YAML parsing passed.
* Solr image built; real startup smoke passed with all seven expected cores and
  UID 8983. No public ports were opened. Temporary container/volume removed.
* Backend assembly reached Maven dependency resolution but was blocked by HTTP
  403 on `https://handle.net/maven`. That dependency is required by upstream;
  it was not removed or replaced with an unverified download.
* UI: the full browser+SSR production build passed. The final image started as
  UID 1000 and served the real logo asset with no host port or backend. It does
  not prove integrated SSR, login or deposits. The entrypoint also refuses both
  legacy and current flags that enable upstream's self-signed TLS fallback.
* Full backend build/startup remains pending CI. A workflow being present does
  not mean it has passed.
* `npm audit --package-lock-only --omit=dev` against the upstream UI lock reported
  22 advisories (2 low, 11 moderate, 7 high, 2 critical) on 2026-11-06. These counts
  are dependency-graph findings, not proof of exploitability of every bundled
  path. They require review/compatible fixes before homologation; the unchanged
  candidate must not be deployed as a production release.

Local builds use the managed Docker vfs driver and initially exhausted temporary
disk when backend cache and Solr layers coexisted. Only this task's cache records
and smoke resources were removed; pre-existing images/volumes were preserved.
The independent CI build jobs avoid accumulating all three builds on one runner.

## Before merge

All three image builds and their smoke checks must pass on the exact PR commit.
The dependency audit job also blocks high/critical findings. The currently locked
upstream UI fails that gate: review compatible dependency patches and rebuild/test
the affected application before promotion. Do not force npm upgrades or suppress
the audit to make a check green. Until these checks pass, this is a draft.

## Next implementation step

Build an isolated installer consuming immutable, published application image
digests. It must generate private configuration, explicitly migrate the database,
initialize PostgreSQL/Solr, route UI/API, journal phases and recover after reboot.
First establish the image distribution channel and resulting digests; never
substitute a development image or build application sources during user setup.

This PR's runtime smoke is narrower than acceptance. Repository login, deposits,
private access, actual backend/UI SSR, consistent backup and isolated restoration
are required in later stages before the installation can be considered ready.
