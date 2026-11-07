#!/usr/bin/env python3
"""Record exact tested image identities; never publish or install anything."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path(__file__).resolve().parents[1] / 'platforms/dspace'
REGISTRY = 'ghcr.io/paulofbaldifh/koha.nexus/dspace-'


def catalog(published=False):
    release = json.loads((BASE / 'release.json').read_text())
    images = {}
    for name in ('backend', 'ui', 'solr'):
        tag = 'nexus-dspace-%s:%s-r%s' % (name, release['sources']['backend']['version'], release['recipe'])
        data = json.loads(subprocess.check_output(
            ['docker', '--host=unix:///var/run/docker.sock', 'image', 'inspect', tag], text=True))[0]
        expected = release['sources']['ui' if name == 'ui' else 'backend']['commit']
        if data['Config']['Labels'].get('org.opencontainers.image.revision') != expected:
            raise ValueError('Unexpected source revision: ' + name)
        if data['Config']['Labels'].get('org.koha-nexus.dspace.release-lock') != hashlib.sha256((BASE / 'release.json').read_bytes()).hexdigest():
            raise ValueError('Image was built for another recipe/release: ' + name)
        if published:
            refs = [x for x in data.get('RepoDigests', []) if x.startswith(REGISTRY + name + '@sha256:')]
            if len(refs) != 1:
                raise ValueError('One published immutable digest is required: ' + name)
            images[name] = refs[0]
        else:
            images[name] = data['Id']
    return {'schema': 1, 'release_sha256': hashlib.sha256((BASE / 'release.json').read_bytes()).hexdigest(),
            'images': images}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--published', action='store_true')
    args = parser.parse_args()
    print(json.dumps(catalog(args.published), indent=2))
