#!/usr/bin/env python3
"""Smoke-test locally built images in disposable containers, without host ports.

This checks image startup/contracts only, NOT installation or repository readiness.
No named volumes, host mounts, host network, service restarts or migrations.
Any anonymous volume inherited from a base image is removed with its container.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid

from dspace_images import BASE, load_release

DOCKER = ["docker", "--host=unix:///var/run/docker.sock"]


def docker(*args, check=True):
    result = subprocess.run(DOCKER + list(args), capture_output=True, text=True)
    if check and result.returncode:
        # These are disposable smoke containers with no private configuration.
        raise RuntimeError(f"Docker smoke command failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
    return result


def smoke(image, prefix):
    release = load_release()
    version = release["sources"]["backend"]["version"]
    tag = f"{prefix}-{image}:{version}-r{release['recipe']}"
    name = "nexus-dspace-smoke-" + uuid.uuid4().hex[:12]
    if image == "backend":
        docker("run", "--rm", "--network", "none", "--entrypoint", "sh", tag, "-ec",
               'test "$(id -u)" = 10001 || { echo "wrong runtime UID" >&2; exit 1; }; '
               'test -s /dspace/webapps/server-boot.jar || { echo "missing server JAR" >&2; exit 1; }; '
               'test -x /dspace/bin/dspace || { echo "CLI not executable by runtime user" >&2; ls -l /dspace/bin/dspace >&2; exit 1; }; '
               'test -s /usr/share/licenses/dspace/LICENSE || { echo "missing license" >&2; exit 1; }; '
               'test ! -e /dspace/config/local.cfg || { echo "unexpected local.cfg" >&2; exit 1; }; java -version')
        result = docker("run", "--rm", "--network", "none", tag, check=False)
        if result.returncode != 78 or "Missing DSpace local.cfg" not in result.stderr:
            raise RuntimeError("Backend did not refuse missing installation configuration")
        return
    options = ["--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true"]
    if image == "ui":
        for value in ("DSPACE_UI_BASEURL=http://127.0.0.1:4000", "DSPACE_REST_HOST=127.0.0.1",
                      "DSPACE_REST_PORT=8080", "DSPACE_REST_SSL=false", "DSPACE_REST_NAMESPACE=/server",
                      "DSPACE_REST_SSRBASEURL=http://127.0.0.1:8080/server"):
            options += ["-e", value]
        probe = ["node", "-e", "fetch('http://127.0.0.1:4000/assets/images/dspace-logo.svg').then(async r=>{if(!r.ok || !(await r.text()).includes('<svg'))process.exit(1)}).catch(()=>process.exit(1))"]
    else:
        probe = ["curl", "-fsS", "http://127.0.0.1:8983/solr/admin/cores?action=STATUS&wt=json"]
    try:
        docker("run", "-d", "--name", name, *options, tag)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            result = docker("exec", name, *probe, check=False)
            if result.returncode == 0:
                if image == "solr":
                    cores = json.loads(result.stdout).get("status", {})
                    expected = json.loads((BASE / "contract.json").read_text())["solr_cores"]
                    if not all(core in cores for core in expected):
                        time.sleep(2)
                        continue
                uid = docker("exec", name, "id", "-u").stdout.strip()
                if uid == "0":
                    raise RuntimeError("Runtime started as root")
                print(f"{image}: startup and image contract passed as uid {uid}")
                return
            if docker("inspect", "-f", "{{.State.Running}}", name).stdout.strip() != "true":
                break
            time.sleep(2)
        # Disposable containers have no credentials or institutional data.
        logs = docker("logs", "--tail", "60", name, check=False)
        print(logs.stdout, logs.stderr)
        raise RuntimeError(f"{image}: startup smoke test failed")
    finally:
        docker("rm", "-f", "-v", name, check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", choices=("backend", "ui", "solr"))
    parser.add_argument("--prefix", default="nexus-dspace")
    args = parser.parse_args()
    smoke(args.image, args.prefix)
