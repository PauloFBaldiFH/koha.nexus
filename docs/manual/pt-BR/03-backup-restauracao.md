# 3. Backup e restauração

[Índice do manual](README.md) · [Primeiros passos](02-painel.md)

## 3.1 Onde ficam as operações

Abra **Central de backups e restauração**, pela barra lateral ou pela tecla `b` na tela principal. A tela reúne os indicadores de último backup, tamanho e resultado, o seletor de compressão e os cartões das rotinas.

As ações existentes são:

| Cartão | Finalidade |
| --- | --- |
| Baixar Backup Recente | Copiar o arquivo mais recente encontrado para o computador, quando possível |
| Gerar backup manual e baixar no computador | Criar uma cópia do banco agora, verificar o arquivo e oferecer a transferência |
| Exportar registros MARC21 agora | Exportar registros bibliográficos e de autoridade |
| Restaurar base de dados | Substituir o banco atual pelo backup escolhido |
| Configurar backup na nuvem | Conectar o envio dos backups a um serviço externo |
| Testar a integridade do último backup | Fazer um teste de importação em banco temporário |

**Restaurar base de dados é um cartão dessa central.** Não procure um botão superior de restauração nem uma opção separada de restauração no menu principal do painel atual.

O resultado exibido no cartão de status se refere à última execução noturna, enquanto a data e o tamanho se referem ao backup mais recente encontrado. Essas informações podem não corresponder à mesma execução.

Fontes: seção `backup` de [menus.py](../../../panel/kei_panel/menus.py), [views/backup.py](../../../panel/kei_panel/views/backup.py) e [routines/backup.py](../../../panel/kei_panel/routines/backup.py).

## 3.2 Entender os tipos de cópia

**Backup SQL:** contém o banco de dados do Koha. É o arquivo usado para restaurar o banco pela central. Não é uma imagem completa do computador, do Windows ou de todo o sistema de arquivos do Debian.

**Exportação MARC21:** reúne registros bibliográficos e de autoridade em arquivos MARC, dentro de um pacote `.tar.gz`. Não substitui o backup SQL para recuperar o banco completo, inclusive leitores e circulação.

**Backup de segurança da restauração:** antes de substituir um banco que já tem tabelas, o fluxo cria e valida uma cópia do banco atual. Se o banco atual estiver vazio, a etapa pode ser dispensada porque não há tabelas a salvar.

As pastas padrão são:

- SQL automático e cópias de segurança: `/var/backups/koha_sql`.
- Pacotes MARC: `/var/backups/koha_marc`.

O backup manual tem destino próprio, escolhido na tela. O padrão é a subpasta `backups` da pasta do usuário identificado pelo painel. Não suponha que todo backup manual será gravado na pasta dos automáticos.

As gravações de segurança usam um arquivo temporário terminado em `.part` e só o promovem a arquivo final depois das verificações. Um `.part` não deve ser escolhido como backup concluído.

Fontes: `DIR_SQL`, `DIR_MARC`, `create_safety_backup` e `write_backup_scripts` no [instalador](../../../installer); [save_backup.py](../../../panel/kei_panel/save_backup.py); `manual_backup` e `marc_backup` em [routines/backup.py](../../../panel/kei_panel/routines/backup.py).

## 3.3 Escolher a compressão

No seletor **Compressão**, escolha o formato para novos backups:

| Formato | Descrição da tela |
| --- | --- |
| Gzip, `.sql.gz` | Compatibilidade ampla |
| Zstandard, `.sql.zst` | Rápido e menor, indicado na tela para catálogos grandes |
| XZ / LZMA, `.sql.xz` | Menor arquivo, com geração mais lenta |

A mudança é salva quando você escolhe o valor; não há um botão adicional de salvar nessa tela. Ela vale para novos backups noturnos, manuais e de segurança. Os arquivos já existentes não são recomprimidos por essa escolha.

Se o programa necessário não puder ser instalado, a tela informa a falha e os novos backups continuam com gzip. Leia também o aviso de formato efetivamente usado.

A restauração reconhece os arquivos SQL simples e os comprimidos suportados, independentemente da seleção atual. Neste roteiro, use `.sql`, `.sql.gz`, `.sql.zst` ou `.sql.xz`; a extensão sozinha não comprova que o conteúdo é válido.

Fontes: `CODECS`, `_set_codec` e `_show_codec` em [views/backup.py](../../../panel/kei_panel/views/backup.py); `backup_set_codec`, `dump_codec` e `restore_preflight` no [instalador](../../../installer).

## 3.4 Criar um backup manual

1. Abra **Gerar backup manual e baixar no computador**.
2. Confira o campo de pasta no servidor. Aceite a pasta proposta ou indique um destino apropriado e gravável.
3. Clique em **Salvar backup**.
4. Aguarde a geração e a verificação. A tela não fecha enquanto está salvando ou copiando.
5. Confira o nome, o tamanho e o caminho apresentados no resultado.
6. Faça a cópia para fora do servidor:
   - No WSL, use **Baixar na pasta Downloads** ou **Escolher pasta no Windows**.
   - Em acesso remoto, copie o comando de transferência apresentado e execute-o no terminal do seu próprio computador.
7. Confira se o arquivo chegou ao destino. Use **Concluir e sair** para fechar a tela.

Os botões de pasta Windows só são apresentados no ambiente WSL. Não copie um comando de exemplo de outra instalação: o painel monta o comando para o arquivo e o servidor que ele identificou.

Se o painel avisar que outro backup ou uma restauração já está em andamento, aguarde. O código usa uma trava compartilhada para impedir a sobreposição dessas operações; o aviso não deve ser contornado iniciando outra cópia concorrente por fora do painel.

Fontes: [screens/save_backup.py](../../../panel/kei_panel/screens/save_backup.py), [save_backup.py](../../../panel/kei_panel/save_backup.py), `function_manual_backup` e `backup_lock_acquire` no [instalador](../../../installer).

## 3.5 Baixar o backup mais recente

Abra **Baixar Backup Recente**. Em WSL ou em desktop Linux, o fluxo tenta copiar o arquivo para a pasta Downloads do computador correspondente. Por SSH (VPS ou servidor remoto), o painel abre uma página HTTPS temporária no servidor, na porta 8765: abra o endereço mostrado no navegador do seu computador e o backup é salvo na sua pasta Downloads. O navegador avisa sobre o certificado, que o servidor cria só para essa transferência; o painel mostra a impressão digital dele. Se o firewall do provedor mantiver a porta fechada, use o comando `ssh -L` mostrado na mesma tela. A página para quando a tela é fechada.

Para restaurar por SSH, escolha **No meu computador: enviar pelo navegador** (ou solte o arquivo no terminal): o arquivo vai pelo mesmo tipo de página, é conferido por tamanho e SHA-256, salvo em `~/backups/received` e só então restaurado.

Essa ação baixa um arquivo existente; ela não gera um backup novo. Se não houver arquivo encontrado, o painel avisa. Gere um backup manual quando precisar de uma cópia atual antes de uma operação.

Fonte: `download_latest` e `download_file` em [routines/backup.py](../../../panel/kei_panel/routines/backup.py).

## 3.6 Testar a integridade e a possibilidade de restauração

1. Abra **Testar a integridade do último backup**.
2. Confira o arquivo e a data propostos. Para outro arquivo, use **Escolher outro arquivo**.
3. Confirme a execução do teste apresentado.
4. Aguarde a importação em uma base temporária e as verificações.
5. Leia o resultado, que informa o arquivo e contagens de tabelas, registros bibliográficos e leitores quando o teste tem sucesso.

Esse fluxo testa sem substituir o banco de produção. Um teste aprovado se refere ao arquivo testado naquele ambiente; faça a transferência e mantenha acesso a esse mesmo arquivo para poder recuperá-lo depois.

Fonte: `test_backup` em [routines/backup.py](../../../panel/kei_panel/routines/backup.py) e rotina `function_test_backup` no [instalador](../../../installer).

## 3.7 Exportar MARC21

1. Abra **Exportar registros MARC21 agora**.
2. Leia a confirmação e autorize a exportação.
3. Aguarde o pacote com os registros bibliográficos e de autoridade.
4. Confira o caminho e o conteúdo informados na tela.
5. Use o download oferecido no ambiente local ou o comando mostrado para transferir o pacote.

O Koha continua em funcionamento durante a exportação. Quando o envio à nuvem está configurado, o resultado também informa se houve esse envio. Guarde o pacote MARC para intercâmbio de registros; mantenha o SQL para a recuperação completa do banco.

Fonte: `marc_backup` em [routines/backup.py](../../../panel/kei_panel/routines/backup.py) e `function_marc_backup` no [instalador](../../../installer).

## 3.8 Configurar uma cópia na nuvem

Abra **Configurar backup na nuvem**. O fluxo oferece duas formas expressas para Google Drive e um caminho para outros serviços, incluindo OneDrive, MEGA e S3.

1. Escolha o caminho adequado ao local onde o painel está aberto: há autorização no próprio servidor e um fluxo para concluir a autorização por outro computador.
2. Siga somente o endereço e as instruções que a tela dessa instalação apresentar.
3. Para outros provedores, escolha o serviço e preencha o nome da conexão e os campos solicitados. O fluxo S3 distingue o serviço, a região ou endereço do provedor e o bucket de destino.
4. Aguarde o teste de envio real e leia o resultado. Se houver falha, corrija a configuração antes de contar com essa cópia.
5. Confirme no destino escolhido que a cópia foi recebida.

Os dados privados necessários à autorização devem ser preenchidos apenas nos campos da própria instalação. Não os coloque no manual, em imagens públicas ou em mensagens de suporte. Este roteiro não publica valores nem caminhos de arquivos que armazenem esses dados.

O instalador cria por padrão um backup SQL diário às 23:00 e uma exportação MARC aos domingos às 03:00, no horário do servidor. Os agendamentos podem ser alterados pela área de cron; esses horários não são promessa sobre uma instalação já personalizada.

Fontes: `cloud_backup`, `cloud_provider`, `_provider_values` e `_cloud_result` em [routines/backup.py](../../../panel/kei_panel/routines/backup.py); `write_cron_tasks` no [instalador](../../../installer).

## 3.9 Restaurar o banco

**Ação destrutiva: a confirmação autoriza substituir o banco atual.** Combine uma janela de manutenção e mantenha uma cópia fora do servidor antes de começar. Essa é uma recomendação operacional; ela não é uma etapa adicional que o painel execute automaticamente em seu computador.

1. Abra **Restaurar base de dados** na central.
2. Escolha o backup que deve substituir o banco atual. Se o arquivo estiver no seu computador e o painel estiver em outro servidor, use a orientação de transferência da própria tela e depois selecione a cópia no servidor.
3. No Windows com WSL, um arquivo vindo do disco Windows pode ser copiado para uma área local do Linux antes da restauração.
4. Leia as verificações de leitura, conteúdo, integridade e espaço. Um aviso de arquivo suspeito ou possivelmente incompleto exige investigar a origem; não confirme apenas porque a extensão parece correta.
5. Confira novamente o arquivo na confirmação de substituição. Até essa confirmação, você pode desistir pela tela.
6. Depois de autorizar, aguarde sem fechar a janela. O fluxo de restauração é não cancelável no painel.

### O que o processo faz

Primeiro, o SQL é importado em uma base temporária. O código confere a quantidade de tabelas e a presença das tabelas essenciais do Koha. Se o teste falhar, ele encerra antes de substituir o catálogo atual.

Se o banco atual tem tabelas, é criado e validado um backup de segurança na pasta SQL. O nome começa com `pre_restore_safety_backup_`, seguido de data, horário e extensão de compressão. Se essa criação falhar, o fluxo não deve apagar o banco atual. Se o banco estiver vazio, o código pode dispensar essa cópia.

Depois, o processo para os clientes do banco do Koha, recria e importa o banco, atualiza seu esquema, sincroniza o mecanismo de busca, reconstrói os índices e reinicia os serviços. Há também uma tentativa de reaplicar a aparência salva do OPAC e da interface da equipe quando existe estado de tema salvo.

### Como interpretar uma falha

- **Falha no teste temporário:** o catálogo atual não foi substituído por essa etapa.
- **Falha ao gerar a cópia de segurança:** a operação é interrompida antes da substituição do banco com tabelas.
- **Falha na recriação, importação ou atualização do esquema:** conforme a etapa e a existência da cópia de segurança, o código tenta recuperar o banco anterior. Essa recuperação pode falhar; não é garantia de retorno automático em qualquer situação.
- **Falha na reconstrução do índice:** o banco pode já ter sido restaurado. Não conclua que o conteúdo anterior foi recuperado apenas por aparecer uma mensagem de erro.

Leia a mensagem completa e preserve os arquivos indicados. Os logs dessa operação são `/var/log/koha-easy-install/restore.log` e `/var/log/koha-easy-install/restore-import.log`. Para uma falha de indexação, o código também aponta `/var/log/koha-easy-install/zebra-rebuild.log`.

Não siga uma numeração antiga de menu para tentar recuperação. No painel atual, retorne ao cartão **Restaurar base de dados** da central para selecionar a cópia adequada, com apoio do responsável técnico se o estado do banco estiver incerto.

### Depois de concluir

Atualize o Painel de Controle, abra a interface da equipe e o catálogo e confira registros e buscas. Essas conferências são recomendações de operação. A conclusão da rotina não comprova, sozinha, a recuperação de arquivos externos ao banco SQL.

Fontes: `restore`, `_copy_in` e `_restore_file` em [routines/backup.py](../../../panel/kei_panel/routines/backup.py); `restore_preflight`, `_function_restore_database`, `create_safety_backup`, `restore_failed`, `restored_search_engine` e `restore_task_reindex` no [instalador](../../../installer).
