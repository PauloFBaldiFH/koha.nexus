"""Reproduz a medição da Central de backups citada no estudo (modo demonstração).

Executar a partir da raiz do repositório, com o venv do painel (textual 8.x):

    python3 docs/estudo-usabilidade/medir_backups.py

Para cada filtro, mostra quantos cartões de ação estavam visíveis antes de a
leitura terminar, quantos depois, a linha (dentro da tela rolável) onde o
primeiro cartão aparece, a altura total do conteúdo e o tempo de leitura.
Nada é executado no servidor: o modo demonstração simula o instalador.
"""
import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "panel"))
for name in ("KOHA", "TAINACAN", "DSPACE"):
    os.environ["KEI_PANEL_DEMO_" + name] = "1"

from kei_panel.env import PanelEnv  # noqa: E402
from kei_panel.i18n import Translator, install  # noqa: E402

INSTALLER = ROOT / "installer"
install(Translator("pt", INSTALLER, False))

from kei_panel.app import KohaPanelApp  # noqa: E402
from kei_panel.views.backups import BackupCenterView  # noqa: E402
from kei_panel.widgets.cards import ActionCard  # noqa: E402


async def main(size):
    app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="pt", plain=False, demo=True))
    async with app.run_test(size=size) as pilot:
        await pilot.pause(2)
        for scope in ("koha", "tainacan", "dspace", "both", "nexus"):
            app.backup_scope = scope
            app.screen.action_show("backups")
            await pilot.pause(0.2)
            view = app.screen.query_one(BackupCenterView)
            view.set_scope(scope)
            start = time.monotonic()
            await pilot.pause(0.05)
            before = [c for c in view.query(ActionCard) if c.display]
            for _ in range(100):
                await pilot.pause(0.1)
                if not view.query_one("#platform-loader").display:
                    break
            seconds = time.monotonic() - start
            await pilot.pause(0.3)
            cards = [c for c in view.query(ActionCard) if c.display]
            rows = [c.region.y - view.region.y + int(view.scroll_y) for c in cards]
            print(f"{size[0]}x{size[1]} {view.scope:<9} antes={len(before):>2} depois={len(cards):>2} "
                  f"primeiro_cartao_linha={min(rows) if rows else '-':>3} altura={view.virtual_size.height:>3} "
                  f"leitura={seconds:.1f}s")


for terminal in ((80, 24), (160, 48)):
    asyncio.run(main(terminal))
