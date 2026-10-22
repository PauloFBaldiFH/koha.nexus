# Synthetic import tests

Run the Magic Import reliability, migration and library-tool tests with Docker:

```sh
bash tests/run.sh
```

The runner creates a fresh Debian 12 container. It mounts this repository
read-only, installs dependencies from Debian's signed package repositories,
starts a local MariaDB and Memcached, and installs the command doubles from
`tests/mocks/`. A separate temporary directory holds the extracted installer
library and test state. Both the container and that directory are removed when
the runner finishes, including after failure or interruption.

The runner never connects to a host library database. Each test resets only
the disposable container's synthetic `koha_library` database. Do not run Bats
directly on an installed library server or source its setup helpers there.
Tests sharing the same database run sequentially.

Run selected files or a matching test:

```sh
bash tests/run.sh tests/magic_import_reliability.bats
bash tests/run.sh --filter 'R03' tests/magic_import_reliability.bats
```

All catalogue records and patron values in fixtures are synthetic. Uploaded
library exports must stay outside the repository and must not become fixtures
or appear in CI logs. Tests check that sensitive values remain out of public
validation reports.

MariaDB, Memcached, YAZ and Perl MARC readers are real in this harness; Koha's
commands are doubles. Passing this suite verifies orchestration, quoting,
validation, backups and error handling. It does not establish compatibility
with every installed Koha release. Any validation using real Koha must use a
separate disposable environment.

The Python import and mapper suites run independently:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pytest -r panel/requirements.txt
cd panel
../.venv/bin/python -m pytest -q tests/test_import_*_v2.py \
  tests/test_import_legacy_contracts.py tests/test_magic_engine.py \
  tests/test_fieldmap.py tests/test_fieldmap_screen.py
```

Install `zstd` to include compressed-format tests. The
`magic-import.yml` workflow runs these Python suites on Python 3.9 and 3.13
and runs the Docker Bats suite separately.
