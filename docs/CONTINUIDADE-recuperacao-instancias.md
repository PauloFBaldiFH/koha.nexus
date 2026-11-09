# Recuperação e instâncias — continuidade

Atualizado em 09/11/2026. Primeiro conjunto mesclado no #359
(`feat/instance-recovery`, base `05aed5c`). Continuação de agendamentos na
branch `feat/schedule-controls`, base `9bac7c0`, versão 1.5.189.
Trabalho autorizado: plano de recuperação e instâncias inteiro, mais logs,
backups individuais com compactação, recuperação do Nexus completo, controles
editáveis das agendas, idiomas DSpace e criação/remoção pela lateral.

## Primeiro conjunto implementado

- Corrigida serialização DSpace que quebrava o status geral. Leitores completos
  no painel, núcleo e Windows, com compatibilidade ao payload antigo.
- Consulta do status com prazo e limpeza de subprocessos. CPU, memória e disco
  locais não dependem da consulta das aplicações. Falha aparece no Geral,
  preserva leitura anterior e permite tentar novamente.
- Diagnóstico/log/planejamento da remoção DSpace continuam alcançáveis com
  estado desconhecido; driver ainda valida o alvo antes de agir.
- Operação silenciosa mostra mensagem inicial, explicação no Log e aviso após
  dez segundos sem saída. Primeira saída real substitui a explicação. Payloads
  internos e segredos não são copiados ao log para preencher espaço.
- Instalar Koha/Tainacan/DSpace não abre automaticamente o assistente de
  publicação/nuvem. As rotinas continuam disponíveis nos menus.
- DSpace: compactação nenhuma/gzip/bzip2/xz antes da cifragem, configuração
  persistente para captura manual/agendada/de segurança, leitura automática de
  pacotes antigos e novos, seleção e estatísticas na central de backup.
- Lateral: Adicionar ou remover instância chama os drivers existentes, sem
  reinstalar aplicativos já presentes. Por enquanto permite a instalação única
  de cada sistema. Remoção disponível para os drivers Tainacan/DSpace; remoção
  nativa Koha ainda exige adaptação específica.
- Registro de instâncias (biblioteca do núcleo) com descoberta somente leitura,
  adoção explícita, UUID persistente, trava e escrita atômica. Ainda não ligado
  ao protocolo instalado nem usado para criar uma segunda instalação.

## Trabalho restante — não declarar concluído

1. Catálogo de idiomas DSpace baseado nas traduções realmente entregues;
   associação com idioma do painel; entrada no menu Idiomas. O helper Java
   ainda limita a três códigos. Mudá-lo exige nova receita e atualização
   compatível da receita 4 (preservar também a recuperação da receita 3).
2. Tela de agendas: implementada na branch `feat/schedule-controls`, versão
   1.5.189, após #359. Switch, frequência/horário compatíveis, confirmação,
   revisão concorrente e gravadores existentes. Detalhes e limites em
   `docs/schedules/PR-agendamentos.md`; verificar mesclagem e CI da etapa.
3. Tainacan: compactação configurável e painel individual completo. Adaptar
   formato e leitores, pois hoje esperam db.sql.gz/files.tar.gz fixos.
4. Recuperação completa Nexus: manifesto de todas as instâncias, configurações
   do painel e recursos compartilhados, segredos cifrados e imagens locais
   necessárias. Não rotular o conjunto atual de plataformas como imagem de
   disco/VM ou cópia integral da máquina.
5. Integrar registro/contexto ao instalador e distribuir módulos também fora
   do checkout. Migrar legado sem mover dados, portas ou URLs.
6. Propriedade, reservas de portas/redes/proxy, backups/agendas por ID;
   parametrização integral dos três drivers antes de criar segunda instância.
7. Navegação dinâmica por instância, remoção específica Koha, endereços e
   broker multi-instância. Não remover serviço compartilhado ao apagar um alvo.
8. Aceitação integrada com aplicação/navegador reais e reboot. O login em branco
   do servidor não foi reproduzido aqui. A main já continha o #358 que corrige
   acesso Windows/WSL à porta 8100; conferir esse fluxo em uso.

## Verificação local

Resultados confirmados até este ponto:

- Status, loader, navegação e núcleo: 39 aprovados e 1 teste de host pulado.
- Registro, menus, loader e arquivos de backup: 68 aprovados, 17 subtestes.
- Runtime DSpace no host fora do remapeamento: 62 aprovados, 1 pulado, 18 subtestes.
- Inventário/compactação na tela de backup (80×24 e160×48) e confirmação: 3 aprovados.
- Bats DS01 em contêiner Debian descartável como root: 2 aprovados; cobrem formato antigo e gz/bz2/xz dentro do conjunto.
- Sintaxe, checksum do instalador e reprodução do build bundle aprovados.
- Rodada combinada de telas: 97 aprovados e 1 falha de espera fixa no teste de restauração. O teste agora aguarda a conclusão observável; os 4 casos de restauração passaram na rodada focada após a correção. Não houve aceite integrado Docker/navegador nesta etapa.

Os arquivos /tmp/recovery-*.log guardam saídas desta execução, mas o código e os
testes devem ser persistidos no Git; a continuidade não deve depender de /tmp.

Comandos relevantes:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=panel /workspace/.koha-dev/venv/bin/python -m pytest panel/tests/test_status_recovery.py panel/tests/test_loader.py nexus_core/tests/test_status.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=panel /workspace/.koha-dev/venv/bin/python -m pytest panel/tests/test_dspace_panel.py panel/tests/test_backup_center.py tests/test_dspace_backup.py nexus_core/tests/test_instances.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=panel /workspace/.koha-dev/venv/bin/python -m pytest panel/tests/test_menus.py panel/tests/test_docs_preview.py panel/tests/test_installer_sha256.py
bash -n installer
sha256sum -c installer.sha256
python3 tools/dspace_build_bundle.py --check
```

Após qualquer alteração de runtime.py/backup.py, recalcular seus SHA no installer
antes de recalcular installer.sha256. Regenerar preview ao mudar menus. O bundle
experimental de build não inclui runtime.py/backup.py; `--check` confirma sua
reprodutibilidade sem reconstruir imagens.

Não mesclar automaticamente. Nenhum teste no servidor de Paulo foi executado.
