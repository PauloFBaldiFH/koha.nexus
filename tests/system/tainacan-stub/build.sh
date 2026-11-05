#!/bin/bash
# Builds the test double of the Tainacan plugin (tainacan.php next to this
# script) as a zip plus a checksums file in the format wordpress.org
# publishes. Only for tests/tainacan_system.bats where wordpress.org cannot
# be reached: OUT/tainacan.zip and OUT/checksums.json.
set -e
here="$(cd "$(dirname "$0")" && pwd)"; out="$1"
mkdir -p "$out"
( cd "$here" && rm -f "$out/tainacan.zip" && python3 -I -c '
import hashlib, json, sys, zipfile
z = zipfile.ZipFile(sys.argv[1], "w")
z.write("tainacan/tainacan.php")
z.close()
h = hashlib.sha256(open("tainacan/tainacan.php", "rb").read()).hexdigest()
m = hashlib.md5(open("tainacan/tainacan.php", "rb").read()).hexdigest()
json.dump({"plugin": "tainacan", "version": "1.4.1", "source": "test", "zip": "test",
           "files": {"tainacan.php": {"md5": m, "sha256": h}}}, open(sys.argv[2], "w"))
' "$out/tainacan.zip" "$out/checksums.json" )
