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


async def remove(app):
    # Native Koha removal is not a package uninstall. Its dedicated driver
    # must be implemented before offering destructive server-wide operations.
    available = [key for key in ('tainacan', 'dspace') if app.platform_ready(key)]
    if not available:
        await app.push_screen_wait(MessageScreen(t('Remove instance'), t(
            'No removable container installation was detected. Open the application diagnosis if its state cannot be read.')))
        return
    selected = await app.push_screen_wait(ChoiceScreen(t('Remove instance'), t('Choose the installation. Its removal plan is shown before any change.'),
                                                       [(key, NAMES[key]) for key in available]))
    if selected not in available:
        return
    from . import ROUTINES
    await ROUTINES[{'tainacan': 'tainacan-uninstall', 'dspace': 'dspace-remove'}[selected]](app)
