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
* Input tests: 18 passed on Python 3.9 and 18 passed on Python 3.13, including
  refused patches with wrong source/checksum/path and valid deterministic replay.
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
The dependency audit job also blocks high/critical findings. The upstream lock
failed that gate; the reviewed dependency patch now passes locally with 0 high,
0 critical, 6 moderate and 2 low findings. Angular framework versions stay on
20.3 (20.3.34); the patch and its exact input/output bytes are hashed. No `--force`
or peer dependency bypass was used. The updated UI must rebuild and smoke-test
on the exact PR commit before merging; the earlier image smoke is not evidence
that the new lockfile builds. Until those checks pass, this is a draft.

## Follow-up for the first CI failures

The backend smoke failed because the root-owned CLI was not executable by UID
10001: the upstream script is a 0644 source file, and Ant added only owner execute
(0744). Assembly now explicitly installs bin scripts as 0555. A disposable
container reproduced the permission distinction for a non-root account. The
source exporter also preserves tracked executable bits for other scripts.

The smoke runner now reports stdout/stderr and names the failed assertion, rather
than hiding the reason inside CalledProcessError. Backend full build remains
blocked locally by handle.net access; confirm the result of the new CI run.

## Follow-up for the UI compiler failure

The public checks for commit d208624 show backend, Solr and production audit passed.
The two failures are UI builds from push and pull_request events. Reproducing the
same locked input locally failed with runtime imports of type-only symbols such
as SimpleChanges and HttpEvent. Dependency resolution had introduced multiple
incompatible instances of the Angular build plugin (20.3.34 and 20.3.42).

The new patch preserves more upstream dependencies: 155 lock records change,
instead of 1057. Framework/compiler security patches remain 20.3.34, while CLI,
build-angular and ngtools/webpack are all fixed at upstream's 20.3.36, including
custom-webpack's dependency. No application types, compiler checks, or audit
thresholds were removed. Source preparation now refuses mixed nested build-tool
versions, covered by a regression test.

The aligned graph passes the production audit locally (0 high/critical), strict
lockfile consistency checks and input tests. Its full image build and smoke must
still pass before merging; do not substitute the earlier unpatched image results.

## Next implementation step

Build an isolated installer consuming immutable, published application image
digests. It must generate private configuration, explicitly migrate the database,
initialize PostgreSQL/Solr, route UI/API, journal phases and recover after reboot.
First establish the image distribution channel and resulting digests; never
substitute a development image or build application sources during user setup.

This PR's runtime smoke is narrower than acceptance. Repository login, deposits,
private access, actual backend/UI SSR, consistent backup and isolated restoration
are required in later stages before the installation can be considered ready.
