# Testes de desenvolvimento

Execute apenas em WordPress descartável. integration.php cria usuários, eventos, coleções e reservas. dependency.py desativa e move a dependência para testar a preparação dos arquivos incluídos. Nunca execute esses arquivos em um site real.

Ambiente usado:
- Contêiner WordPress: nexus-events-wp, publicado em 127.0.0.1:18791.
- WordPress 6.8.3, PHP 8.3, MariaDB 11.4.
- WP-CLI disponível em /tmp/wp-cli.phar dentro do contêiner.
- Events Manager fornecido e Tainacan 1.4.1 com dependências e ativos compilados.
- Conta administrativa inicial com ID 1, em site vazio.
- Nenhum envio real de e-mail nos testes de integração: pre_wp_mail interceptado.
- Chromium local, Playwright, Pillow e zxing-cpp para testes no navegador e leitura do QR.

Pré-requisitos para repetir:
1. Prepare um site vazio isolado, com nomes e porta acima. Use senhas de teste geradas localmente.
2. Instale a base, conclua sua configuração inicial e ative Tainacan e Nexus Eventos.
3. Copie integration.php para /tmp/integration.php no contêiner.
4. Execute:

    docker exec -e NXEV_TEST_RUN=disposable nexus-events-wp php /tmp/wp-cli.phar --allow-root eval-file /tmp/integration.php
    docker cp nexus-events-wp:/tmp/nxev-fixtures.json /tmp/nxev-fixtures.json
    python development/tests/browser.py /tmp/nxev-fixtures.json /tmp/nxev-browser-output
    NXEV_TEST_RUN=disposable python development/tests/dependency.py /tmp/nxev-fixtures.json

O JSON temporário contém cookies administrativos de teste e links de passe. Não o publique, não o versione e apague-o depois de encerrar o ambiente. Gere um novo fixture antes de repetir browser.py, pois o teste desfaz uma presença e revoga seu documento.

A presença de NXEV_TEST_RUN não transforma um site em descartável: quem executa continua responsável por escolher o ambiente correto. Os arquivos não devem ser copiados para uma instalação de produção.

Para lint PHP, execute php -l em todos os arquivos PHP do plugin. O POT foi gerado com wp i18n make-pot, domínio nexus-eventos, excluindo assets/vendor e bundled.

Os testes cobrem os caminhos descritos em VALIDACAO.md. Não substituem teste de carga, revisão independente ou homologação do tema utilizado pela instituição.
