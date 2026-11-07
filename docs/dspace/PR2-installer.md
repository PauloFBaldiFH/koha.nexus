# PR 2 — ciclo de instalação isolado do DSpace

Base: main `9de999b`, após #347. Versão do painel: 1.5.181.
Estado: experimental, em validação. Não habilita DSpace como disponível no painel.

## O que foi implementado

Adaptador Python 3.9+ em `platforms/dspace/runtime.py`, com ponte pequena no
instalador Bash. A ponte verifica SHA-256 de **cada** arquivo antes de executar,
tanto no checkout quanto no download usado pelo `config.sh` independente. O hash
esperado está dentro do instalador; não vem de um arquivo baixado ao lado do código.
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
Compose, colisões, memória disponível, espaço de staging, porta e proxy. Endereço
explícito nesta etapa: não adivinha uma interface nem seleciona a VPN. Apenas amd64.
O perfil de laboratório reserva limites de 2 GiB para backend, 1 GiB para Solr,
1,5 GiB para UI e 1 GiB para PostgreSQL. O gate de 4 GiB disponíveis/8 GiB de disco
livre é conservador para testes e **não** é dimensionamento garantido de um acervo.

O projeto `kn-dspace` tem quatro serviços e rede própria. Reutiliza
`kei_docker_network_create`, isolamento, auditoria, registro `owned.tsv`, módulos,
firewall e aplicação segura de site do Apache. PostgreSQL e Solr não publicam
portas; backend e UI escutam apenas em loopback (18101/18100). O proxy encaminha
`/server` antes de `/`. Não altera vhosts do Koha ou Tainacan. As bases, frontend,
backend e Solr ficam fixados por digest/identidade imutável.

Dados persistentes: PostgreSQL, todos os cores Solr, assetstore e diretórios
graváveis do backend. Configuração privada e senha aleatória ficam no diretório
700 da plataforma; configuração 640 para UID/GID do backend e senha 600. Senha não
entra em argumentos, Compose, catálogo, status ou diagnóstico. E-mail e cadastro
público ficam desligados. A criação do primeiro administrador pertence ao PR 3;
este PR não cria conta padrão nem publica dados de teste em produção.

Diário atômico, fsync e trava por plataforma registram as fases. Uma falha mantém
dados; retomar depois da API falhar não repete migração nem troca a senha.
Migração interrompida/falha requer investigação e `install --retry-migration
--confirm` explícito. Início normal nunca migra. Arquivos editados não são
sobrescritos silenciosamente. `stop` é gracioso e preserva volumes e configuração.
Não existe tarefa de remoção/destruição nesta etapa.

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

Nesta etapa, o Apache precisa existir; não é instalado implicitamente. O painel
já tem instalação de infraestrutura compartilhada. URL HTTPS requer proxy TLS
externo configurado; o assistente de domínio/túnel vem no PR 6.

Com proxy externo, os serviços locais são preparados, mas o administrador ainda
deve configurar duas rotas, preservar Host/esquema e não cachear respostas privadas:

| Rota | Destino |
|---|---|
| `/server` e subcaminhos | `http://127.0.0.1:18101/server` |
| `/` | `http://127.0.0.1:18100/` |

Bloquear endpoints operacionais `/server/actuator` e `/server/config` externamente.
Não bloquear `/server/api`: a interface pública precisa dela. Não anunciar HTTPS
ou URL pública funcionando só porque o processo Node iniciou.

## Validação e limites

* 20 testes locais de falha, retomada, identidade das imagens, privacidade de
  configuração e preservação de dados passaram. São testes com doubles declarados.
* Os 18 testes da fundação continuam passando localmente.
* `tools/dspace_install_test.py --disposable` prepara um conjunto **real** na CI,
  usando exatamente as imagens construídas pelos jobs de backend, UI e Solr.
  Confere migração, sete cores, API, SSR, proxy, persistência, parada/início e
  reinício do serviço Docker. Não chamar isso de reboot da máquina.
* Resultado da execução integrada ainda pendente ao escrever este documento.

Permanecem para etapas seguintes: administrador/depósito real e painel (PR 3),
backup/restauração PostgreSQL+arquivos+Solr (PR 4), conjuntos/agendas (PR 5),
domínios/túnel/atualização (PR 6). Ainda não homologados aqui: Debian 12/13 com o
conjunto DSpace, reboot real, coexistência com Koha e Tainacan reais, WSL, ARM,
acervo grande, operação prolongada e download público do catálogo promovido.
Não existe homologação de produção ou validação no servidor do Paulo.
