# PR 2 — ciclo de instalação isolado do DSpace

Base: main `9de999b`, após #347. Versão do painel: 1.5.181.
Estado: experimental, ciclo real validado na CI; ainda sem homologação de produção. Não habilita DSpace como disponível no painel.

## O que foi implementado

Adaptador Python 3.9+ em `platforms/dspace/runtime.py`, com ponte pequena no
instalador Bash. A ponte verifica SHA-256 de **cada** arquivo antes de executar,
tanto no checkout quanto no download usado pelo `config.sh` independente. O hash
esperado está dentro do instalador; não vem de um arquivo baixado ao lado do código.
A instalação confirmada guarda os arquivos verificados em cache privado local:
início, status e diagnóstico não dependem de download depois de instalados.
Não há dependência Python nova nem extração geral do instalador.

Comandos experimentais, locais, como root:

```sh
sudo config.sh --task dspace plan --url http://192.168.1.20:8100
sudo config.sh --task dspace install --url http://192.168.1.20:8100 --confirm
sudo config.sh --task dspace status
sudo config.sh --task dspace diagnose
sudo config.sh --task dspace stop --confirm
sudo config.sh --task dspace start --confirm
```

Antes de instalar, a prévia verifica catálogo de imagens, arquitetura, Docker e
Compose (rootful, sem remapeamento de usuários ainda não homologado), colisões, memória disponível, espaço de staging, porta e proxy. Endereço
explícito nesta etapa: não adivinha uma interface nem seleciona a VPN. Apenas amd64.
Endereços por IP/localhost exigem porta própria, diferente de 80/443 e das portas
privadas, para não substituir o site padrão já existente. Python e os helpers
Bash usam o mesmo socket Docker local, sem herdar contexto remoto do usuário.
O perfil de laboratório reserva limites de 2 GiB para backend, 1 GiB para Solr,
1,5 GiB para UI e 1 GiB para PostgreSQL. O gate de 4 GiB disponíveis/8 GiB de disco
livre é conservador para testes e **não** é dimensionamento garantido de um acervo.

O projeto `kn-dspace` tem quatro serviços e rede própria. Reutiliza
`kei_docker_network_create`, isolamento, auditoria, registro `owned.tsv`, módulos,
firewall e aplicação segura de site do Apache. PostgreSQL e Solr não publicam
portas; backend e UI escutam apenas em loopback (18101/18100). A UI tem identidade
IP própria na rede gerida, e o backend só confia nela e no gateway do proxy;
não resolve o domínio público para ampliar a lista de proxies confiáveis. Imagens imutáveis já presentes são verificadas sem novo acesso ao registro,
permitindo retomar a instalação sem rede. O proxy encaminha
`/server` antes de `/`. Não altera vhosts do Koha ou Tainacan. As bases, frontend,
backend e Solr ficam fixados por digest/identidade imutável.

Dados persistentes: PostgreSQL, todos os cores Solr, assetstore e diretórios
graváveis do backend. O volume `discovery-state` guarda o diretório legado de
sinalização de reindexação em `/dspace/solr/search/conf`; ele é separado do Solr real. Configuração privada e senha aleatória ficam no diretório
700 da plataforma; configuração 640 para UID/GID do backend e senha 600. Senha não
entra em argumentos, Compose, catálogo, status ou diagnóstico. E-mail e cadastro
público ficam desligados. A criação do primeiro administrador pertence ao PR 3;
este PR não cria conta padrão nem publica dados de teste em produção.

Diário atômico, fsync e trava por plataforma registram as fases. A trava é o mesmo
`backup/dspace.lock` do motor existente, recusando links e donos/permissões
não confiáveis, para a futura integração não abrir outro
domínio de concorrência. Comando administrativo ainda ativo no Docker após uma
desconexão impede uma operação conflitante, mesmo que o cliente tenha terminado.
Diretórios sem diário de propriedade, links ou arquivos de estado não confiáveis
são recusados sem adoção automática. Uma falha mantém
dados; retomar depois da API falhar não repete migração nem troca a senha.
Migração interrompida/falha requer investigação e `install --retry-migration
--confirm` explícito. Início normal não emite o comando de migração. Arquivos editados não são
sobrescritos silenciosamente. `stop` é gracioso e preserva volumes e configuração.
Não existe tarefa de remoção/destruição nesta etapa.

### Particularidade do upstream: migração na criação de Context

O `org.dspace.core.Context` chama `DatabaseUtils.updateDatabase()` ao iniciar.
Somente deixar de executar `database migrate` no entrypoint não impediria isso.
A receita **2** acrescenta `NexusSchemaGuard`, um programa JDBC pequeno, independente
do núcleo DSpace: lê a tabela `public.schema_version` usada por esta release
numa transação somente leitura e confere
um recibo do hash da release e das migrações bem-sucedidas. O recibo só é gravado
por `schema-record`, após a migração explicitamente autorizada. Sem recibo, com
release diferente ou histórico alterado, o backend recusa iniciar **antes** de
carregar o Context. Vale também no reinício automático do Docker.

O recibo fica em `/dspace/var/nexus-schema.sha256`, no volume persistente `var`.
Não substitui o backup do banco nem valida alterações manuais em todas as tabelas;
identifica a história de migração aprovada. Atualização/restauração futuras devem
preservar ou regenerar esse recibo somente após validar o banco de destino.

## Imagens: condição necessária antes de oferecer a instalação

O #347 construiu/testou imagens, mas não as publicou. Este PR mantém a instalação
**bloqueada** na ausência de catálogo revisado em
`/etc/koha-nexus/dspace-images.json`. Não compila DSpace na máquina do usuário e não
usa imagens de desenvolvimento como alternativa.

Foi acrescentada ao workflow `DSpace image foundation` uma publicação **manual**:
`workflow_dispatch`, na main, com `publish=true`. PR e push nunca publicam. Ela só
publica após build, auditoria de dependências, smoke e teste integrado aprovados.
O job com permissão `packages: write` recebe os arquivos das mesmas imagens já
testadas e publica em:

* `ghcr.io/paulofbaldifh/koha.nexus/dspace-backend`
* `ghcr.io/paulofbaldifh/koha.nexus/dspace-ui`
* `ghcr.io/paulofbaldifh/koha.nexus/dspace-solr`

O artefato `dspace-candidate-published-catalog` contém referências `@sha256:` e hash
do release lock. **Nada foi publicado por este trabalho.** Antes de promover o
catálogo, o mantenedor precisa revisar esses digests e tornar os pacotes públicos,
comprovar download sem login e instalar o catálogo como root, modo 600. O painel
não fica dependente da sessão GitHub do usuário. A promoção automática não faz
parte deste PR.

Na CI, `tools/dspace_catalog.py` gera IDs locais imutáveis dos builds. Somente a
opção explícita `--lab --catalog ARQUIVO` os aceita. Tags móveis são recusadas
também no laboratório. Não é uma forma de contornar a falta de imagens públicas
em instalação comum.

## Apache e proxy externo

Nesta etapa experimental por CLI, o Apache precisa estar instalado previamente
pelo administrador; não é instalado implicitamente. A instalação assistida dessa
dependência pertence à integração do PR 3. URL HTTPS requer proxy TLS
externo configurado; o assistente de domínio/túnel vem no PR 6.

Com proxy externo, o resultado e o estado ficam explicitamente marcados
`external-configuration-required`: serviços locais não equivalem a publicação.
O administrador ainda deve configurar duas rotas, preservar Host/esquema e não cachear respostas privadas:

| Rota | Destino |
|---|---|
| `/server` e subcaminhos | `http://127.0.0.1:18101/server` |
| `/` | `http://127.0.0.1:18100/` |

Bloquear endpoints operacionais `/server/actuator` e `/server/config` externamente.
Não bloquear `/server/api`: a interface pública precisa dela. Não anunciar HTTPS
ou URL pública funcionando só porque o processo Node iniciou.

## Validação e limites

* 36 testes locais de falha, retomada, identidade das imagens, privacidade de
  configuração e preservação de dados passaram. São testes com doubles declarados.
* Os 18 testes da fundação continuam passando localmente.
* Compilação Java 21 e seis verificações do guard passaram localmente: recibo
  estável, alteração de histórico, outra release, migração falha, banco vazio e
  identidade ausente. Estes testes também usam doubles JDBC declarados.
* Regressão local: 148 testes de plataformas/nexus_core passaram, um foi pulado.
* `tools/dspace_install_test.py --disposable` prepara um conjunto **real** na CI,
  usando exatamente as imagens construídas pelos jobs de backend, UI e Solr.
  Confere migração, sete cores, API, SSR, proxy, persistência, parada/início e
  reinício do serviço Docker. Também adultera o histórico Flyway num banco de
  laboratório para exigir recusa do backend sem alterações automáticas.
  Não chamar isso de reboot da máquina.
* A rodada real [42367863941](https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42367863941)
  passou por inteiro: instalação, API e interface pelo Apache, volumes de banco,
  assetstore e Solr preservados após recriar contêineres e após reiniciar o Docker,
  além da recusa por histórico de migração alterado. As imagens passaram smoke
  novamente mesmo restauradas do cache, e a auditoria de dependências passou.
* A integração encontrou e permitiu corrigir a montagem incompleta dos arquivos
  base pelo Ant: agora usa `install_code update_webapps`, sem operação no banco,
  e exige os arquivos essenciais no build e no smoke. O teste também foi alinhado
  ao contrato HAL upstream: relação `_links.communities` na raiz e paginação/link
  canônico na lista vazia, que pode omitir `_embedded`.
* As proteções finais de porta pública e de contexto Docker têm testes unitários;
  a rodada da revisão final deve ser conferida pelo commit antes da mesclagem.

Permanecem para etapas seguintes: administrador/depósito real e painel (PR 3),
backup/restauração PostgreSQL+arquivos+Solr (PR 4), conjuntos/agendas (PR 5),
domínios/túnel/atualização (PR 6). Ainda não homologados aqui: Debian 12/13 com o
conjunto DSpace, reboot real, coexistência com Koha e Tainacan reais, WSL, ARM,
acervo grande, operação prolongada e download público do catálogo promovido.
Não existe homologação de produção ou validação no servidor do Paulo.
