"""AddressesView: "Addresses and access" of a system (study 17.4).

The configured address first (the only one with "use this", Open and
Copy), each with where it was checked from and when; the alternatives the
server also answers at, with the effect to expect; the internet. Nothing
is called working without a test: "Test access" opens each address from
this server (read only). Changing the address is the system's own routine,
with its plan and its question. The cards of before stay below.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label

from .. import addresses
from ..i18n import t
from ..tasks import TaskResult
from ..widgets.cards import LinkCard, StatusCard
from .base import SectionView

# The routines behind the buttons, by system: Tainacan's and DSpace's own
# address routine changes the address and publishes it (a domain, HTTPS,
# the free address); Koha is published through the Cloudflare tunnel, which
# also sets its OPACBaseURL and staffClientBaseURL. Koha's own button
# chooses one port (names) or two (U10).
CHANGE = {"tainacan": "tainacan-address", "dspace": "dspace-address", "koha": "koha-access"}
PUBLISH = {"koha": "cloudflare"}


class AddressesView(SectionView):
    data: addresses.Addresses | None = None
    public: list[str] = []

    @property
    def platform(self) -> str:
        return self.section.group

    def compose(self) -> ComposeResult:
        yield from self.heading()
        yield Label(t("Configured address (use this)"), classes="view-prompt addr-head")
        yield Vertical(id="addr-configured")
        yield Label("", id="addr-windows", classes="addr-line", markup=False)
        yield Label(t("Other names of this server (may redirect or fail at login)"), classes="view-prompt addr-head")
        yield Vertical(id="addr-alternatives")
        with Horizontal(classes="addr-row"):
            yield Label(t("On the internet"), classes="addr-name")
            yield Label("…", id="addr-internet", classes="addr-value", markup=False)
            if self.platform in PUBLISH:
                yield Button(t("Publish…"), id="addr-publish", classes="small", compact=True)
        with Horizontal(classes="addr-buttons"):
            if self.platform in CHANGE and (self.platform != "koha" or self.app.bridge.has_task("koha-access")):
                label = t("One port or two…") if self.platform == "koha" else t("Change or publish the address…")
                yield Button(label, id="addr-change", classes="small")
            yield Button(t("Test access"), id="addr-test", classes="small")
        yield from self.cards()

    def on_mount(self) -> None:
        # Read as soon as it exists too: a Show event can be missed when the
        # view is mounted and made current in one step on a busy machine.
        self.refresh_data()

    def on_show(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        self.run_worker(self.read(), group="addresses", exclusive=True, exit_on_error=False)

    async def read(self, test: bool = False) -> None:
        app = self.app
        out = None
        if app.bridge.has_task("addresses"):
            try:
                if test:
                    from ..routines.common import run_task
                    result: TaskResult = await run_task(app, t("Test access"), "addresses", self.platform, "test")
                    out = result.value if result.ok else None
                else:
                    out = await app.bridge.task("addresses", self.platform)
            except Exception:  # noqa: BLE001 - the screen then says it could not read
                out = None
        data = addresses.parse(self.platform, out) if out is not None and getattr(out, "ok", True) else None
        if data is not None and not test and self.data is not None:
            # Tests made while the screen is open stay with their time.
            data.checks = {u: c for u, c in self.data.checks.items()
                           if u in {x for _k, x in data.configured + data.alternatives}}
        self.data = data
        self.public = []
        if self.platform == "koha":
            try:
                status = await app.bridge.status()
            except Exception:  # noqa: BLE001
                status = {}
            access = status.get("access") if isinstance(status, dict) else None
            if isinstance(access, dict):
                self.public = [f"https://{h}" for h in (access.get("public_opac"), access.get("public_staff"))
                               if isinstance(h, str) and h and "/" not in h]
        await self.draw()

    async def draw(self) -> None:
        data = self.data
        box = self.query_one("#addr-configured", Vertical)
        alts = self.query_one("#addr-alternatives", Vertical)
        await box.remove_children()
        await alts.remove_children()
        if data is None:
            await box.mount(Label(t("The addresses could not be read. Update this panel and try again."),
                                  classes="addr-line"))
            self.query_one("#addr-internet", Label).update("-")
            self.query_one("#addr-windows", Label).display = False
            return
        cards = []
        for kind, url in data.configured:
            line, state = addresses.check_text(data.checks.get(url))
            card = LinkCard(f"{t(addresses.KIND_NAMES[kind])} · {t('configured')}")
            cards.append((card, url, line, state))
        for kind in data.unset:
            cards.append((StatusCard(t(addresses.KIND_NAMES[kind]), t("Not set"), t(
                "${pref} is empty: Koha builds its links from the address the browser used.",
                pref=addresses.PREFERENCE[kind])), "", "", ""))
        if not cards:
            cards.append((StatusCard(t("Address"), t("Not set"), ""), "", "", ""))
        await box.mount(*[c for c, *_ in cards])
        for card, url, line, state in cards:
            if isinstance(card, LinkCard):
                card.set_url(url, line, state)
        windows = self.query_one("#addr-windows", Label)
        windows.display = data.host_platform == "wsl"
        line, state = addresses.windows_text(data)
        windows.update(line)
        windows.set_class(state == "ok", "addr-ok")
        windows.set_class(state == "bad", "addr-bad")
        rows = []
        for kind, url in data.alternatives:
            effect = addresses.alternative_text(self.platform, url, data.configured, data.checks.get(url))
            name = f"{t(addresses.KIND_NAMES[kind])}: " if self.platform == "koha" else ""
            rows.append(Label(f"{name}{url}   {effect}", classes="addr-line", markup=False))
        if not rows:
            rows.append(Label(t("None found."), classes="addr-line"))
        await alts.mount(*rows)
        self.query_one("#addr-internet", Label).update(addresses.internet_text(self.platform, data, self.public))

    @on(LinkCard.Pressed)
    def _link(self, event: LinkCard.Pressed) -> None:
        event.stop()
        if event.copy:
            self.app.copy_to_clipboard(event.url)
        else:
            self.app.open_url(event.url)

    @on(Button.Pressed, "#addr-test, #addr-change, #addr-publish")
    def _pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "addr-test":
            self.run_worker(self.read(test=True), group="addresses", exclusive=True, exit_on_error=False)
        elif event.button.id == "addr-change":
            self.app.run_native(CHANGE[self.platform], after=self.refresh_data)
        else:
            self.app.run_native(PUBLISH[self.platform], after=self.refresh_data)
