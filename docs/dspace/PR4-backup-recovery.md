# PR4 — backup individual e recuperação do DSpace

Base: PR3 (#353) mesclado. Aceite integrado aprovado na CI em `20e3082`; ajustes finais em nova validação.

O formato DSpace 1 é separado do formato 2 do motor Tainacan: usa dump custom do
PostgreSQL e cópia fria de todos os volumes de arquivos e Solr. O pacote inteiro
é cifrado com a chave GPG já configurada no Nexus; exige a frase de recuperação
para abrir. Não amplia agendas nem conjuntos Koha/Tainacan (PR5).

A trava é a mesma do ciclo de serviços (`backup/dspace.lock`). A captura lembra
os serviços ativos, para UI/backend/Solr, faz o dump lógico, para PostgreSQL e
copia os arquivos com UID/GID preservados. Sessões podem exigir novo login após a manutenção. Retoma os serviços anteriores mesmo
em erro tratável. O diário só registra retomada após sucesso. Uma captura
interrompida exige retomar os serviços registrados antes da próxima operação.
O pacote é publicado por rename somente após cifragem completa; staging privado
é removido ao sair. SIGKILL pode deixar staging privado para revisão.

Recuperação confere checksum externo quando presente, integridade GPG, formato, release,
matriz exata de imagens, inventário com hashes, nomes/tipos de arquivos, limites
de decifragem e extração e todos os volumes. Não executa Compose vindo do pacote. O Compose
é gerado da configuração confiável. Links, dispositivos, caminhos relativos
ambíguos e entradas repetidas são recusados antes da extração.

O teste usa volumes vazios independentes. PostgreSQL tem `network_mode: none`;
Solr e backend compartilham somente esse loopback, sem bridge, saída, DNS externo
ou portas publicadas. SMTP fica desativado. O banco é importado com pg_restore;
todos os dados lógicos são comparados ao fingerprint capturado, os arquivos e
todos os cores Solr são comparados por hash, e o guard de esquema/administração
oficial e o carregamento dos cores são exercitados.

Restauração ativa: confirmação, backup de segurança cifrado, clone verificado,
parada do projeto, troca dos volumes referenciados e validação dos serviços.
Todos os volumes anteriores são preservados. Volumes candidatos também são
preservados assim que podem receber escritas de produção, mesmo após rollback. A configuração anterior fica em
`recovery-rollback`; falha tratável tenta voltar. Interrupção na promoção mantém
o diário e bloqueia início normal. A tarefa `backup-rollback --confirm` recoloca
a configuração anterior sem apagar volumes. URLs diferentes exigem migração
separada. Um host vazio precisa preparar a mesma release antes da recuperação.

Tarefas, sob `config.sh --task dspace-panel`:
- `backup-create --confirm`
- `backup-list`
- `backup-plan PACOTE` (decifra e valida em staging privado; não altera serviços)
- `backup-test PACOTE --confirm`
- `backup-restore PACOTE --confirm`
- `backup-rollback --confirm`

A frase entra por `KEI_BACKUP_PHRASE`, retirada do ambiente antes de chamar
Docker e transmitida somente ao serviço de criptografia. Ela não é gravada em
argumentos, resultado ou arquivo do Nexus. Guarde o kit existente fora do host.

O painel oferece DSpace individual na Central de backups e atalhos no grupo
DSpace. Agendas/conjuntos ficam para PR5. Domínios/atualizações ficam para PR6.

## Validação

- 91 testes unitários de imagens/runtime/formato aprovados localmente em Python
  3.12; incluem caminho inseguro, links, duplicatas, expansão e corrupção.
- Os 88 testes locais selecionados do painel, menus, manual e traduções passaram.
  Cancelamentos, frase mascarada, plano de restauração e layouts 80×24/160×48 foram exercitados. Serviços reais: aceite integrado aprovado em `20e3082` (execução
  [42422331580](https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42422331580)),
  incluindo restauração pública e privada e histórico Solr não vazio. Ajustes
  finais de preservação de candidatos e metadados exigem nova execução.
  Nada foi testado no servidor
  de Paulo. Não anunciar recuperação homologada antes da CI real.
- CI acrescenta captura pública e privada, restauração em volumes novos,
  download público com SHA-256, recusa anônima do privado e download autorizado.
- Reboot completo, Debian/WSL/ARM, acervo grande, destinos externos e integração
  em conjuntos não estão comprovados nesta etapa.

A restauração ativa exige um destino com banco legível para o backup de segurança.
Para perda/corrupção do banco atual, preparar outra instalação da mesma matriz
antes de recuperar. Volumes promovidos mantêm o prefixo de recuperação: não
apagá-los pelo nome; o Compose ativo registra quais estão em uso.

## Uso e recuperação operacional

Na Central de backups, selecionar DSpace. Configurar a chave pelo fluxo existente
do Nexus e guardar seu kit fora do servidor antes da primeira captura. Criar o
backup suspende temporariamente o repositório; depois de retomar, o painel mostra
o caminho do pacote. Sessões do DSpace podem exigir novo login após essa parada.

Os pacotes ficam em `/var/backups/koha-nexus/dspace/knx-dspace-*.tar.gpg`. Copiar o
arquivo cifrado para outro armazenamento é possível sem exportar plaintext.
O `.sha256` ao lado é uma verificação adicional transportável, não substitui a
integridade GPG nem o inventário interno. O kit/frase não devem ser guardados
junto dos pacotes. Não há envio ou retenção automáticos do DSpace nesta etapa.

Antes de uma restauração efetiva, usar **Testar recuperação**: o teste usa novos
volumes e não substitui os dados ativos. Para transportar o pacote a outra
instalação, preparar a mesma matriz e o mesmo endereço canônico e disponibilizar
a chave/frase de recuperação do Nexus. Manter o nome do pacote e permissões
restritas ao colocá-lo no diretório de backups; o seletor do painel lista arquivos
locais, não faz upload de um backup remoto.

**Restaurar** primeiro valida e mostra o plano. Depois da confirmação faz uma
cópia de segurança cifrada, verifica a cópia restaurada e promove os volumes.
Uma falha tenta retornar à configuração anterior. Se a operação for interrompida
ou o retorno falhar, preservar `backup-operation.json`, `recovery-rollback` e os
volumes; consultar diagnóstico antes de usar `backup-rollback --confirm`.
Não apagar recursos pelo prefixo: volumes de recuperação podem estar ativos.
