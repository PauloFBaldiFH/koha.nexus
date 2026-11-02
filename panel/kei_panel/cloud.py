"""Cloud backup with rclone: every service rclone knows, without its
command line (the panel's screen is screens/cloud_backup.py).

  * the catalog: `rclone config providers` (JSON) read into Backends and
    their Options, so the form of any service (Google Drive, OneDrive,
    Dropbox, MEGA, S3 and its dozens of compatibles, Backblaze B2, SFTP,
    WebDAV/Nextcloud, SMB, FTP, pCloud, Box...) is drawn from rclone itself;
  * the answers go to a private file (save_file, 0600) for
    `config.sh --task cloud-save FILE`, which creates or changes the rclone
    connection (with an optional encrypted layer) and deletes the file;
  * Authorizer: the browser sign-in of the services that need one (OAuth),
    on a server with no browser too. rclone authorize listens on
    127.0.0.1:53682 of the server; the panel follows its first redirect to
    get the provider's own sign-in address, which works on any computer
    (Copy link). The provider then sends the browser back to
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
from dataclasses import dataclass, field
from pathlib import Path

LOCAL_URL = re.compile(r"http://127\.0\.0\.1:(\d{2,5})/auth\?state=[A-Za-z0-9_-]+")
DEMO_CATALOG = Path(__file__).with_name("data") / "rclone_backends_demo.json"
CRYPT_SUFFIX = "-crypt"
SQL_DIR = "Backup_SQL_Koha"
MARC_DIR = "Backup_MARC_Koha"

# The services people look for first, in this order, with a plain name.
POPULAR = {
    "drive": "Google Drive",
    "onedrive": "Microsoft OneDrive",
    "dropbox": "Dropbox",
    "mega": "MEGA",
    "s3": "Amazon S3 & compatibles (Wasabi, R2, MinIO...)",
    "b2": "Backblaze B2",
    "pcloud": "pCloud",
    "box": "Box",
    "webdav": "WebDAV (Nextcloud, ownCloud...)",
    "sftp": "SFTP (another server, a NAS)",
    "smb": "Shared folder (SMB, Windows/NAS)",
    "ftp": "FTP",
    "protondrive": "Proton Drive",
    "koofr": "Koofr",
    "yandex": "Yandex Disk",
    "azureblob": "Microsoft Azure Blob Storage",
    "gcs": "Google Cloud Storage (not Google Drive)",
    "local": "A folder of this machine (USB, NAS)",
}
# Backends that only wrap or join others (crypt is offered as the
# "encrypt" switch), or cannot take files: never offered as a destination.
HIDDEN = {"alias", "memory", "crypt", "cache", "chunker", "combine", "compress", "union", "hasher", "http",
          "tardigrade", "uptobox", "premiumizeme", "gphotos", "google photos", "doi", "archive"}
# Settings the form never shows: the OAuth plumbing (the sign-in button
# fills token) and rclone's own config questions.
SKIP_OPTIONS = {"token", "auth_url", "token_url", "config_is_local", "config_refresh_token", "description"}
# A sign-in in the browser (rclone authorize) is how these get their token.
OAUTH_EXTRA = {"putio", "sharefile", "hidrive", "box", "dropbox", "pcloud", "yandex", "zoho", "onedrive", "drive"}
# Object storage: the first folder of a path is a bucket (container), so the
# backups need a folder there (the bucket's name, created when missing).
BUCKETS = {"s3", "b2", "gcs", "google cloud storage", "azureblob", "swift", "oracleobjectstorage", "qingstor",
           "storj", "internetarchive"}
# A setting whose value is never shown back (cloud-show leaves it out).
SECRET = re.compile(r"(pass|secret|token|key_pem|sas_url|^key$|api_key|private|bearer|credentials)", re.I)


# ----------------------------------------------------------------------
# The catalog of services
# ----------------------------------------------------------------------
@dataclass
class Option:
    name: str
    help: str = ""
    required: bool = False
    password: bool = False
    advanced: bool = False
    examples: list[tuple[str, str]] = field(default_factory=list)
    exclusive: bool = False
    default: str = ""
    kind: str = "string"
    provider: str = ""

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").capitalize()

    @property
    def summary(self) -> str:
        """The first sentence of rclone's help (the form's hint)."""
        first = self.help.strip().split("\n\n")[0].replace("\n", " ")
        return first[:220]

    @property
    def is_bool(self) -> bool:
        return self.kind == "bool"

    @property
    def secret(self) -> bool:
        return self.password or bool(SECRET.search(self.name))


@dataclass
class Backend:
    name: str                 # rclone's Name ("google cloud storage")
    prefix: str               # what `rclone config create` takes ("gcs")
    description: str
    options: list[Option] = field(default_factory=list)

    @property
    def label(self) -> str:
        return POPULAR.get(self.prefix) or self.description.split("(")[0].strip() or self.name

    @property
    def oauth(self) -> bool:
        return any(o.name == "token" for o in self.options) or self.prefix in OAUTH_EXTRA

    def option(self, name: str) -> Option | None:
        return next((o for o in self.options if o.name == name), None)


def _text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)) or value is None:
        return ""
    return str(value)


def parse_catalog(text: str) -> list[Backend]:
    """`rclone config providers` (any recent version) as Backends, the
    popular ones first, then the others by name; wrappers left out."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out: list[Backend] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        name, prefix = str(item.get("Name") or ""), str(item.get("Prefix") or item.get("Name") or "")
        if not prefix or name in HIDDEN or prefix in HIDDEN or item.get("Hide"):
            continue
        options = []
        for o in item.get("Options") or []:
            if not isinstance(o, dict) or not o.get("Name") or o.get("Hide"):
                continue
            examples = [(_text(e.get("Value")), str(e.get("Help") or "").split("\n")[0])
                        for e in o.get("Examples") or [] if isinstance(e, dict)]
            options.append(Option(str(o["Name"]), str(o.get("Help") or ""), bool(o.get("Required")),
                                  bool(o.get("IsPassword")), bool(o.get("Advanced")), examples,
                                  bool(o.get("Exclusive")), _text(o.get("Default")), str(o.get("Type") or "string"),
                                  str(o.get("Provider") or "")))
        out.append(Backend(name, prefix, str(item.get("Description") or name).strip(), options))
    order = list(POPULAR)
    out.sort(key=lambda b: (order.index(b.prefix) if b.prefix in order else len(order), b.label.lower()))
    return out


def demo_catalog() -> list[Backend]:
    try:
        return parse_catalog(DEMO_CATALOG.read_text(encoding="utf-8"))
    except OSError:
        return []


async def load_catalog(rclone: str = "rclone", timeout: float = 30) -> list[Backend]:
    """rclone's own list of services (no rclone.conf needed)."""
    proc = await asyncio.create_subprocess_exec(rclone, "config", "providers", stdin=asyncio.subprocess.DEVNULL,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return []
    return parse_catalog(out.decode("utf-8", "replace")) if proc.returncode == 0 else []


def find_backend(catalog: list[Backend], kind: str) -> Backend | None:
    """The backend of a connection's type (listremotes --long gives the
    Name, "google cloud storage"; the file may hold the prefix)."""
    kind = (kind or "").strip().lower()
    return next((b for b in catalog if kind in (b.name.lower(), b.prefix.lower())), None)


def search(catalog: list[Backend], text: str) -> list[Backend]:
    words = (text or "").lower().split()
    if not words:
        return list(catalog)
    def hay(b: Backend) -> str:
        return " ".join((b.label, b.name, b.prefix, b.description)).lower()
    return [b for b in catalog if all(w in hay(b) for w in words)]


def provider_matches(rule: str, provider: str) -> bool:
    """An option's Provider rule: "" (all), "AWS,Ceph" (only those) or
    "!AWS,Minio" (all but those)."""
    rule = (rule or "").strip()
    if not rule:
        return True
    negative = rule.startswith("!")
    names = [n.strip() for n in rule.lstrip("!").split(",") if n.strip()]
    return provider not in names if negative else provider in names


def form_options(backend: Backend, values: dict[str, str], advanced: bool = False) -> list[Option]:
    """The settings the form shows for the answers so far: the provider
    chosen (S3: AWS, Wasabi, R2...) decides which region/endpoint rows
    apply; the advanced ones only when asked."""
    provider = values.get("provider", "")
    seen: set[str] = set()
    out = []
    for o in backend.options:
        if o.name in SKIP_OPTIONS or o.name in seen or (o.advanced and not advanced):
            continue
        if o.name != "provider" and not provider_matches(o.provider, provider):
            continue
        seen.add(o.name)
        out.append(o)
    return out


def missing(backend: Backend, values: dict[str, str], keep: set[str] = frozenset()) -> list[Option]:
    """Required settings still empty (a secret kept from before counts)."""
    return [o for o in form_options(backend, values) if o.required and not o.is_bool
            and not values.get(o.name, "").strip() and not o.default and o.name not in keep]


def answers(backend: Backend, values: dict[str, str], advanced: bool = False) -> dict[str, str]:
    """What goes to rclone: the settings shown and filled, minus the ones
    left at rclone's default."""
    out = {}
    for o in form_options(backend, values, advanced):
        v = values.get(o.name, "")
        v = v if o.is_bool else v.strip()
        if v == "" or (v == o.default and o.name != "provider"):
            continue
        out[o.name] = v
    if values.get("token"):
        out["token"] = values["token"]
    return out


# ----------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------
def name_problem(name: str, taken: list[str] | tuple[str, ...] = ()) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", name or ""):
        return "Use a short name: a letter, then letters, digits, _ or -."
    if name.endswith(CRYPT_SUFFIX) and len(name) > len(CRYPT_SUFFIX):
        return "Names ending in -crypt are kept for the encrypted layer."
    if name.lower() in {n.lower() for n in taken}:
        return "There is already a connection with this name."
    return ""


def base_problem(base: str) -> str:
    """The folder of the cloud the backup folders go in ("" = the top)."""
    b = (base or "").strip().strip("/")
    if not b:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9._ /-]{1,200}", b) or any(p in ("", ".", "..") for p in b.split("/")):
        return "Use letters, digits, spaces, . _ - and / between folders."
    return ""


def needs_bucket(kind: str) -> bool:
    return (kind or "").strip().lower() in BUCKETS


def clean_base(base: str) -> str:
    return (base or "").strip().strip("/")


def folders(base: str) -> tuple[str, str]:
    """The SQL and MARC21 folders under base, as the installer writes them."""
    b = clean_base(base)
    return (f"{b}/{SQL_DIR}" if b else SQL_DIR, f"{b}/{MARC_DIR}" if b else MARC_DIR)


def base_of(sql_folder: str) -> str:
    """The base folder of a SQL folder from backup.conf."""
    sql_folder = clean_base(sql_folder)
    if sql_folder == SQL_DIR:
        return ""
    return sql_folder[: -len(SQL_DIR) - 1] if sql_folder.endswith("/" + SQL_DIR) else sql_folder


def keep_problem(text: str, low: int = 0) -> str:
    if not re.fullmatch(r"\d{1,4}", (text or "").strip()) or int(text) < low:
        return "Type a number of days."
    return ""


def bwlimit_problem(text: str) -> str:
    """rclone's --bwlimit: 2M, 512k, or a timetable "08:00,1M 19:00,off"."""
    text = (text or "").strip()
    if not text:
        return ""
    size = r"(\d+(\.\d+)?[BbKkMmGgTtPp]?|off)(:(\d+(\.\d+)?[BbKkMmGgTtPp]?|off))?"
    slot = rf"((Mon|Tue|Wed|Thu|Fri|Sat|Sun)-)?\d{{1,2}}:\d{{2}},{size}"
    if re.fullmatch(size, text) or re.fullmatch(rf"{slot}( {slot})*", text):
        return ""
    return "Examples: 2M, 512k, or 08:00,1M 19:00,off"


def password_problem(password: str, again: str) -> str:
    if len(password or "") < 10:
        return "Use at least 10 characters for the encryption password."
    if password != again:
        return "The two passwords are not the same."
    return ""


def token_problem(text: str) -> str:
    """"" for a whole rclone OAuth token (JSON with both tokens and the expiry)."""
    try:
        data = json.loads(clean_token(text))
    except ValueError:
        return "The token is not complete: copy all of it, from { to }."
    if not isinstance(data, dict) or not data.get("access_token") or "expiry" not in data:
        return "The token is not complete: copy all of it, from { to }."
    return ""


def clean_token(raw: str) -> str:
    """A pasted token as one line of JSON: line breaks, a byte-order mark,
    quotes around it, typographic quotes and PowerShell's \\" removed."""
    s = re.sub(r"[\x00-\x1f\x7f]", "", raw or "").lstrip("\ufeff")
    s = s.replace("\u201c", '"').replace("\u201d", '"').strip()
    if len(s) > 1 and s[0] in "'\"" and s[-1] == s[0] and s[1:2] == "{" and s[-2:-1] == "}":
        s = s[1:-1]
    if '\\"' in s:
        s = s.replace('\\"', '"')
    try:
        data = json.loads(s)
    except ValueError:
        return s
    return json.dumps(data, separators=(",", ":")) if isinstance(data, dict) else s


@dataclass
class Pasted:
    kind: str            # "token", "redirect" or "" (with problem)
    value: str
    problem: str = ""


def classify(text: str) -> Pasted:
    """What the person pasted: rclone's token, or the address the browser
    ended on after the sign-in (http://localhost:53682/?code=...&state=...)."""
    text = (text or "").strip()
    if text.lstrip("\ufeff'\"").startswith("{"):
        problem = token_problem(text)
        return Pasted("" if problem else "token", "" if problem else clean_token(text), problem)
    parts = urllib.parse.urlsplit(text)
    query = urllib.parse.parse_qs(parts.query)
    if parts.scheme == "http" and parts.hostname in ("localhost", "127.0.0.1") and "state" in query \
            and ("code" in query or "error" in query):
        return Pasted("redirect", text)
    return Pasted("", text, "Paste the whole address from the browser's address bar (it starts with "
                            "http://localhost:53682/), or the token.")


def save_file(name: str, kind: str, mode: str, values: dict[str, str], crypt: str = "", crypt2: str = "",
              crypt_dir: str = "") -> Path:
    """The answers for `--task cloud-save` (0600; the task deletes it)."""
    fd, path = tempfile.mkstemp(prefix="kei-cloud-", suffix=".tsv")
    os.fchmod(fd, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(f"name\t{name}\ntype\t{kind}\nmode\t{mode}\n")
            for key, value in values.items():
                if "\t" in value or "\n" in value or not re.fullmatch(r"[a-z0-9_]{1,64}", key):
                    raise ValueError(key)
                fh.write(f"opt\t{key}\t{value}\n")
            for key, value in (("crypt", crypt), ("crypt2", crypt2), ("cryptdir", crypt_dir)):
                if value:
                    if "\t" in value or "\n" in value:
                        raise ValueError(key)
                    fh.write(f"{key}\t{value}\n")
    except ValueError:
        Path(path).unlink(missing_ok=True)
        raise
    return Path(path)


def settings_file(values: dict[str, str]) -> Path:
    """KEY<TAB>VALUE lines for `--task cloud-settings` (0600)."""
    fd, path = tempfile.mkstemp(prefix="kei-cloudset-", suffix=".tsv")
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for key, value in values.items():
            fh.write(f"{key}\t{value}\n")
    return Path(path)


# ----------------------------------------------------------------------
# What the installer's cloud tasks answer
# ----------------------------------------------------------------------
@dataclass
class Entry:
    is_dir: bool
    name: str
    size: int = 0
    modified: str = ""     # "2026-11-02T23:00:12"

    @property
    def when(self) -> str:
        return self.modified.replace("T", " ")[:16]


def parse_entries(lines: list[str]) -> list[Entry]:
    out = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2 or parts[0] not in ("D", "F"):
            continue
        size = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        out.append(Entry(parts[0] == "D", parts[1], size, parts[3] if len(parts) > 3 else ""))
    return out


def is_backup_name(name: str) -> bool:
    n = name.lower()
    return bool(re.fullmatch(r"[a-z0-9._-]+\.sql(\.(gz|zst|xz|bz2))?", n)) or \
        bool(re.fullmatch(r"koha_marc_[0-9_-]+\.tar\.gz", n))


@dataclass
class Remote:
    name: str
    kind: str          # rclone's type name ("drive", "google cloud storage")

    @property
    def encrypted(self) -> bool:
        return self.kind == "crypt"


def parse_remotes(lines: list[str]) -> list[Remote]:
    out = []
    for line in lines:
        name, _, kind = line.partition("\t")
        if name:
            out.append(Remote(name.strip(), kind.strip()))
    return out


@dataclass(frozen=True)
class Plan:
    """A cloud backup: what the installer keeps in cloud_plans.conf. Its
    schedule and what it sends are its cron job (cron.cloud_job)."""
    id: str
    remote: str
    base: str
    keep: int          # days kept in the cloud, 0 = everything

    def folders(self) -> tuple[str, str]:
        return folders(self.base)

    def where(self) -> str:
        return f"{self.remote}:{self.base + '/' if self.base else ''}"


def parse_plans(lines: list[str]) -> list[Plan]:
    """cloud-status "plan" lines: ID<TAB>CONNECTION<TAB>FOLDER<TAB>DAYS."""
    out = []
    for line in lines:
        parts = (line.split("\t") + ["", "", "", ""])[:4]
        if not parts[0]:
            continue
        keep = int(parts[3]) if parts[3].isdigit() else 0
        out.append(Plan(parts[0], parts[1], clean_base(parts[2]), keep))
    return out


def plan_problem(plan_id: str, taken: list[str] | tuple[str, ...] = ()) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", plan_id or ""):
        return "Use a short name: a letter, then letters, digits, _ or -."
    if plan_id.endswith(CRYPT_SUFFIX):
        return "Names ending in -crypt are kept for the encrypted layer."
    if plan_id.lower() in {n.lower() for n in taken}:
        return "There is already a cloud backup with this name."
    return ""


def free_plan_id(remote: str, taken: list[str] | tuple[str, ...]) -> str:
    """A name for a new cloud backup to REMOTE: the connection's own, then -2, -3..."""
    low = {n.lower() for n in taken}
    base = remote[:28] or "cloud"
    if base.lower() not in low:
        return base
    n = 2
    while f"{base}-{n}".lower() in low:
        n += 1
    return f"{base}-{n}"


@dataclass
class History:
    which: str        # sql or marc
    when: str
    text: str
    ok: bool

    @property
    def cloud(self) -> bool:
        return "Cloud" in self.text or "cloud" in self.text or "RCLONE_REMOTE" in self.text


def parse_history(lines: list[str]) -> list[History]:
    """The backup logs' lines ("2026-11-02 23:00:41 | Cloud OK: gdrive:Backup_SQL_Koha/ (file)")."""
    out = []
    for line in lines:
        which, _, rest = line.partition("\t")
        when, sep, text = rest.partition(" | ")
        if not sep:
            when, text = "", rest
        bad = text.startswith(("WARN", "FAILED")) or "failed" in text
        out.append(History(which, when.strip(), text.strip(), not bad))
    return out


def last_cloud(history: list[History]) -> History | None:
    """The newest line about the cloud (an upload or its failure)."""
    cloud = [h for h in history if h.cloud and "cleanup" not in h.text]
    return max(cloud, key=lambda h: h.when) if cloud else None


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

    def __init__(self, provider: str, rclone: str = "rclone", extra: tuple[str, ...] = ()):
        # extra: the library's own client id and secret, when it has them.
        self.provider, self.rclone, self.extra = provider, rclone, tuple(extra)
        self.proc: asyncio.subprocess.Process | None = None
        self.port = 53682
        self.local_url = ""
        self.output: list[str] = []

    async def start(self, wait: float = 30) -> str:
        """The address to open (Microsoft's, else rclone's local one)."""
        self.proc = await asyncio.create_subprocess_exec(
            self.rclone, "authorize", self.provider, *self.extra, "--auth-no-open-browser",
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

    def __init__(self, provider: str, rclone: str = "rclone", extra: tuple[str, ...] = ()):
        super().__init__(provider, rclone, extra)
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
