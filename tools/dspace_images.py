#!/usr/bin/env python3
"""Versioned build inputs for DSpace. Engineering tool, never an installer.

No shell evaluation, registry writes, host service changes, or migrations.
The UI remains unsupported in the panel until later implementation stages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "platforms/dspace"
REPOSITORIES = {
    "backend": "https://github.com/DSpace/DSpace.git",
    "ui": "https://github.com/DSpace/dspace-angular.git",
}


def load_release(path: Path = BASE / "release.json") -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or data.get("status") != "experimental":
        raise ValueError("Unsupported release schema or maturity")
    if data.get("recipe") != 4 or data.get("architectures") != ["linux/amd64"]:
        raise ValueError("Only the experimental amd64 recipe is currently supported")
    if set(data.get("sources", {})) != set(REPOSITORIES):
        raise ValueError("Expected backend and UI sources")
    for name, source in data["sources"].items():
        if source.get("repository") != REPOSITORIES[name]:
            raise ValueError("Unexpected upstream repository")
        if not re.fullmatch(r"[0-9a-f]{40}", source.get("commit", "")):
            raise ValueError("Source must be pinned to a full commit")
        if not re.fullmatch(r"dspace-\d+\.\d+(?:\.\d+)?", source.get("tag", "")):
            raise ValueError("Source must be a stable release tag")
        if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", source.get("version", "")):
            raise ValueError("Invalid source version")
        if source["tag"][7:].split(".")[:2] != source["version"].split(".")[:2]:
            raise ValueError("Source version does not match its release tag")
    if data["sources"]["backend"]["tag"] != data["sources"]["ui"]["tag"]:
        raise ValueError("Backend and UI releases must match")
    expected = {"maven", "java", "node", "postgres", "solr"}
    if set(data.get("bases", {})) != expected:
        raise ValueError("Incomplete base image matrix")
    for reference in data["bases"].values():
        if not re.fullmatch(r"docker\.io/[a-z0-9-]+:[A-Za-z0-9_.-]+@sha256:[0-9a-f]{64}", reference):
            raise ValueError("Base images require a registry, version and sha256 digest")
    if set(data.get("images", {})) != {"backend", "ui", "solr"}:
        raise ValueError("Unexpected application image set")
    for name, image in data["images"].items():
        if image != {"dockerfile": name + ".Dockerfile", "source": "ui" if name == "ui" else "backend"}:
            raise ValueError("Unexpected image recipe")
    patch = data.get("ui_patch", {})
    if patch.get("file") != "ui-dependencies.json" or not re.fullmatch(r"[0-9a-f]{64}", patch.get("sha256", "")):
        raise ValueError("A reviewed UI dependency patch is required")
    if hashlib.sha256((BASE / patch["file"]).read_bytes()).hexdigest() != patch["sha256"]:
        raise ValueError("UI dependency patch checksum mismatch")
    source_patch = data.get('ui_source_patch', {})
    if source_patch.get('file') != 'ui-cookie-metadata.patch' or hashlib.sha256((BASE / 'ui-cookie-metadata.patch').read_bytes()).hexdigest() != source_patch.get('sha256'):
        raise ValueError('UI cookie metadata patch checksum mismatch')
    previous = data.get('previous_release', {})
    if previous != {'file':'release-r3.json', 'sha256':'72c8cec876cbc1ae991c07f19253d2d5bddfe62123e0cfc5572b57480149d608'}:
        raise ValueError('Unreviewed previous release')
    if hashlib.sha256((BASE / previous['file']).read_bytes()).hexdigest() != previous['sha256']:
        raise ValueError('Previous release checksum mismatch')
    return data


def source_stamp(data: dict) -> dict:
    return {"sources": data["sources"], "ui_patch": data["ui_patch"], 'ui_source_patch': data['ui_source_patch']}


def apply_ui_source_patch(directory: Path, patch: dict) -> None:
    if patch.get('file') != 'ui-cookie-metadata.patch':
        raise ValueError('Unexpected UI source patch')
    path = BASE / patch['file']
    if hashlib.sha256(path.read_bytes()).hexdigest() != patch.get('sha256'):
        raise ValueError('UI source patch checksum mismatch')
    # Only used in the fresh pinned checkout, never in a user's source tree.
    run('git', '-C', str(directory), 'apply', '--index', '--check', str(path.resolve()))
    run('git', '-C', str(directory), 'apply', '--index', str(path.resolve()))


def apply_ui_patch(directory: Path, patch: dict) -> None:
    """Modify only two JSON dependency files, checking both input and output bytes."""
    if set(patch) != {"package.json", "package-lock.json"}:
        raise ValueError("Only UI dependency files may be patched")
    outputs = {}
    for filename, change in patch.items():
        path = directory / filename
        original = path.read_bytes()
        if hashlib.sha256(original).hexdigest() != change["before"]:
            raise ValueError("Upstream dependency file differs from reviewed patch")
        value = json.loads(original)
        if filename == "package.json":
            value = change["value"]
        else:
            for key in change["remove"]:
                del value["packages"][key]
            value["packages"].update(change["update"])
        result = (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
        if hashlib.sha256(result).hexdigest() != change["after"]:
            raise ValueError("Dependency patch output checksum mismatch")
        outputs[path] = result
    for path, result in outputs.items():
        path.write_bytes(result)


def validate_ui_toolchain(directory: Path) -> None:
    package = json.loads((directory / 'package.json').read_text())
    lock = json.loads((directory / 'package-lock.json').read_text())
    tools = ('@angular-devkit/build-angular', '@angular/cli', '@ngtools/webpack')
    versions = {package['devDependencies'][tool] for tool in tools}
    if len(versions) != 1 or not re.fullmatch(r'\d+\.\d+\.\d+', next(iter(versions))):
        raise ValueError('Angular build tools must use one exact version')
    selected = next(iter(versions))
    webpack = package['devDependencies']['webpack']
    if not re.fullmatch(r'\d+\.\d+\.\d+', webpack) or lock['packages']['node_modules/webpack']['version'] != webpack:
        raise ValueError('Root Webpack must be fixed to the compatible exact version')
    for path, entry in lock['packages'].items():
        if any(path.endswith('/' + tool) for tool in tools) and entry.get('version') != selected:
            raise ValueError('Mixed Angular build-tool versions in dependency graph')


def validate_sources(data: dict, directory: Path) -> None:
    """Check exact exported contents, not an editable checkout with a matching HEAD."""
    stamp = json.loads((directory / "sources.json").read_text(encoding="utf-8"))
    if stamp != source_stamp(data):
        raise ValueError("Prepared sources do not match this release")
    ns = {"m": "http://maven.apache.org/POM/4.0.0"}
    backend = ET.parse(directory / "backend-source/pom.xml").findtext("m:version", namespaces=ns)
    ui = json.loads((directory / "ui-source/package.json").read_text())["version"]
    if backend != data["sources"]["backend"]["version"] or ui != data["sources"]["ui"]["version"]:
        raise ValueError("Upstream package versions do not match the release")
    for source in (directory / "backend-source", directory / "ui-source"):
        if not source.is_dir() or source.is_symlink():
            raise ValueError("Source directory missing or symlinked")
    expected = json.loads((directory / "checksums.json").read_text())
    if not expected or expected != source_checksums(directory):
        raise ValueError("Prepared source files changed; prepare a fresh source directory")


def source_checksums(directory: Path) -> dict:
    hashes = {}
    for name in REPOSITORIES:
        base = directory / (name + "-source")
        for path in sorted(base.rglob("*")):
            if path.is_symlink():
                raise ValueError("Symlinks are not allowed in build sources")
            if path.is_file():
                hashes[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def run(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, **kwargs)


def prepare(data: dict, output: Path) -> None:
    """Fetch verified commits into a fresh directory; never overwrite user files."""
    if output.exists():
        raise ValueError("Output already exists; choose a new source directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".dspace-source-", dir=output.parent) as temporary:
        stage = Path(temporary)
        for name, source in data["sources"].items():
            checkout = stage / (name + "-checkout")
            run("git", "init", "-q", str(checkout))
            run("git", "-C", str(checkout), "remote", "add", "origin", source["repository"])
            run("git", "-C", str(checkout), "fetch", "--depth=1", "origin", "refs/tags/" + source["tag"])
            commit = run("git", "-C", str(checkout), "rev-parse", "FETCH_HEAD^{}", capture_output=True, text=True).stdout.strip()
            if commit != source["commit"]:
                raise ValueError("Upstream release tag moved; review the lock before building")
            run("git", "-C", str(checkout), "checkout", "-q", "--detach", commit)
            if name == 'ui':
                apply_ui_source_patch(checkout, data['ui_source_patch'])
            exported = stage / (name + "-source")
            # Export only tracked regular files. No .git, local credentials or hooks.
            files = run("git", "-C", str(checkout), "ls-files", "-z", capture_output=True).stdout.split(b"\0")
            for raw in filter(None, files):
                relative = Path(os.fsdecode(raw))
                original = checkout / relative
                if relative.is_absolute() or ".." in relative.parts or original.is_symlink() or not original.is_file():
                    raise ValueError("Unsupported file type in upstream release")
                destination = exported / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, destination)
                # Preserve Git's executable bit, without copying writable/special modes.
                destination.chmod(0o755 if original.stat().st_mode & 0o111 else 0o644)
            shutil.rmtree(checkout)
        apply_ui_patch(stage / "ui-source", json.loads((BASE / data["ui_patch"]["file"]).read_text()))
        validate_ui_toolchain(stage / "ui-source")
        (stage / "sources.json").write_text(json.dumps(source_stamp(data), indent=2) + "\n")
        (stage / "checksums.json").write_text(json.dumps(source_checksums(stage), sort_keys=True) + "\n")
        validate_sources(data, stage)
        # No secrets or untracked content can enter the build through the context.
        stage.rename(output)


def maven_proxy_settings(path: Path) -> bool:
    """Maven ignores HTTP_PROXY. Pass its proxy configuration as a build secret."""
    value = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if not value:
        return False
    proxy = urlsplit(value)
    if proxy.scheme not in ("http", "https") or not proxy.hostname:
        raise ValueError("Unsupported build proxy URL")
    root = ET.Element("settings")
    proxies = ET.SubElement(root, "proxies")
    item = ET.SubElement(proxies, "proxy")
    # Managed builders cannot resolve the outer container's hosts aliases.
    # Resolve the SAME configured proxy endpoint; never bypass it.
    host = socket.gethostbyname(proxy.hostname) if os.environ.get("CODEX_PROXY_CERT") else proxy.hostname
    fields = {"id": "build-proxy", "active": "true", "protocol": "http",
              "host": host, "port": str(proxy.port or 8080),
              "nonProxyHosts": os.environ.get("NO_PROXY", "localhost,127.0.0.1").replace(",", "|")}
    for key, value in (("username", proxy.username), ("password", proxy.password)):
        if value:
            fields[key] = unquote(value)
    for key, value in fields.items():
        ET.SubElement(item, key).text = value
    path.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    path.chmod(0o600)
    return True


def build_command(data: dict, sources: Path, name: str, prefix: str, metadata: Path,
                  maven_settings: Path | None = None) -> list[str]:
    if not re.fullmatch(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*", prefix):
        raise ValueError("Invalid image prefix (supply a lowercase repository path, without tag)")
    version = data["sources"]["backend"]["version"]
    args = ["docker", "--host=unix:///var/run/docker.sock", "buildx", "build", "--load",
            "--platform", data["architectures"][0], "--metadata-file", str(metadata),
            "--tag", f"{prefix}-{name}:{version}-r{data['recipe']}",
            "--file", str(BASE / "images" / data["images"][name]["dockerfile"])]
    source = data["images"][name]["source"]
    args += ["--build-context", f"{source}-source={sources / (source + '-source')}"]
    args += ["--build-context", f"nexus-license={BASE.parents[1]}"]
    for key, value in data["bases"].items():
        args += ["--build-arg", f"{key.upper()}_IMAGE={value}"]
    args += ["--build-arg", f"DSPACE_VERSION={version}", "--build-arg",
             f"SOURCE_REVISION={data['sources'][source]['commit']}", "--build-arg",
             f"RELEASE_LOCK_SHA256={hashlib.sha256((BASE / 'release.json').read_bytes()).hexdigest()}"]
    ca = os.environ.get("CODEX_PROXY_CERT")
    if ca:
        if not Path(ca).is_file():
            raise ValueError("Configured build proxy CA not found")
        args += ["--secret", f"id=proxy_ca,src={ca}"]
    if maven_settings:
        args += ["--secret", f"id=maven_settings,src={maven_settings}"]
    return args + [str(BASE / "images")]


def image_tag(data: dict, name: str) -> str:
    return f"nexus-dspace-{name}:{data['sources']['backend']['version']}-r{data['recipe']}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    tag = sub.add_parser("tag")
    tag.add_argument("image", choices=("backend", "ui", "solr"))
    fetch = sub.add_parser("prepare")
    fetch.add_argument("output", type=Path)
    build = sub.add_parser("build")
    build.add_argument("sources", type=Path)
    build.add_argument("--image", choices=("backend", "ui", "solr"), required=True)
    build.add_argument("--prefix", default="nexus-dspace")
    build.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = load_release()
        if args.command == "tag":
            print(image_tag(data, args.image))
        elif args.command == "prepare":
            prepare(data, args.output.resolve())
        elif args.command == "build":
            validate_sources(data, args.sources)
            args.metadata.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="dspace-build-") as temp:
                settings = Path(temp) / "settings.xml"
                use_proxy = args.image == "backend" and maven_proxy_settings(settings)
                run(*build_command(data, args.sources.resolve(), args.image, args.prefix,
                                   args.metadata.resolve(), settings if use_proxy else None))
        else:
            print("DSpace experimental release lock: valid; installation remains disabled")
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError, ET.ParseError) as error:
        parser.exit(1, f"DSpace image preparation failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
