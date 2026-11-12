import asyncio
from types import SimpleNamespace

import pytest

from kei_panel.routines import ROUTINES, instances
from kei_panel.screens.dialogs import ChoiceScreen


@pytest.mark.parametrize('application', ['koha', 'tainacan', 'dspace'])
def test_add_routes_only_to_a_missing_application_driver(monkeypatch, application):
    calls=[]
    async def run(app): calls.append(application)
    monkeypatch.setitem(ROUTINES, {'koha':'install','tainacan':'tainacan-install','dspace':'dspace-install'}[application],run)
    shown=[]
    async def choose(screen):
        shown.append(type(screen).__name__)
        # U5: the list, then what the system is and needs, then Install…
        return application if isinstance(screen,ChoiceScreen) else True
    app=SimpleNamespace(platform_ready=lambda p:p!=application,push_screen_wait=choose)
    asyncio.run(instances.add(app))
    assert calls==[application] and shown==['ChoiceScreen','PlanSummaryScreen']


def test_add_never_reinstalls_an_existing_application(monkeypatch):
    async def forbidden(app): raise AssertionError('existing data must not be reinstalled')
    for action in ('install','tainacan-install','dspace-install'):monkeypatch.setitem(ROUTINES,action,forbidden)
    async def choose(screen):return 'koha' # an installed one opens its page, never a second installation
    opened=[]
    screen=SimpleNamespace(action_show=opened.append)
    asyncio.run(instances.add(SimpleNamespace(platform_ready=lambda p:p=='koha',push_screen_wait=choose,screen=screen)))
    assert opened==['koha']


def test_cancel_remove_does_not_call_a_driver(monkeypatch):
    async def forbidden(app):raise AssertionError('cancel must not mutate')
    for action in ('tainacan-uninstall','dspace-remove'):monkeypatch.setitem(ROUTINES,action,forbidden)
    async def cancel(screen):return None
    asyncio.run(instances.remove(SimpleNamespace(platform_ready=lambda p:True,push_screen_wait=cancel)))
