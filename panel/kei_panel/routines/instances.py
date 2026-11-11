"""Explicit creation/removal entry points using the installed application drivers."""
from ..i18n import t
from ..screens.dialogs import ChoiceScreen, MessageScreen

NAMES = {'koha': 'Koha', 'tainacan': 'Tainacan', 'dspace': 'DSpace'}


async def add(app):
    available = [key for key in NAMES if not app.platform_ready(key)]
    if not available:
        await app.push_screen_wait(MessageScreen(t('Add instance'), t(
            'All currently supported application slots are installed. Additional instances of the same application require the instance drivers; existing data will not be overwritten.')))
        return
    selected = await app.push_screen_wait(ChoiceScreen(t('Add instance'), t('Choose the application to install.'),
                                                       [(key, NAMES[key]) for key in available]))
    if selected not in available:
        return
    from . import ROUTINES
    await ROUTINES[{'koha': 'install', 'tainacan': 'tainacan-install', 'dspace': 'dspace-install'}[selected]](app)


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
