"""RemoteFormScreen: one rclone connection, created or changed with a form
drawn from rclone's own catalog (cloud.Backend), never rclone's wizard.

  ╭ ☁ New cloud connection ─────────────── ① Service › ② Settings › ③ Test ╮
  │ [Search: drive, s3, nextcloud...]   ╭ Google Drive ─────────────────────╮ │
  │ ▸ Google Drive                      │ Connection name [gdrive_______]   │ │
  │   Microsoft OneDrive / SharePoint   ├ Sign in ──────────────────────────┤ │
  │   Dropbox                           │ [🔑 Sign in to Google Drive] ✓    │ │
  │   MEGA                              ├ Settings ─────────────────────────┤ │
  │   Amazon S3 and compatibles         │ Client id   [________] (optional) │ │
  │   ... every service of this rclone  │ Scope       [drive ▾]             │ │
  │                                     │ [x] Show advanced settings        │ │
  │ 63 services in this rclone          ├ 🔒 Encryption ────────────────────┤ │
  │                                     │ [ ] Encrypt before sending        │ │
  │                                     ╰───────────────────────────────────╯ │
  │                                            [💾 Save and test] [Cancel]     │
  ╰────────────────────────────────────────────────────────────────────────────╯

The screen only collects the answers. It closes with a dict (name, backend
prefix, mode create|update, values, crypt password) that the cloud backup
screen hands to `config.sh --task cloud-save`, then to the upload test.
A service with a browser sign-in (OAuth) gets its token from OAuthScreen
(rclone authorize on this machine, the link copied to any computer, or a
token pasted from rclone on another computer). Secrets of a connection
being edited never come back from the installer: their boxes stay empty
and keep the old value unless something is typed.
"""

from __future__ import annotations

from typing import Optional

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Select, Static, Switch
from textual.widgets.option_list import Option as ListOption

from .. import cloud
from ..i18n import t

OTHER = "__other__"


def _id(name: str) -> str:
    return name.replace(" ", "_")


class RemoteFormScreen(ModalScreen[Optional[dict]]):
    BINDINGS = [Binding("escape", "cancel", t("Cancel"))]

    def __init__(self, catalog: list[cloud.Backend], taken: list[str], *, remote: cloud.Remote | None = None,
                 current: dict[str, str] | None = None, secrets: set[str] | None = None,
                 has_crypt: bool = False):
        super().__init__()
        self.catalog = catalog
        self.taken = list(taken)
        self.remote = remote                       # None: a new connection
        self.values: dict[str, str] = dict(current or {})
        self.secrets = set(secrets or ())          # settings kept from before (not shown)
        self.has_crypt = has_crypt
        self.backend: cloud.Backend | None = cloud.find_backend(catalog, remote.kind) if remote else None
        self.shown: list[cloud.Backend] = list(catalog)
        self.advanced = False
        self.token = ""
        self._drawing = False

    @property
    def editing(self) -> bool:
        return self.remote is not None

    # --- layout -----------------------------------------------------------
    @staticmethod
    def _card(title: str, card_id: str, *classes: str) -> Vertical:
        card = Vertical(classes=" ".join(("sb-card",) + classes), id=card_id)
        card.border_title = title
        return card

    def compose(self) -> ComposeResult:
        title = t("✏ Edit cloud connection") if self.editing else t("☁ New cloud connection")
        with Vertical(id="cr-box"):
            with Horizontal(id="sb-head"):
                yield Label(title, classes="dialog-title", id="cr-title", markup=False)
                yield Static(t("① Service  ›  ② Settings  ›  ③ Test"), id="sb-steps", markup=False)
            with Horizontal(id="cr-body"):
                with Vertical(id="cr-left"):
                    yield Input(placeholder=t("Search: drive, s3, nextcloud, sftp..."), id="cr-search")
                    yield OptionList(id="cr-services")
                    yield Static("", id="cr-count", classes="sb-hint", markup=False)
                with VerticalScroll(id="cr-form"):
                    with self._card(t("Service"), "cr-service"):
                        yield Static(t("Choose a service on the left."), id="cr-about", classes="sb-hint",
                                     markup=False)
                        with Vertical(id="cr-name-box"):
                            yield Label(t("Connection name (how this panel and the backup log call it):"),
                                        classes="sb-prompt", markup=False)
                            yield Input(id="cr-name", max_length=32)
                    with self._card(t("Sign in"), "cr-signin", "-download"):
                        yield Static(t("This service is opened with your account in a browser. The panel gives "
                                       "the link to open on any computer, even when this server has no browser."),
                                     classes="sb-hint", markup=False)
                        with Horizontal(classes="sb-card-buttons"):
                            yield Button(t("🔑 Sign in"), id="cr-signin-go", variant="success")
                        yield Static("", id="cr-signin-state", markup=False)
                    with self._card(t("Settings"), "cr-settings"):
                        yield Vertical(id="cr-fields")
                        with Horizontal(classes="cr-switch-row"):
                            yield Switch(value=False, id="cr-advanced")
                            yield Label(t("Show advanced settings"), markup=False)
                    with self._card(t("🔒 Encryption"), "cr-crypt"):
                        with Horizontal(classes="cr-switch-row"):
                            yield Switch(value=False, id="cr-encrypt")
                            yield Label(t("Encrypt the backups on this server before they are sent"),
                                        markup=False)
                        yield Static(t("The cloud only sees scrambled names and contents. Without this password "
                                       "nobody can open the backups, not even you: write it down and keep it "
                                       "safe, away from this server."), classes="sb-hint", markup=False)
                        with Vertical(id="cr-crypt-fields"):
                            yield Label(t("Encryption password (10 characters or more):"), markup=False)
                            yield Input(password=True, id="cr-pass")
                            yield Label(t("The same password again:"), markup=False)
                            yield Input(password=True, id="cr-pass2")
                            with Vertical(id="cr-crypt-bucket-box"):
                                yield Label(t("Bucket that holds the encrypted backups (created if missing):"),
                                            markup=False)
                                yield Input(id="cr-crypt-bucket", placeholder="my-library-backups")
                        yield Static("", id="cr-crypt-note", classes="sb-hint", markup=False)
            yield Label("", id="cr-problem", classes="dialog-error", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("💾 Save and test"), id="cr-save", variant="primary")
                yield Button(t("Cancel"), id="cr-cancel")

    def on_mount(self) -> None:
        self.query_one("#cr-crypt-fields").display = False
        self.query_one("#cr-problem").display = False
        if not self.editing:
            self._fill_list()
        if self.editing:
            name = self.query_one("#cr-name", Input)
            name.value = self.remote.name
            name.disabled = True
            self.query_one("#cr-search").display = False
            self.query_one("#cr-services", OptionList).disabled = True
            if self.has_crypt:
                self.query_one("#cr-encrypt", Switch).disabled = True
                self.query_one("#cr-crypt-note", Static).update(t(
                    "Already encrypted: the backups go through ${name}. Its password is not changed here.",
                    name=self.remote.name + cloud.CRYPT_SUFFIX))
            if self.backend is None:
                self._problem(t("This rclone does not know the service '${type}'.", type=self.remote.kind))
            self._fill_list()
            self._choose(self.backend)
        else:
            if self.backend is None:
                self._choose(None)
            self.query_one("#cr-search", Input).focus()

    # --- the list of services -----------------------------------------------
    def _fill_list(self, text: str = "") -> None:
        self.shown = cloud.search(self.catalog, text) if not self.editing else (
            [self.backend] if self.backend else [])
        ol = self.query_one("#cr-services", OptionList)
        ol.clear_options()
        ol.add_options([ListOption(Text.assemble(t(b.label), ("  " + b.prefix, "dim")), id=b.prefix)
                        for b in self.shown])
        self.query_one("#cr-count", Static).update(
            t("${n} services in this rclone", n=len(self.catalog)) if not text
            else t("${n} of ${all} services", n=len(self.shown), all=len(self.catalog)))
        if self.backend in self.shown:
            ol.highlighted = self.shown.index(self.backend)
        elif self.shown and not self.editing:
            ol.highlighted = 0
            # The form follows the list: the first service found is the one open.
            self._choose(self.shown[0])

    @on(Input.Changed, "#cr-search")
    def _search(self, event: Input.Changed) -> None:
        self._fill_list(event.value)

    @on(Input.Submitted, "#cr-search")
    def _search_enter(self) -> None:
        if self.shown:
            self._choose(self.shown[0])

    @on(OptionList.OptionSelected, "#cr-services")
    @on(OptionList.OptionHighlighted, "#cr-services")
    def _picked(self, event) -> None:
        if self.editing or event.option_index >= len(self.shown):
            return
        backend = self.shown[event.option_index]
        if backend is not self.backend:
            self._choose(backend)

    def _choose(self, backend: cloud.Backend | None) -> None:
        if backend is not self.backend and not self.editing:
            self.values, self.token = {}, ""
        self.backend = backend
        about = self.query_one("#cr-about", Static)
        for card in ("#cr-signin", "#cr-settings", "#cr-crypt"):
            self.query_one(card).display = backend is not None
        if backend is None:
            about.update(t("Choose a service on the left."))
            self.query_one("#cr-name-box").display = False
            return
        self.query_one("#cr-name-box").display = True
        self.query_one("#cr-service").border_title = t(backend.label)
        about.update((backend.description + "\n" if backend.description.lower() != t(backend.label).lower() else "")
                     + f"rclone: {backend.prefix}" + ("  ·  " + t("sign-in in the browser") if backend.oauth else ""))
        name = self.query_one("#cr-name", Input)
        if not self.editing:
            name.value = self._free_name(backend.prefix)
        self.query_one("#cr-signin").display = backend.oauth
        self.query_one("#cr-signin-go", Button).label = t("🔑 Sign in to ${service}", service=t(backend.label))
        self._signin_state()
        self._draw_fields()

    def _free_name(self, prefix: str) -> str:
        base = "".join(c for c in prefix if c.isalnum()) or "cloud"
        if not base[0].isalpha():
            base = "c" + base
        name, n = base[:28], 2
        while name.lower() in {x.lower() for x in self.taken}:
            name, n = f"{base[:26]}{n}", n + 1
        return name

    def _signin_state(self) -> None:
        state = self.query_one("#cr-signin-state", Static)
        if self.token:
            state.update(t("✅ Signed in: the access was given to rclone on this server."))
        elif self.editing and "token" in self.secrets:
            state.update(t("Signed in before. Sign in again only if the backups stopped reaching the cloud."))
        else:
            state.update(t("Not signed in yet."))

    # --- the settings -------------------------------------------------------
    @work(exclusive=True, group="cr-draw")
    async def _draw_fields(self) -> None:
        self._drawing = True
        box = self.query_one("#cr-fields", Vertical)
        await box.remove_children()
        if self.backend is None:
            self._drawing = False
            return
        widgets = [self._field(o) for o in cloud.form_options(self.backend, self.values, self.advanced)]
        if not widgets:
            widgets = [Static(t("Nothing else to fill in for this service."), classes="sb-hint", markup=False)]
        await box.mount_all(widgets)
        for o in cloud.form_options(self.backend, self.values, self.advanced):
            self._show_other(o)
        self._drawing = False

    def _field(self, o: cloud.Option) -> Vertical:
        value = self.values.get(o.name, "")
        label = o.label + (" *" if o.required and not o.is_bool else "")
        if o.secret and o.name in self.secrets and not value:
            label += "  " + t("(kept: type only to change it)")
        parts: list = [Label(label, classes="cr-label", markup=False)]
        fid = f"cr-v-{_id(o.name)}"
        if o.is_bool:
            on_now = (value or o.default or "false").lower() == "true"
            parts.append(Switch(value=on_now, id=fid))
        elif o.examples and (o.exclusive or o.name == "provider" or len(o.examples) <= 60):
            options = [(f"{v}  ·  {h}" if h and h != v else v, v) for v, h in o.examples if v != ""]
            known = {v for _, v in options}
            if not o.exclusive:
                options.append((t("✎ Another value (type it below)"), OTHER))
            chosen = value or o.default
            if chosen and chosen not in known:
                chosen = OTHER if not o.exclusive else ""
            blank = not (o.required and o.exclusive)
            if not chosen or chosen is Select.NULL:
                chosen = Select.NULL if blank else options[0][1]
            parts.append(Select(options, value=chosen, id=fid, allow_blank=blank, prompt=t("Choose")))
            if not o.exclusive:
                parts.append(Input(value=value if value and value not in known else "",
                                   placeholder=o.default, id=f"cr-x-{_id(o.name)}", classes="cr-other"))
        else:
            parts.append(Input(value=value, placeholder=o.default, password=o.password, id=fid))
        if o.summary:
            parts.append(Static(o.summary, classes="sb-hint", markup=False))
        return Vertical(*parts, classes="cr-field")

    def _show_other(self, o: cloud.Option) -> None:
        other = self.query(f"#cr-x-{_id(o.name)}")
        if other:
            sel = self.query_one(f"#cr-v-{_id(o.name)}", Select)
            other.first().display = sel.value == OTHER

    def _read_fields(self) -> None:
        """The boxes into self.values (kept across a redraw)."""
        if self.backend is None or self._drawing:
            return
        for o in cloud.form_options(self.backend, self.values, self.advanced):
            found = self.query(f"#cr-v-{_id(o.name)}")
            if not found:
                continue
            w = found.first()
            if isinstance(w, Switch):
                self.values[o.name] = "true" if w.value else "false"
            elif isinstance(w, Select):
                v = w.value
                if v == OTHER:
                    v = self.query_one(f"#cr-x-{_id(o.name)}", Input).value
                self.values[o.name] = "" if v is Select.NULL or v is None else str(v)
            elif isinstance(w, Input):
                self.values[o.name] = w.value

    @on(Select.Changed)
    def _select_changed(self, event: Select.Changed) -> None:
        if self.backend is None or not (event.select.id or "").startswith("cr-v-"):
            return
        name = event.select.id[len("cr-v-"):]
        option = next((o for o in self.backend.options if _id(o.name) == name), None)
        if option is None:
            return
        self._show_other(option)
        if option.name == "provider" and not self._drawing:
            # S3: the provider decides which region and endpoint rows apply.
            before = self.values.get("provider", "")
            self._read_fields()
            if self.values.get("provider", "") != before:
                self._draw_fields()

    @on(Switch.Changed, "#cr-advanced")
    def _advanced(self, event: Switch.Changed) -> None:
        self._read_fields()
        self.advanced = event.value
        self._draw_fields()

    @on(Switch.Changed, "#cr-encrypt")
    def _encrypt(self, event: Switch.Changed) -> None:
        self.query_one("#cr-crypt-fields").display = event.value
        self.query_one("#cr-crypt-bucket-box").display = bool(
            self.backend and cloud.needs_bucket(self.backend.prefix))
        if event.value:
            self.query_one("#cr-pass", Input).focus()

    # --- the sign-in --------------------------------------------------------
    @on(Button.Pressed, "#cr-signin-go")
    def _sign_in(self) -> None:
        if self.backend is None:
            return
        from .oauth import OAuthScreen
        self._read_fields()
        extra = ()
        if self.values.get("client_id", "").strip() and self.values.get("client_secret", "").strip():
            extra = (self.values["client_id"].strip(), self.values["client_secret"].strip())
        maker = cloud.DemoAuthorizer if self.app.env.demo else cloud.Authorizer
        auth = maker(self.backend.prefix, extra=extra)

        def signed(token: str | None) -> None:
            if token:
                self.token = token
                self._problem("")
            self._signin_state()

        label = t(self.backend.label)
        self.app.push_screen(OAuthScreen(t("Sign in to ${service}", service=label), label, auth), signed)

    # --- the end ------------------------------------------------------------
    def _problem(self, text: str) -> None:
        label = self.query_one("#cr-problem", Label)
        label.update(text)
        label.display = bool(text)

    def collect(self) -> tuple[dict | None, str]:
        """The answers, or why they cannot be saved yet."""
        if self.backend is None:
            return None, t("Choose a service on the left.")
        self._read_fields()
        name = self.query_one("#cr-name", Input).value.strip()
        if not self.editing:
            problem = cloud.name_problem(name, self.taken)
            if problem:
                return None, t(problem)
        keep = self.secrets if self.editing else set()
        lacking = cloud.missing(self.backend, self.values, keep)
        if lacking:
            return None, t("Fill in: ${fields}", fields=", ".join(o.label for o in lacking))
        if self.backend.oauth and not self.token and not (self.editing and "token" in self.secrets) \
                and any(o.name == "token" for o in self.backend.options) and "service_account_file" not in {
                    k for k, v in self.values.items() if v.strip()}:
            return None, t("Sign in first: press the green button.")
        values = cloud.answers(self.backend, self.values, self.advanced)
        if self.token:
            values["token"] = self.token
        crypt, crypt_dir = "", ""
        if self.query_one("#cr-encrypt", Switch).value:
            crypt = self.query_one("#cr-pass", Input).value
            problem = cloud.password_problem(crypt, self.query_one("#cr-pass2", Input).value)
            if problem:
                return None, t(problem)
            if cloud.needs_bucket(self.backend.prefix):
                crypt_dir = cloud.clean_base(self.query_one("#cr-crypt-bucket", Input).value)
                if not crypt_dir or cloud.base_problem(crypt_dir):
                    return None, t("Type the bucket that holds the encrypted backups.")
        return {"name": name, "prefix": self.backend.prefix, "label": self.backend.label,
                "mode": "update" if self.editing else "create", "values": values, "crypt": crypt,
                "crypt_dir": crypt_dir}, ""

    @on(Button.Pressed, "#cr-save")
    def _save(self) -> None:
        answers, problem = self.collect()
        self._problem(problem)
        if answers is not None:
            self.dismiss(answers)

    @on(Button.Pressed, "#cr-cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)
