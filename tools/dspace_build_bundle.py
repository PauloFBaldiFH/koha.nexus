#!/usr/bin/env python3
"""Create/check the deterministic, installer-pinned experimental build kit."""
import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'platforms/dspace/build-inputs.zip'
FILES = ['LICENSE', 'tools/dspace_images.py', 'tools/dspace_catalog.py',
         'tools/dspace_smoke.py', 'tools/dspace_bootstrap.py'] + [
    'platforms/dspace/' + name for name in
    ('release.json', 'release-r3.json', 'contract.json', 'ui-dependencies.json', 'ui-cookie-metadata.patch')]
FILES += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / 'platforms/dspace/images').iterdir()) if p.is_file()]


def create(path):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(FILES):
            entry = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, (ROOT / name).read_bytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        import io
        data = io.BytesIO()
        create(data)
        if data.getvalue() != OUTPUT.read_bytes():
            parser.exit(1, 'DSpace build kit is stale; run python3 tools/dspace_build_bundle.py\n')
    else:
        create(OUTPUT)
