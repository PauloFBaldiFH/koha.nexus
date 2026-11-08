#!/usr/bin/env python3
"""Prepare experimental images locally; no publication, platform data or migration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

import dspace_images as images
from dspace_catalog import catalog


def trusted_directory(path):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ValueError('Build/catalog paths must not contain symbolic links')
    for parent in (path, *path.parents):
        if not parent.exists():
            continue
        info = parent.stat()
        sticky = parent != path and info.st_uid == 0 and info.st_mode & stat.S_ISVTX
        if info.st_uid not in (0, os.geteuid()) or (info.st_mode & 0o022 and not sticky):
            raise ValueError('Build/catalog directory is writable by another user')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def matching_image(data, name):
    proc = subprocess.run(['docker', '--host=unix:///var/run/docker.sock', 'image', 'inspect', images.image_tag(data, name)],
                          capture_output=True, text=True)
    if proc.returncode:
        return False
    image = json.loads(proc.stdout)[0]
    labels = image.get('Config', {}).get('Labels') or {}
    source = data['sources']['ui' if name == 'ui' else 'backend']['commit']
    return (image.get('Architecture') == 'amd64' and image.get('Os') == 'linux'
            and labels.get('org.opencontainers.image.revision') == source
            and labels.get('org.koha-nexus.dspace.release-lock') == hashlib.sha256((images.BASE / 'release.json').read_bytes()).hexdigest())


def prepare(target, workspace):
    data = images.load_release()
    target = Path(target).absolute()
    trusted_directory(target.parent)
    if target.exists() or target.is_symlink():
        raise ValueError('Existing catalog was preserved; it must be inspected rather than overwritten')
    workspace = trusted_directory(workspace)
    missing = [name for name in ('backend', 'ui', 'solr') if not matching_image(data, name)]
    sources = workspace / 'sources'
    if missing:
        if not sources.exists():
            images.prepare(data, sources)
        images.validate_sources(data, sources)
        for name in missing:
            print('Building experimental DSpace image: ' + name, file=sys.stderr, flush=True)
            with tempfile.TemporaryDirectory(prefix='proxy-', dir=workspace) as tmp:
                settings = Path(tmp) / 'settings.xml'
                proxy = name == 'backend' and images.maven_proxy_settings(settings)
                images.run(*images.build_command(data, sources, name, 'nexus-dspace', workspace / (name + '.json'), settings if proxy else None))
    # Run actual entrypoint checks before allowing the normal installer to use it.
    from dspace_smoke import smoke
    for name in ('backend', 'ui', 'solr'):
        print('Checking experimental DSpace image: ' + name, file=sys.stderr, flush=True)
        smoke(name, 'nexus-dspace')
    result = dict(catalog(), origin='local-build', experimental=True)
    fd, temporary = tempfile.mkstemp(prefix='.dspace-images-', dir=target.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(result, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        # No overwrite even if a catalog appeared during compilation.
        os.link(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', required=True, type=Path)
    parser.add_argument('--workspace', required=True, type=Path)
    args = parser.parse_args()
    try:
        prepare(args.catalog, args.workspace)
    except (ValueError, OSError, subprocess.SubprocessError, RuntimeError) as error:
        print('DSpace image preparation failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
