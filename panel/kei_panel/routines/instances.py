"""Explicit creation/removal entry points using the installed application drivers,
and the visible name of each installation (U6)."""
from .. import names
from ..i18n import t
from ..screens.dialogs import ChoiceScreen, MessageScreen

NAMES = names.SYSTEMS


# "Add system" (study 7.2): every system, the installed ones too, since
# each is installed once per server. An installed one opens its page; a
# missing one shows what it is and what it needs before "Install…".
ABOUT = {
    'koha': ('📚', 'Koha · library catalogue', 'Loans, patrons, the catalogue and the public catalogue (OPAC).',
             'Installs Koha on this server, with its database, search and web server. The installation shows '
             'its stages; Tainacan and DSpace are not changed.',
             'Debian or Ubuntu · memory: at least 4 GB on a server (8 GB recommended), 8 GB on a desktop or WSL.'),
    'tainacan': ('🏺', 'Tainacan · collections and museums', 'Digital collections with WordPress.',
                 'Runs in containers; Docker is installed with your consent if missing. Koha and DSpace are not '
                 'changed.',
                 'Docker · 768 MB of free memory · 3 GB of free disk.'),
    'dspace': ('🏛', 'DSpace · institutional repository',
               'Theses, articles and research output, with access rules per document.',
               'The first time, prepares the DSpace programs on this server (30 to 90 minutes); then creates an '
               'empty repository with its own address. Koha and Tainacan are not changed.',
               'amd64 processor · Debian or Ubuntu · Docker (installed with your consent) · 4 GB of free memory '
               '· 8 GB of free disk.'),
}
INSTALL = {'koha': 'install', 'tainacan': 'tainacan-install', 'dspace': 'dspace-install'}


def add_options(app) -> list[tuple[str, str]]:
    rows = []
    for key, (icon, name, _what, _happens, _needs) in ABOUT.items():
        name = names.custom(names.of(app), key)
        state = (t('Installed: ${name} · open', name=name) if name else t('Installed · open')) \
            if app.platform_ready(key) else t('Not installed')
        rows.append((key, f'{icon} {t(name)} — {state}'))
    return rows


async def add(app):
    from ..screens.install_flow import PlanSummaryScreen
    selected = await app.push_screen_wait(ChoiceScreen(t('Add system'), t(
        'Each system can be installed once on this server. Choose one to see what it does and what it needs.'),
        add_options(app)))
    if selected not in ABOUT:
        return
    if app.platform_ready(selected):
        # Never a second installation over existing data: its page opens.
        show = getattr(app.screen, 'action_show', None)
        if show:
            show(selected)
        return
    icon, name, what, happens, needs = ABOUT[selected]
    if not await app.push_screen_wait(PlanSummaryScreen(
            f'{icon} {t(name)}', [(t('What it is'), t(what)), (t('When installing'), t(happens)),
                                  (t('Requirements'), t(needs))],
            body=t('Nothing is changed here. Install… starts the installation, which shows its own checks and questions first.'),
            action=t('Install…'))):
        return
    from . import ROUTINES
    await ROUTINES[INSTALL[selected]](app)


KOHA_REMOVAL = ("Koha: removal is not available in the panel yet. It will be its own step, with a verified safety "
                "backup and the data kept for recovery. Nothing of Koha is changed here.")


async def remove(app):
    # Koha's removal is its own step (U11, routines/koha_remove.py): a
    # verified package first, the packages and the other systems stay. An
    # installer older than that step keeps saying it is not available.
    bridge = getattr(app, 'bridge', None)
    koha_step = app.platform_ready('koha') and bridge is not None and bridge.has_task('koha-remove')
    available = (['koha'] if koha_step else []) + [key for key in ('tainacan', 'dspace') if app.platform_ready(key)]
    # Said, never just left out (study 17.3).
    koha = t(KOHA_REMOVAL) if app.platform_ready('koha') and not koha_step else ''
    if not available:
        await app.push_screen_wait(MessageScreen(t('Remove instance'), '\n\n'.join(filter(None, (t(
            'No removable container installation was detected. Open the application diagnosis if its state cannot be read.'), koha)))))
        return
    selected = await app.push_screen_wait(ChoiceScreen(t('Remove instance'), '\n\n'.join(filter(None, (
        t('Choose the installation. Its removal plan is shown before any change.'), koha))),
                                                       [(key, names.label(names.of(app), key)) for key in available]))
    if selected not in available:
        return
    from . import ROUTINES
    await ROUTINES[{'koha': 'koha-remove', 'tainacan': 'tainacan-uninstall', 'dspace': 'dspace-remove'}[selected]](app)


# "Name the installations" (study 12, U6). The name lives only in the
# instance registry: nothing is reinstalled, moved or renamed. Opening this
# only reads; a name is written after OK, one system at a time.
NAMING = "Name the installations"


def systems_of(out) -> list[tuple[str, str, str]]:
    """(system, "named" | "proposed", name) from `--task instance-names`."""
    rows = []
    for row in (out.lists.get("system") or ([out.get("system")] if out.get("system") else [])) if out else []:
        key, _, rest = row.partition("|")
        state, _, name = rest.partition("|")
        if key in NAMES and state in ("named", "proposed") and names.valid(name) and key not in [r[0] for r in rows]:
            rows.append((key, state, names.valid(name)))
    return rows


def choice_text(key: str, state: str, name: str) -> str:
    if state == "named" and name != NAMES[key]:
        return f"{name} · {NAMES[key]}"
    return f"{NAMES[key]} — " + t("no name yet")


def check_name(value: str) -> str:
    return "" if names.valid(value) else t("Use 1 to 120 letters, numbers or signs, without line breaks.")


async def name_instances(app, only: str = "") -> None:
    from .common import run_task, show_failure, failed
    from ..screens.dialogs import InputScreen
    title = t(NAMING)
    bridge = app.bridge
    if not bridge.has_task("instance-names"):
        await app.push_screen_wait(MessageScreen(title, t(
            "This server's installer is older than the panel: update it (Update panel) to name the installations.")))
        return
    try:
        out = await bridge.task("instance-names")
    except Exception:  # noqa: BLE001 - said below
        out = None
    rows = [r for r in systems_of(out) if app.platform_ready(r[0]) and (not only or r[0] == only)]
    if not rows:
        problem = out.get("registry") if out else ""
        await app.push_screen_wait(MessageScreen(title, "\n\n".join(filter(None, (t(
            "No installed system was found to name.") if out else t("The names could not be read."), problem)))))
        return
    key = rows[0][0]
    if len(rows) > 1:
        key = await app.push_screen_wait(ChoiceScreen(title, t(
            "The name is shown in this panel: in the sidebar, the tabs, backups, schedules and confirmations. "
            "Only the name changes: databases, files, services and addresses stay as they are."),
            [(k, choice_text(k, state, name)) for k, state, name in rows]))
        if key not in NAMES:
            return
    _k, state, current = next(r for r in rows if r[0] == key)
    value = await app.push_screen_wait(InputScreen(
        f"{title} · {NAMES[key]}", t(
            "A name for this ${system}, such as the institution's or the collection's. Only the name changes: "
            "its database, files, services and addresses stay as they are.", system=NAMES[key]),
        # Not named yet: the system's name is proposed (study 12), never the
        # Koha site's internal name ("library").
        t("Name:"), validate=check_name, value=current if state == "named" else NAMES[key]))
    name = names.valid(value)
    if not name or (state == "named" and name == current):
        return
    result = await run_task(app, title, "instance-name", key, name)
    if failed(result):
        await show_failure(app, title, result)
        return
    saved = dict(names.of(app))
    for k, st, n in systems_of(result.value):
        if st == "named":
            saved[k] = n
    # Shown at once; the next status read confirms it.
    app.names_seen({"names": saved})
    app.notify(t("Name saved: ${name}", name=names.label(saved, key)), timeout=5)
