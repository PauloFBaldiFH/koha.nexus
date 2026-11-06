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
* Input tests: 13 passed on Python 3.9 and 13 passed on Python 3.13.
* Entrypoint shell syntax and workflow YAML parsing passed.
* Solr image built; real startup smoke passed with all seven expected cores and
  UID 8983. No public ports were opened. Temporary container/volume removed.
* Backend assembly reached Maven dependency resolution but was blocked by HTTP
  403 on `https://handle.net/maven`. That dependency is required by upstream;
  it was not removed or replaced with an unverified download.
* Full backend build/startup remains pending CI. UI status will be recorded before
  handoff. A workflow being present does not mean it has passed.

Local builds use the managed Docker vfs driver and initially exhausted temporary
disk when backend cache and Solr layers coexisted. Only this task's cache records
and smoke resources were removed; pre-existing images/volumes were preserved.
The independent CI build jobs avoid accumulating all three builds on one runner.

## Before merge

All three image builds and their smoke checks must pass on the exact PR commit.
Review component inventory and candidate dependency versions; no production
security certification is claimed. Until those checks pass, this is a draft.

## Next implementation step

Build an isolated installer consuming immutable, published application image
digests. It must generate private configuration, explicitly migrate the database,
initialize PostgreSQL/Solr, route UI/API, journal phases and recover after reboot.
First establish the image distribution channel and resulting digests; never
substitute a development image or build application sources during user setup.

This PR's runtime smoke is narrower than acceptance. Repository login, deposits,
private access, actual backend/UI SSR, consistent backup and isolated restoration
are required in later stages before the installation can be considered ready.
