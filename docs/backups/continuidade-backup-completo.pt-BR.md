# Continuidade — backup completo do Nexus (1.5.194)

Branch: `feat/nexus-full-backup`, baseada na main após #364 (`8780842`).
O arquivo local preexistente `docs/plano-instancias.pt-BR.md` pertence à próxima
etapa e foi preservado fora desta alteração. Não mesclar automaticamente.

## Implementação

- Aba **Nexus completo** na Central de backups, inclusive antes de instalar
  aplicativos, para permitir abrir uma recuperação. Preferência persistente de
  compactação: gzip, bzip2, xz ou sem compactação; sempre criptografado.
- Pacote portátil `.nexus`: chave privada protegida pela frase, payload cifrado,
  dados/segredos dos sistemas instalados, imagens Docker por ID, configuração e
  referências privadas da infraestrutura. Manifesto/checksums, publicação atômica,
  espaço estimado e rejeição explícita de estado desconhecido/captura parcial.
- `--task nexus-full`: plan, create, identify, verify, open, restore-plan, restore,
  load-images, cleanup, settings e status. Adaptador fixado por SHA-256 e cache
  offline para instalações com apenas `config.sh`.
- Restauração usa os motores existentes. Exige destino preparado/compatível;
  não provisiona uma máquina vazia ou clona o sistema operacional. DSpace mantém
  as exigências de URL/receita/matriz. Outra chave primária não é sobrescrita.
- Sessão privada registra componentes concluídos e permite retomar após falha.
  Configurações estruturadas têm journal/rollback. Fonte de cron, túneis, contas
  cloud e programas arquivados ficam para revisão, sem execução automática.
  Novos planos são recuperados desativados; planos e cron existentes são mantidos.
- Correção encontrada no Debian real: caminho longo de GNUPGHOME impedia abrir
  os sockets do gpg-agent. Chaveiro temporário privado curto resolve isso; há teste.

Detalhes e comandos: [nexus-completo.pt-BR.md](nexus-completo.pt-BR.md).
Capturas **simuladas** do painel em 80×24 e 160×48: `capturas/nexus-completo-*.svg`.
As capturas não constituem testes de aplicações em servidor real.

## Verificação e comandos para continuidade

```bash
python3 -m unittest discover -s tests -p test_nexus_recovery.py -v
KEI_NEXUS_DOCKER_TESTS=1 python3 -m unittest discover -s tests -p test_nexus_docker.py -v
python3 export_docs_preview.py --check
python3 tools/dspace_build_bundle.py --check
bash -n installer
sha256sum -c installer.sha256
```

Validações locais: 23 testes do pacote/chaveiro com GnuPG real nos quatro codecs, frase errada,
kit desatualizado, corrupção, links, mudança de dados, cancelamento, concorrência,
retomada, rollback após interrupção e distribuição offline. Docker save/remove/load
com imagem descartável confirmou o ID após remover a original. O Debian descartável
validou o driver instalado fora do checkout e a recuperação das configurações após
remover o chaveiro ativo, **sem aplicativos instalados nessa rodada local**.

O teste real de importação de imagem passou (1 caso). Os 53 testes existentes dos motores de backup/conjuntos/agendas passaram no Debian.
Os testes de backup e operações do DSpace também passaram no Debian: 31 e 36 casos
(um skip de plataforma já existente). As telas e rotinas novas são cobertas pelo
painel, incluindo 80×24/160×48 e abertura só de leitura. O teste antigo de backup
manual em modo de demonstração foi isolado de `/root`, inacessível ao usuário de
desenvolvimento sem privilégios; a rotina de produção não foi alterada.

## CI e limites da evidência

A CI passou a executar o pacote com aplicações reais:

- `proxy / koha-set`: Koha + Tainacan, alteração de dados após a captura, perda do
  chaveiro ativo, importação do kit portátil, restauração e conferência dos dados,
  segredo de 2FA e arquivo enviado. Driver standalone e cache verificado.
- `DSpace image foundation / installation`: DSpace real, perda do chaveiro ativo,
  restauração do histórico Solr alterado, download privado autenticado e negação
  anônima. Recibo `nexus-full-dspace-acceptance.json` no artefato do job.
- Testes de envelope e Docker em Python 3.9 e 3.13; testes das rotinas do painel
  em `Platforms panel`. O job pesado também roda nesta branch `feat/nexus-*`.

O #365 foi mesclado. O job `proxy / koha-set` concluiu com os aplicativos reais.
O log da main também comprova a recuperação completa real do DSpace depois da
perda do chaveiro; a execução foi cancelada mais tarde, nas operações adicionais,
ao atingir o limite de 60 minutos. A suíte inteira ainda precisa terminar. A
correção divide esses testes em jobs obrigatórios independentes, com tempos por
fase: [dspace-validacao-tempo.pt-BR.md](dspace-validacao-tempo.pt-BR.md). Não há validação desta etapa no servidor de Paulo.
Não houve publicação de broker, alteração de produção ou merge automático.
