"""Explicit creation/removal entry points using the installed application drivers."""
from ..i18n import t
from ..screens.dialogs import ChoiceScreen, MessageScreen

NAMES = {'koha': 'Koha', 'tainacan': 'Tainacan', 'dspace': 'DSpace'}


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
        state = t('Installed · open') if app.platform_ready(key) else t('Not installed')
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
    # Native Koha removal is not a package uninstall. Its dedicated driver
    # must be implemented before offering destructive server-wide operations.
    available = [key for key in ('tainacan', 'dspace') if app.platform_ready(key)]
    # Said, never just left out (study 17.3): Koha removal is a later step.
    koha = t(KOHA_REMOVAL) if app.platform_ready('koha') else ''
    if not available:
        await app.push_screen_wait(MessageScreen(t('Remove instance'), '\n\n'.join(filter(None, (t(
            'No removable container installation was detected. Open the application diagnosis if its state cannot be read.'), koha)))))
        return
    selected = await app.push_screen_wait(ChoiceScreen(t('Remove instance'), '\n\n'.join(filter(None, (
        t('Choose the installation. Its removal plan is shown before any change.'), koha))),
                                                       [(key, NAMES[key]) for key in available]))
    if selected not in available:
        return
    from . import ROUTINES
    await ROUTINES[{'tainacan': 'tainacan-uninstall', 'dspace': 'dspace-remove'}[selected]](app)
