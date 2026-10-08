"""Cloud backup with rclone on OneDrive, MEGA or an S3 bucket, without the
rclone command line.

The Google Drive flows of the backup center are not touched (they live in
routines/backup.py and the installer). This module holds the other
providers:

  * PROVIDERS: what each one asks for; settings_file() writes the answers
    to a private file for `config.sh --task cloud-provider FILE`, which
    creates the rclone remote, tests a real upload and makes it the backup
    destination;
  * Authorizer: the OneDrive sign-in on a server with no browser. rclone
    authorize listens on 127.0.0.1:53682 of the server; the panel follows
    its first redirect to get Microsoft's own sign-in address, which works
    on any computer (Copy link). Microsoft then sends the browser back to
    http://localhost:53682/?code=..., a page that does not open on the
    person's computer: they paste that address in the panel, which hands it
    to rclone here, and rclone prints the token. A token made with rclone
    on another computer can be pasted as well.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PROVIDERS = {
    "onedrive": "Microsoft OneDrive",
    "mega": "MEGA",
    "s3": "Amazon S3 or compatible (Wasabi, Cloudflare R2, MinIO...)",
}
S3_PROVIDERS = {"AWS": "Amazon Web Services (S3)", "Cloudflare": "Cloudflare R2", "Wasabi": "Wasabi",
                "Minio": "MinIO", "Other": "Another S3-compatible service"}
RESERVED = ("gdrive",)        # the Google Drive flow's own remote
LOCAL_URL = re.compile(r"http://127\.0\.0\.1:(\d{2,5})/auth\?state=[A-Za-z0-9_-]+")


# ----------------------------------------------------------------------
# Answers
# ----------------------------------------------------------------------
def name_problem(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", name or ""):
        return "Use a short name: a letter, then letters, digits, _ or -."
    if name.lower() in RESERVED:
        return "The name gdrive belongs to the Google Drive backup."
    return ""


def bucket_problem(bucket: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket or "") or ".." in bucket:
        return "A bucket name has 3 to 63 lowercase letters, digits, dots or hyphens."
    return ""


def endpoint_problem(url: str) -> str:
    if not re.fullmatch(r"https?://[A-Za-z0-9.-]+(:\d+)?/?", url or ""):
        return "Type the service address, for example https://s3.wasabisys.com"
    return ""


def token_problem(text: str) -> str:
    """"" for a whole rclone OAuth token (JSON with both tokens and the expiry)."""
    try:
        data = json.loads((text or "").strip())
    except ValueError:
        return "The token is not complete: copy all of it, from { to }."
    if not isinstance(data, dict) or not data.get("access_token") or "expiry" not in data:
        return "The token is not complete: copy all of it, from { to }."
    return ""


@dataclass
class Pasted:
    kind: str            # "token", "redirect" or "" (with problem)
    value: str
    problem: str = ""


def classify(text: str) -> Pasted:
    """What the person pasted: rclone's token, or the address the browser
    ended on after the sign-in (http://localhost:53682/?code=...&state=...)."""
    text = (text or "").strip()
    if text.startswith("{"):
        problem = token_problem(text)
        return Pasted("" if problem else "token", text, problem)
    parts = urllib.parse.urlsplit(text)
    query = urllib.parse.parse_qs(parts.query)
    if parts.scheme == "http" and parts.hostname in ("localhost", "127.0.0.1") and "state" in query \
            and ("code" in query or "error" in query):
        return Pasted("redirect", text)
    return Pasted("", text, "Paste the whole address from the browser's address bar (it starts with "
                            "http://localhost:53682/), or the token.")


def settings_file(name: str, provider: str, values: dict[str, str]) -> Path:
    """The answers for `--task cloud-provider` (0600; the task deletes it)."""
    fd, path = tempfile.mkstemp(prefix="kei-cloud-", suffix=".tsv")
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(f"name\t{name}\ntype\t{provider}\n")
        for key, value in values.items():
            if "\t" in value or "\n" in value:
                raise ValueError(key)
            fh.write(f"{key}\t{value}\n")
    return Path(path)


# ----------------------------------------------------------------------
# OneDrive sign-in on a server with no browser
# ----------------------------------------------------------------------
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):   # noqa: D102
        return None


def provider_url(local_url: str, timeout: float = 10) -> str:
    """The sign-in page rclone's local address sends the browser to."""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        opener.open(local_url, timeout=timeout)
    except urllib.error.HTTPError as e:
        location = e.headers.get("Location", "")
        if 300 <= e.code < 400 and location.startswith("https://"):
            return location
    except OSError:
        pass
    return local_url


def deliver(pasted_url: str, port: int, timeout: float = 15) -> None:
    """Hands the sign-in answer to rclone, listening on this server."""
    parts = urllib.parse.urlsplit(pasted_url)
    target = urllib.parse.urlunsplit(("http", f"127.0.0.1:{port}", parts.path or "/", parts.query, ""))
    try:
        urllib.request.urlopen(target, timeout=timeout).read(100_000)   # noqa: S310 (rclone on this server)
    except urllib.error.HTTPError:
        pass                 # rclone says on its page; the token (or its error) comes on its output


class Authorizer:
    """`rclone authorize PROVIDER --auth-no-open-browser`, run on this server."""

    def __init__(self, provider: str, rclone: str = "rclone"):
        self.provider, self.rclone = provider, rclone
        self.proc: asyncio.subprocess.Process | None = None
        self.port = 53682
        self.local_url = ""
        self.output: list[str] = []

    async def start(self, wait: float = 30) -> str:
        """The address to open (Microsoft's, else rclone's local one)."""
        self.proc = await asyncio.create_subprocess_exec(
            self.rclone, "authorize", self.provider, "--auth-no-open-browser",
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait
        while loop.time() < deadline:
            try:
                line = await asyncio.wait_for(self.proc.stdout.readline(), max(0.1, deadline - loop.time()))
            except asyncio.TimeoutError:
                break
            if not line:
                break
            text = line.decode("utf-8", "replace")
            self.output.append(text)
            m = LOCAL_URL.search(text)
            if m:
                self.local_url, self.port = m.group(0), int(m.group(1))
                return await asyncio.to_thread(provider_url, self.local_url)
        await self.stop()
        raise RuntimeError("rclone did not print an authorization link (is port 53682 busy?)")

    async def token(self) -> str:
        """Waits for rclone to print the token (after the sign-in)."""
        assert self.proc is not None
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                break
            self.output.append(line.decode("utf-8", "replace"))
        await self.proc.wait()
        for text in self.output:
            m = re.search(r"\{.*\}", text)
            if m and not token_problem(m.group(0)):
                return m.group(0)
        tail = " ".join(t.strip() for t in self.output[-3:] if "token" not in t)
        raise RuntimeError(tail or "rclone did not return a token")

    async def answer(self, pasted_url: str) -> None:
        await asyncio.to_thread(deliver, pasted_url, self.port)

    async def stop(self) -> None:
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), 5)
            except asyncio.TimeoutError:
                self.proc.kill()


class DemoAuthorizer(Authorizer):
    """Demo mode: no rclone; any pasted answer gives a token."""

    def __init__(self, provider: str):
        super().__init__(provider)
        self._got = asyncio.Event()

    async def start(self, wait: float = 30) -> str:
        return ("https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=demo"
                "&redirect_uri=http%3A%2F%2Flocalhost%3A53682%2F&response_type=code&state=demo")

    async def token(self) -> str:
        await self._got.wait()
        return '{"access_token":"demo","token_type":"Bearer","refresh_token":"demo","expiry":"2030-01-01T00:00:00Z"}'

    async def answer(self, pasted_url: str) -> None:
        self._got.set()

    async def stop(self) -> None:
        return None
