# PR combinado 5 e 6 — operações DSpace

Base: main 1504c03, PR4 #354 mesclado, versão 1.5.183.

Objetivo: concluir a integração operacional numa única branch/PR, com blocos de mudança separados por commits. Não publicar imagens, broker, certificados ACME ou DNS em produção, nem mesclar automaticamente.

## Contratos

- Backups individuais DSpace continuam integralmente cifrados; conjuntos com DSpace usam formato 2, mantendo o leitor e o significado do formato 1. Um plano guarda sua lista explícita de participantes. Os planos antigos continuam Koha/Tainacan.
- Agendas e conexões de nuvem aparecem nas centrais compartilhadas. Cada execução registra captura, cópia e retenção separadamente; captura parcial ou cópia falha não autoriza eliminar a última cópia boa.
- Restauração seletiva usa o restaurador de cada plataforma. DSpace exige frase, versão e matriz compatíveis; sem restaurar as outras plataformas implicitamente.
- Endereço canônico, origem HTTP do proxy/túnel e TLS são conceitos separados. Alterar endereço preserva propriedades personalizadas e requer prévia, confirmação, backup e retorno ao estado anterior em falha. Não editar proxy de terceiros.
- Endereço gratuito depende de capacidade do broker implantado. Código e migração não equivalem a publicação; manter os endereços Koha/Tainacan existentes.
- Primeira atualização homologável: receita 3 para receita 4 do mesmo DSpace 10.1, sem mudar PostgreSQL/Solr nem esquema. Exigir catálogo imutável e cópia de segurança verificada. Migrações não homologadas são recusadas.
- Remoção mantém dados por padrão. Exclusão requer confirmação adicional, backup verificável e propriedade comprovada de cada recurso. Docker, Apache, túnel e credenciais compartilhados não são removidos por pertencerem também a outras plataformas.

## Validação

Testes nativos de formatos, concorrência, falhas e preservação dos contratos antigos; testes do painel e broker; provas com serviços reais na CI para captura/recuperação, agenda, URL/HTTPS, atualização e remoção. Registrar separadamente testes executados, simulados e pendentes. Não declarar homologado em servidor de Paulo, ARM, Windows/WSL ou após reboot de VM sem execução real.

## Estado

Em implementação. Este documento registra o escopo; não afirma que os critérios acima já passaram.

## Implementação entregue na branch

Versão 1.5.184, branch `feat/dspace-operations`, base de revisão `main` após #354. Um único PR reúne as etapas 5 e 6; não depende de branches empilhadas.

| Área | Comportamento |
|---|---|
| Central de backups | DSpace individual; Koha + DSpace; Tainacan + DSpace; os três; preserva o conjunto antigo Koha + Tainacan |
| Conjuntos | Formato 2 apenas quando contém DSpace, como pacote integral cifrado; formato 1 e seus participantes continuam válidos |
| Restauração | Inspeção por conteúdo, snapshot privado antes da extração, rejeição de duplicatas/conteúdo não declarado, seleção por plataforma; DSpace passa pelo restaurador isolado do PR4 |
| Planos | Participantes fixos, horário diário, retenção por quantidade de pacotes válidos, histórico privado, trava por plano e travas existentes por plataforma |
| Nuvem | Usa as conexões rclone existentes, inclusive Google Drive; saída nova integralmente cifrada, cópia conferida, sem poda após falha/resultado parcial |
| Desativar agenda | Não exige acessar destino, nuvem ou chave: permite desligar um plano mesmo com essas dependências indisponíveis |
| Endereço | Alteração assistida da URL canônica, preservando configuração personalizada e identificadores; backup cifrado e recuperação isolada antes da mudança |
| HTTPS | Apache com certificado/chave existentes, ou trechos para o Nginx/Caddy já administrado pela instituição. Não há emissão ACME automática |
| Endereço gratuito | `<nome>-repositorio.koha.nexus`, origem HTTP só em `127.0.0.1:18102`, descoberta de capacidade, migração 0004 e adesão/remoção do serviço DSpace preservando os demais |
| Atualização | Apenas receita 3 → 4 do DSpace 10.1, com catálogo imutável; mesma versão de PostgreSQL/Solr/esquema; verificação de backup e rollback de configuração/imagens em falha |
| Remoção | Mantém dados por padrão e desativa apenas planos participantes. Apagar volumes ativos exige confirmação digitada e backup testado; mantém backups e volumes anteriores de recuperação |
| Interrupções | Diário privado e bloqueio de outra mutação até recuperação explícita. Uma restauração interrompida não pode ter seu diário sobrescrito por um novo backup de endereço/atualização |

Os dados não são capturados no mesmo instante entre plataformas. A captura de cada participante usa seu adaptador e registra seu próprio intervalo. A restauração de várias plataformas é sequencial, com as confirmações e salvaguardas de cada uma; não é uma transação distribuída.

Uma nova agenda guarda os participantes no arquivo privado. Instalar DSpace depois não muda agendas anteriores. Editar um arquivo de cron manualmente faz o instalador recusar a sobrescrita/remoção automática desse arquivo.

## Pontos de operação

- Menus permanentes: DSpace → endereço/HTTPS, atualização e remoção; centrais gerais → backups, planos, conexões e agendas. O assistente chama as mesmas rotinas e permite fazer depois.
- Planos: `/var/lib/koha-nexus/backup-plans/`, registros e históricos privados. Cron: `/etc/cron.d/koha-nexus-plan-<id>`.
- Saída de um plano: `<destino>/nexus-<id>/`, subpasta privada criada pelo sistema; não altera a permissão da pasta de backups compartilhada.
- Cofre e kit de recuperação continuam compartilhados. A frase e o kit são necessários para recuperar DSpace: não existe recuperação de seu pacote cifrado sem a chave.
- A retenção elimina apenas arquivos registrados por aquele plano e, na nuvem, apenas o caminho exato registrado na conexão atual. Não faz limpeza global de Drive, diretórios, volumes ou repositórios.
- O backup individual original de DSpace, criado durante a captura de um conjunto/plano, permanece na pasta individual. A retenção do plano governa suas próprias saídas, não essas cópias de origem nem backups manuais anteriores.
- Restauração DSpace continua exigindo a matriz e o endereço compatíveis do PR4. Troca de versão maior, PostgreSQL/Solr diferente e migração arbitrária de endereços no restaurador são recusadas.
- O diário de operações contém configuração privada. Não publicar seu conteúdo nem o de `local.cfg`/`db-password` em issues. O resumo público seleciona apenas operação/fase, sem exportar esses arquivos.
- Após apagar volumes ativos, configuração e diário são arquivados privadamente fora do diretório ativo (`dspace-removed-<id>`). Backups e volumes históricos preservados precisam de revisão explícita antes de uma nova instalação; não são adotados ou apagados silenciosamente.

## Broker: preparação não é publicação

O código permanece com `DSPACE_ENABLED = "false"`. O mantenedor deve revisar a migração 0004 e aplicar as migrações pendentes em ordem, incluindo a 0003 da etapa T, antes de habilitar e publicar o Worker. Manter `DSPACE_SUFFIX = "-repositorio"`: é o contrato suportado pelo cliente desta versão. A capacidade DSpace só aparece quando a variável e a migração estão presentes.

Este PR não executa nenhum desses passos na conta Cloudflare. O endereço gratuito permanece indisponível onde o serviço implantado ainda não o oferece. Não exige Koha para uma instituição usar somente DSpace. Uma biblioteca com Koha/Tainacan adiciona o repositório ao túnel existente.

O assistente de endereço gratuito desta versão exige o proxy Apache gerenciado. Com Nginx/Caddy preexistente, são oferecidos endereço institucional e trechos manuais de configuração, sem instalar ou modificar Apache.

HTTPS institucional exige DNS/certificado/proxy da instituição, e a verificação pública continua necessária. Limites de upload do túnel e da instituição podem ser menores que os da aplicação; a instalação não promete uploads ilimitados.

OAI-PMH não é publicado pelo proxy gerenciado nesta entrega experimental. A implementação upstream consultada deriva visibilidade/exclusão do índice OAI (`DSpaceSolrItem`/`XOAI`), que não está nos consumidores automáticos padrão. Expor um índice desatualizado não comprova que um item continua público. A API REST/Discovery permanece disponível, com as permissões do DSpace; homologar publicação e reconciliação OAI é uma etapa separada.

## Testes registrados até a consolidação local

- Python 3.13: 137 testes nativos, incluindo escrita real de arquivos privados, rollback por falha, diários, formato/integridade, propriedade e concorrência. Docker e cripto são explicitamente simulados nos testes de falha. A proteção de ancestrais foi executada fora do mapeamento de UID da sandbox local, sem relaxar a validação de root do produto.
- Painel/documentação: 131 testes nas áreas alteradas. Avisos existentes de encerramento de workers/Textual continuam registrados; não são resultados de servidor.
- Debian 12 descartável como root: os 17 testes de conjuntos, o teste adicional de preservação de cron e sete testes do cliente de endereço DSpace (25 no total), mais os nove testes antigos de endereço do Tainacan (34 no conjunto local). As capturas Koha/Tainacan deste arquivo usam os adaptadores de teste já declarados em `backup_set.bats`; não equivalem a instalar os três sistemas reais. Os testes do cliente de endereço usam respostas explícitas simuladas do broker e do runtime, cobrindo recusa, compartilhamento, falha e repetição de remoção.
- Broker: TypeScript, 72 testes unitários e 24 checks e2e existentes + 6 novos checks locais com Worker/D1/Durable Object, assinaturas reais e API Cloudflare simulada. Não há teste contra a conta Cloudflare de produção.
- Capturas do painel em modo de demonstração: [80×24](captures/backup-center-80x24.svg) e [160×48](captures/backup-center-160x48.svg). Os estados e dados são simulados; a rolagem do seletor de conjuntos foi verificada no terminal pequeno.

A CI executa PostgreSQL, Solr, backend, UI, GPG, rclone e navegador reais. As receitas 3 são construídas a partir do export imutável `858153cc730c17d410943836d222944149c24250`, sem rotular imagens novas como antigas. A atualização deve conferir também as imagens efetivamente em execução, além dos dados e do esquema. **Os resultados desta CI precisam ser acrescentados após terminar; testes escritos/em fila não são aprovação.**

## Pendências de liberação

Continuam sem validação no servidor de Paulo: convivência e carga reais, rede, domínio/túnel conectado, contas e política institucional, acervo grande, reboot de VM/WSL e os testes da etapa T. A matriz de aplicação real desta etapa roda em Ubuntu 24.04; não declarar os mesmos testes DSpace completos em Debian 12/13 apenas pelos testes de infraestrutura. ARM permanece sem imagem/homologação. DSpace continua experimental.

Não publicar imagens ou broker nem promover catálogo por causa desta documentação. A publicação de imagens continua exigindo dispatch explícito na main, depois dos testes de instalação e atualização. Não mesclar automaticamente.
