# Estudo de implementação do DSpace no koha.nexus

Data: 06/11/2026. Escopo: planejamento, sem implementação, publicação ou mudanças de serviços.

## 1. Base analisada e conclusão

Repositório koha.nexus: `origin/main`, commit `1d34ee8`, versão 1.5.180, com U1 a U6 mesclados. Documentos da etapa T consultáveis na branch `claude/etapa-T-docs`. A investigação utilizou uma worktree separada, sem modificar a branch de trabalho existente.

Fontes upstream efetivamente lidas:

* Backend DSpace, tag `dspace-10.1`, commit `a1f5969b3a6a1ac324328bbe2f1d0df8567df9f3`, de 14/09/2026.
* Interface DSpace Angular, tag `dspace-10.1`, commit `694ed051465faadff20ebdd973720190cbd40b9f`, de 14/09/2026.
* Arquivos Docker, Compose, README, configurações de URLs, autenticação, CORS, SSR, OAI e Solr dessas tags.

A tag correspondente nos dois projetos é uma candidata concreta para homologação, não uma afirmação de que seja a última versão disponível ou de que já esteja homologada. Antes de implementar, conferir suporte, correções de segurança, releases posteriores e compatibilidade de toda a matriz. A API de releases do GitHub respondeu 403 neste ambiente; o conteúdo das tags foi obtido por Git.

Conclusão: a arquitetura existente é aproveitável. O trabalho específico não é apenas adicionar um Compose: será necessário homologar imagens de produção, coordenar backend e interface, adaptar PostgreSQL e Solr ao backup, generalizar centrais ainda restritas a duas plataformas e comprovar recuperação e reinicialização. Não há instalação DSpace executada nem estimativa fechada de prazo neste estudo.

## 2. Fatos importantes do upstream

| Evidência | Consequência para a implementação |
|---|---|
| `pom.xml` do backend 10.1 exige Java 21 e Maven >=3.8 | Compilar em CI com toolchain homologada; não instalar Java/Maven no host do usuário |
| `dspace/src/main/docker/README.md` diz expressamente que suas imagens/recursos não estão prontos para produção | Usar como referência técnica, sem distribuir o Compose de demonstração como instalação final |
| Compose upstream usa backend `dspace-10_x-test`, senha PostgreSQL de exemplo e publica 5432/8983 | Não copiar tags, senha, portas ou configuração de confiança do exemplo |
| `Dockerfile` da interface inicia em desenvolvimento; `Dockerfile.dist` faz build e execução em produção | A interface final precisa de artefato compilado de produção, sem live reload e sem compilação no boot |
| Backend pode executar via `server-boot.jar` nessa tag | Não adicionar contêiner Tomcat independente por suposição herdada de versões anteriores |
| Compose de exemplo usa PostgreSQL 15 e Solr 9.8; interface usa Node 22 | São candidatos de laboratório; escolher patches suportados e digests após homologação, não aceitar tags móveis como contrato |
| `config.example.yml` exige `ui.baseUrl` público correto para SSR e proteção contra SSRF | URLs de navegador e URLs internas SSR devem ser configuradas e testadas separadamente |
| Solr inclui search, oai, statistics, authority, qaevent, suggestion e audit | Classificar persistência e recuperação por core; não assumir que todo Solr é cache |

## 3. Arquitetura proposta

Koha permanece nativo no host. Tainacan permanece no seu conjunto atual. DSpace tem projeto Compose próprio `kn-dspace`, rede exclusiva e recursos registrados por plataforma.

```text
Visitante / navegador
          |
 Apache existente / proxy externo / túnel gerenciado
          |
          +-- /          -> interface Angular SSR, Node em produção
          +-- /server/   -> API e endpoints DSpace permitidos
                              |
                         PostgreSQL + Solr

Nexus Core -> operações administrativas locais e tarefas CLI controladas
```

Quatro serviços persistentes principais: interface, backend, PostgreSQL e Solr. Comandos administrativos, migrações e tarefas podem usar serviços Compose de execução única, com a mesma versão do backend. Um worker persistente adicional só será criado se o comportamento da versão e o perfil escolhido o exigirem.

Não compartilhar PostgreSQL/Solr com Koha, Tainacan ou futuras plataformas. Não instalar Elasticsearch, RabbitMQ, Redis, Keycloak, WordPress ou Portal Nexus por causa do DSpace. Integrações como IIIF, SWORD, OIDC, LDAP e Handle Server público permanecem opcionais.

Preferir um subdomínio para DSpace com interface em `/` e backend em `/server`, validando todas as rotas oficiais necessárias. Não colocar a interface inteira sob `/dspace` nesta primeira entrega. O mesmo vhost atende as rotas pela porta 443, sem publicar banco ou Solr. Para laboratório/local, escolher uma porta livre própria, sem assumir 8080, já usada pelo Koha.

Tanto UI quanto API podem precisar de endpoints públicos para funcionamento; classificar rotas e bloquear interfaces operacionais internas. Não bloquear `/server` inteiro. Evitar cache compartilhado de respostas autenticadas ou privadas.

## 4. O que reutilizar e o que generalizar no código atual

| Área existente | Ação proposta |
|---|---|
| `kei_docker_*`, redes e isolamento | Reutilizar; validar permissões, acesso de saída necessário, reinício e coexistência |
| `owned.tsv`, módulos, regras e sites | Reutilizar com dono `dspace`; remoção só de recursos registrados e sem outros consumidores |
| `kei_proxy_*` e `kei_tunnel_ingress_*` | Gerar vhost específico e testar rollback, URLs e comportamento após recarga |
| `platforms.py`, menu e `views/platform.py` | Adicionar grupo DSpace, resumo na aba do painel e capacidades reais; não duplicar tela Plataformas |
| `routines/setup.py`, contas e assistente | Generalizar lista de plataformas e despacho; manter configurar agora/depois e ações permanentes |
| Motor `kei_backup_*` | Acrescentar adaptador DSpace com dump PostgreSQL, arquivos e dados Solr classificados |
| `KEI_BK_PLATFORMS="tainacan"` | Ampliar para DSpace, com testes de compatibilidade do formato e das tarefas |
| Central `backup_center.py` com `KOHA, TAINACAN, BOTH` | Trocar por seleção orientada a capacidades e conjunto explícito, preservando IDs e planos antigos |
| `KEI_SET_MEMBERS`, `kei_set_platforms`, inspeção e restauração | Hoje restringem conteúdo a Koha/Tainacan; criar versão extensível, sem afrouxar validação de arquivos |
| `schedules.py`, histórico e filtros | Acrescentar DSpace e conjuntos com participantes explícitos; não reinterpretar planos existentes como “todos” |
| rclone/GPG/restic/kit de recuperação | Reutilizar conexões e proteção; segredo e retenção sempre por plano/escopo |
| Broker gratuito | Hoje conhece Koha/Tainacan; ampliar contrato e capacidades antes de habilitar DSpace na interface |
| `.github/workflows/proxy.yml`, testes de sistema e navegador | Reutilizar infraestrutura de testes; acrescentar serviços reais DSpace e matriz compatível com recursos de runner |

O catálogo atual marca DSpace como não suportado. Só mudar esse estado ao entregar os critérios mínimos. Preferir adaptadores e módulos revisáveis em vez de continuar copiando blocos extensos Tainacan no `installer`. A extração de código deve ser gradual, com arquivos auxiliares incluídos e verificados pelo mecanismo de atualização; não reestruturar o projeto inteiro neste trabalho.

## 5. Produção e cadeia de imagens

Criar receitas próprias mantidas no projeto, apoiadas na release oficial e nas recomendações upstream, sem modificar o núcleo funcional do DSpace desnecessariamente.

* Fontes fixadas por tag e commit; bases e artefatos fixados por digest. Configurações Solr vêm da mesma release do backend.
* Build multi-stage em CI, dependências e lockfiles controlados, sem credenciais dentro das camadas.
* Distribuir imagens de runtime previamente construídas. Nenhum `npm install`, Maven ou build Angular em cada instalação ou boot.
* Executar com usuário não privilegiado e diretórios graváveis explicitamente separados de código/configuração. Medir permissões exigidas pelos scripts oficiais antes de impor filesystem somente leitura.
* Publicar versão da receita, proveniência, licenças e componentes; verificar vulnerabilidades e tratar achados pertinentes antes da homologação.
* Testar disponibilidade e compatibilidade de amd64 e arm64. Oracle ARM é relevante, mas não anunciar suporte sem imagem e teste reais. Nunca usar emulação silenciosa como substituto.
* O projeto precisa escolher registro e política de publicação de imagens. Até existir esse canal homologado, não prometer instalador de produção pronto; laboratório e build de engenharia permanecem identificados.

## 6. Contrato de instalação confiável

### 6.1 Prévia sem alterações

`dspace-plan` e estado/status não instalam pacotes, não criam contas e não modificam serviços. A prévia informa versões, digests, arquitetura, serviços, memória prevista, disco, portas, URLs, rede, dados persistentes e alterações próprias. Instalar requer confirmação explícita pelo fluxo do painel.

Verificar sistema suportado, Docker/Compose, arquitetura, relógio, rede, DNS, recursos, espaço de download/descompactação, portas, sub-redes e recursos preexistentes. Não assumir que RAM total está livre ou que um servidor com Koha pode dedicar toda memória ao Java.

Para dimensionamento inicial de laboratório, avaliar perfil dedicado de 8 GiB e perfil compartilhado a partir de 16 GiB como pontos de partida de medição, não como mínimos oficiais ou garantia de capacidade. Medir picos reais de boot, indexação, extração e recuperação antes de fixar limites no instalador. Acervos e carga determinam armazenamento e memória. Swap não substitui um orçamento suficiente de RAM.

### 6.2 Estados e retomada

Estados: ausente, preparando, instalando, instalado, parado, degradado, falhou e dados mantidos. Estado persistido não substitui observação dos serviços. Diferenciar pausa intencional de falha.

Trava por plataforma e trava de operações incompatíveis: instalar/atualizar/restaurar/backup não podem concorrer. Diário atômico registra cada fase, versão da receita, propriedade e resultado, sem segredos.

Fases propostas:
1. Conferir ambiente e confirmação.
2. Baixar e verificar imagens, antes de qualquer indisponibilidade.
3. Criar configuração privada, segredos, rede e volumes próprios.
4. Iniciar PostgreSQL e Solr; validar prontidão e configurações.
5. Executar inicialização/migração controlada uma única vez, registrando resultado e lock.
6. Iniciar backend e validar API/serviços.
7. Iniciar interface em produção e validar conexão local e SSR.
8. Aplicar proxy com configtest, verificação dos sites existentes e retorno ao estado anterior em falha.
9. Executar provas funcionais e gravar o resultado real.
10. Abrir assistente pós-instalação; adiar não reverte instalação nem expõe serviços.

Timeouts específicos, progresso legível, cancelamento e tratamento de sinais. Depois de falha, preservar dados e oferecer retomada controlada; não repetir migrações destrutivas nem executar `down -v`. A execução repetida deve reconhecer instalação e oferecer manutenção, não reinstalar por cima.

Falha em primeira instalação pode recolher só recursos próprios novos, quando seguro. Se já houver dados, priorizar preservação e diagnóstico. Migração concluída não é desfeita apenas trocando imagem.

### 6.3 Inicialização e reinicialização

Ordem PostgreSQL/Solr -> backend -> interface, com healthchecks e espera real. Política de reinício não pode iniciar migração indiscriminada em todo boot. Containers precisam recuperar conexões após indisponibilidade transitória.

Docker deve voltar com o host quando suportado. A unidade de isolamento existente precisa estar ativa na ordem correta. Validar reboot de máquina, não somente `compose restart`. No WSL, distinguir início da distribuição, systemd e Docker: reiniciar Windows não garante que a distribuição foi iniciada. Diagnóstico identifica ambiente parado e endereço alterado antes de recomendar restauração.

## 7. Endereços, domínio e proxy

Usar URL externa canônica para navegador e SSR, sem confundir o endereço interno do backend. Alinhar `dspace.ui.url`, `dspace.server.url`, `dspace.server.ssr.url`, `ui.baseUrl`, `rest` e `ssrBaseUrl` conforme a versão homologada.

Confiar apenas no proxy/rede geridos, validando `Host`, esquema, CORS, cookies/CSRF, redirects e URLs de download. Testar backend e interface atrás de HTTP local, HTTPS e túnel. Nunca deixar frontend apontando para `localhost` do visitante ou para o sandbox upstream.

Escolha simples: local, domínio institucional, endereço gratuito quando suportado ou configurar depois. Manter operações permanentes em Segurança/conectividade e reutilizá-las no assistente.

Alterar URL exige plano com valores antigos/novos, backup de configuração, confirmação e validação; não reescrever identificadores persistentes automaticamente. Configuração HTTPS não significa que o certificado/túnel já existe. Preservar recursos compartilhados.

DSpace deve usar um endereço próprio, distinto do portal WordPress. Endereço gratuito exige extensão do broker e descoberta de capacidade. Sufixo como `-repositorio` é proposta a validar contra comprimento, colisões e certificado; não é recurso existente. Até implantação externa, mostrar indisponibilidade com motivo. Não publicar Worker, DNS ou migração de produção nesta etapa.

Arquivos grandes podem exceder limites do túnel/proxy. Configurar e testar o menor limite efetivo entre aplicação, proxy e serviço externo. Explicar limites e permitir acesso institucional apropriado, sem prometer upload ilimitado.

## 8. Interface e assistentes

Grupo `DSpace (repositório institucional)`: ausente oferece instalar; instalado oferece acesso/ações; falha oferece diagnóstico e início controlado. Resumo apenas na aba DSpace do Painel de Controle, com links público e administrativo corretos da interface Angular, versão, estado por serviço, contagens, disco, backup e última verificação.

Saúde em níveis: processo, dependências, API, UI/SSR e fluxo funcional. “Serviços rodando” não equivale a pronto. Não criar itens fictícios de teste em repositório de produção para cada status. Verificação aprofundada explícita, com data e resultado guardados; status rápido não faz reindexação nem modifica conteúdo.

Grupos funcionais: acesso administrativo, diagnóstico/logs, comunidade/coleções e links de operação, identidade/idioma, e-mail, manutenção/indexação. Backups e agendamentos continuam nas centrais gerais, com atalhos filtrados. Remoção separada e manter/apagar dados com confirmações e backup final quando viável.

DSpace não tem Staff Koha nem administração WordPress. Usar interface administrativa e CLI oficiais compatíveis. Criar primeiro administrador por operação local protegida; “fazer depois” mantém o estado seguro, sem conta padrão, registro aberto concedendo administração ou dependência obrigatória de e-mail. Nunca registrar senha em argumentos, logs ou status. Verificar o comportamento concreto da CLI da release e usar entrada protegida/API local apropriada.

Oferecer alterar senha e criar administrador quando suportado e validado, preservando contas existentes. Não implementar política institucional nem conceder permissões a todos automaticamente.

Assistente pós-instalação: acesso -> acesso público -> backup/nuvem/agenda -> primeiros passos. Cada etapa pode ser adiada e usa a mesma função permanente do menu. Registrar pendências sem duplicar parâmetros ou agendamentos.

## 9. Características específicas e recursos extras necessários

| Recurso | Tratamento |
|---|---|
| Comunidade -> coleção -> depósito -> revisão/publicação | Orientação inicial e links oficiais; não cadastrar hierarquia institucional sem pedido |
| Metadados e formulários de submissão | Preservar registros/configurações customizadas e fornecer exportação/backup; não criar editor paralelo completo inicialmente |
| Perfis, políticas de acesso, embargo e licença de depósito | Validar fluxos reais e privacidade; o painel não inventa política jurídica nem remove embargo |
| SMTP e recuperação de conta | Assistente específico, compartilhando conexão só quando explicitamente escolhido; teste de envio solicitado, nunca disparo em massa |
| Handle e DOI | Distinguir identificador local de registro/resolução global; prefixo/conta externos não são gratuitos por instalação; não inventar Handle resolvível |
| Discovery e OAI-PMH | Comandos de atualização/reindexação e agendamento oficiais, com trava, logs e monitoramento |
| Integridade dos arquivos | Checagem de checksums e histórico; corrupção é alerta, não motivo para sobrescrever automaticamente |
| Extração de texto e miniaturas | Tarefas limitadas e observáveis; medir CPU/RAM/disco; não habilitar processamento ilimitado ou dependências extras sem necessidade |
| Estatísticas e auditoria | Persistência e política de backup próprias; podem conter dados pessoais e não ser reconstruíveis pelo banco |
| Idiomas e identidade visual | Idioma do painel separado do idioma da UI; confirmar pacotes pt-BR; logo/título/configuração suportada, tema avançado em build versionado |
| Coleta futura para Portal Nexus | Documentar API/OAI, paginação, permissões e exclusões; não implementar busca integrada nem SSO agora |

## 10. Backup consistente e recuperação

Não reaproveitar mysqldump nem comandos WordPress. Adaptador DSpace usa ferramentas PostgreSQL da versão homologada; dump lógico validado e identificado no manifesto como PostgreSQL. O motor atual escreve `db.sql.gz`; se mantido, usar SQL compatível e restaurador PostgreSQL. Se preferir formato custom `pg_dump`, versionar e explicitar o nome/formato, sem mascará-lo como SQL.

Incluir banco, todos os assetstores/arquivos locais reconhecidos, configuração personalizada, formulários/licenças/temas necessários, inventário e digests de imagens, segredos e dados Solr não reconstruíveis. Detectar armazenamento externo: recusar o rótulo completo se não capturado ou se depender de uma conta externa não recuperável. Informar dependências fora do pacote.

Classificação Solr por core é requisito prévio: search/OAI podem ser reconstruídos conforme comandos oficiais; statistics, audit e demais cores exigem avaliação concreta. Na primeira recuperação homologada, preferir preservar todos os dados Solr por snapshot/cópia fria consistente e versão exata, junto com plano de reconstrução dos índices derivados. Não copiar diretórios Solr em escrita. Validar export/import oficiais para dados históricos antes de adotar alternativa mais portátil.

Janela de captura: bloquear novas escritas, parar agendamentos e processos CLI/filas relevantes, drenar requisições e parar backend, suspender escritores Solr. Com tudo drenado, fazer dump PostgreSQL e capturar arquivos e Solr. Retomar exatamente os serviços antes ativos, inclusive em falha tratável. Registrar duração. Uma página de manutenção sozinha não bloqueia importadores, API ou tarefas.

Atualizar o diário do motor para registrar retomada realmente bem-sucedida, sem marcar “writes-resumed” quando o serviço falhou ao voltar. Dimensionar espaço de dumps, arquivos, staging, pacote e recuperação sem confiar em compressão otimista.

Segredos protegidos pelo mecanismo existente. Explicar quais podem ser trocados e quais são necessários para ler dados/identificadores; alteração de senha administrativa não troca chaves automaticamente. Dados de usuários/documentos também são sensíveis: envio remoto deve obedecer à política de criptografia, não só cifrar `.env`.

Teste isolado: rede sem saída desnecessária, SMTP e notificações bloqueados, sem registro de identificadores, harvesters ou chamadas de escrita externos, portas públicas ausentes. Usar cópia independente de banco, assetstore e Solr. Conferir UUIDs, handles, políticas, itens, bitstreams e amostras de checksum; download autorizado e negação de acesso privado. Não comparar só contagens.

Restauração real exige prévia, backup de segurança, compatibilidade de release/esquema, destinos e espaço. Preservar URLs e credenciais do destino conforme escolha explícita. Reconstruir índices derivados e validar serviço antes de finalizar. Migração de backup entre versões não é garantida inicialmente: primeiro restaurar na mesma matriz homologada.

## 11. Conjuntos de backup com três plataformas

Generalizar seleção para subconjunto explícito das instaladas, mantendo atalhos simples. Um plano Koha+Tainacan existente continua com os mesmos participantes depois de instalar DSpace. Nunca ampliar automaticamente para “todos”.

Manifesto novo versionado, leitores de formatos antigos preservados, lista permitida por plataforma e adaptador. Rejeitar plataformas desconhecidas, caminhos e links perigosos, arquivos duplicados ambíguos, extração excessiva e inconsistências antes de aplicar. Nada do manifesto vira código.

Oferecer DSpace individual e depois conjuntos Koha+DSpace, Tainacan+DSpace e três sistemas, com restauração seletiva. Validar separadamente o novo formato antes de habilitar os conjuntos adicionais no painel. Leitores antigos recusam formato desconhecido de modo claro.

Travas e retenção por plano; se outra operação conflitar, falhar/pular explicitamente sem apagar backup anterior. Histórico distingue captura, empacotamento, criptografia e envio. Falha em cópia remota não transforma captura local válida em inexistente nem permite declarar nuvem concluída. Pacote transportável não referencia repositório externo como única cópia dos dados.

## 12. Atualização e remoção

Atualização não é `pull latest`. Plano mostra matriz origem/destino, requisitos, backup completo e teste prévio, disponibilidade de imagens e janela de parada. Adotar patches homologados de forma deliberada; upgrade de versão principal em etapa própria.

Migrar banco de modo controlado, atualizar schema/configsets Solr quando necessário e validar UI+backend. Voltar apenas à imagem antiga não desfaz migração; recuperação inclui banco, arquivos e dados/configurações compatíveis. Upgrade principal de PostgreSQL requer dump/restore ou procedimento validado, nunca montagem do mesmo volume numa major nova.

Remoção padrão mantém dados; remoção completa só de recursos próprios, com plano, confirmação e opção de backup final. Não remover Docker, Apache, GPG, rclone ou regras usadas por outras plataformas. Desabilitar agendas próprias e atualizar contratos públicos sem apagar Koha/Tainacan ou seus conjuntos.

## 13. Divisão adotada: seis PRs

A proposta inicial tinha oito blocos técnicos. A execução foi consolidada em seis
PRs, sem retirar os critérios de aceite: contratos ficam junto da fundação, e
publicação/atualização/documentação ficam na última etapa. Um PR é revisado antes
de mesclar; não há mesclagem nem publicação de produção automática.

| PR | Entrega | Critério para concluir |
|---|---|---|
| 1 | Fundação, contrato de release, receitas de imagens e CI (#347, mesclado) | Builds fixados, permissões e smoke reais; DSpace ainda indisponível no painel |
| 2 | Instalador/CLI isolado (#352, mesclado), rede, persistência, proxy local e estado | Instalação real, falhas/retomada, ciclo de serviços e dados persistentes; catálogo público ainda sujeito a promoção explícita |
| 3 | Painel, administrador, assistente e primeiros passos (#353, mesclado) | Fluxo real de depósito/consulta e permissões, idiomas, pré-requisitos assistidos e início/parada; não só HTTP 200 |
| 4 | Backup e restauração individual (versão 1.5.183, branch `feat/dspace-backup-restore`; detalhes em [PR4-backup-recovery.md](PR4-backup-recovery.md)) | Recuperação de base vazia com documentos privados/públicos, checksums e dados Solr históricos |
| 5 | Conjuntos e agendamentos extensíveis | Subconjuntos e planos antigos corretos, falhas parciais e retenção testadas |
| 6 | Domínio/HTTPS/broker, atualização e documentação operacional | Publicação compatível, atualização/recuperação homologadas, reboot e pendências operacionais registradas |

Não anunciar instalação pronta para produção antes de backup/recuperação e
operação básica aprovados. DSpace experimental deve ser identificado sem
ambiguidades até esse marco. A ausência de teste no servidor do Paulo continua
explícita; a CI real reduz riscos, mas não equivale a homologar esse servidor.
Não reabrir os PRs anteriores de Koha/Tainacan para acomodar DSpace.

## 14. Matriz de testes obrigatórios

* Cenários: nenhuma plataforma, DSpace sozinho, Koha+DSpace, Tainacan+DSpace e os três. Não exigir instalar outro sistema para preparar nuvem, domínio ou administrador.
* Hosts: Debian 12, Debian 13 e Ubuntu 24.04 conforme suporte atual; amd64 inicialmente e arm64 antes de anunciá-lo. WSL com teste específico e status de suporte explícito.
* Instalação: sem Docker/com Docker preexistente, proxy próprio/compartilhado/externo, portas/sub-redes ocupadas, download interrompido, disco insuficiente, permissão errada e serviço que não fica pronto.
* Segurança: nenhum serviço 5432/8983 exposto, isolamento entre plataformas, senhas fora dos logs, confiança limitada do proxy, acesso privado/embargo negado e sem vazamento por busca/OAI/SSR.
* Navegador: entrar, criar comunidade/coleção, depositar arquivo com metadados, workflow/publicação, pesquisar, baixar arquivo público, negar privado e verificar hash. Testar interação real e SSR sem depender só de JavaScript para metadados públicos importantes.
* Reinicialização: contêineres, Docker e máquina; ambiente começa com serviço ausente ou falhando; operação intencionalmente parada não é declarada corrompida.
* Recuperação: dump inválido, arquivo ausente, corrupção de bitstream, segredo ausente, pacote malicioso, restauração seletiva e manutenção da outra plataforma. Simular encerramento abrupto e recuperação de estado interrompido.
* Nuvem: autorização adiada, falha de upload, credencial perdida, pacote cifrado e retenção que nunca remove o último válido após falha.
* Updates: backup validado, migração falhando e recuperação de matriz anterior, configuração personalizada preservada.
* UI: terminal 80x24/160x48, teclado e traduções; cancelamentos não alteram servidor.

Pipeline: testes unitários rápidos; integração real com PostgreSQL/Solr/UI/backend; e2e de release; máquina virtual com systemd/reboot para aceite de publicação. Se testes forem divididos por custo, documentar quais bloqueiam PR e quais bloqueiam release. Não atribuir sucesso a testes apenas escritos ou mocks.

## 15. Pendências e critérios de liberação

Antes da implementação: confirmar versão/suporte e correções, disponibilidade/licenciamento/procedência de imagens e matriz final PostgreSQL/Solr/Node/Java, orçamento de recursos, extensões PostgreSQL necessárias e comportamento dos comandos de administração/migração.

Antes de produção: ambiente realmente reinicia, instalação é repetível, depósitos e permissões funcionam, recuperação em ambiente vazio passa, versões e fontes são rastreáveis, domínio funciona ou modo local está claramente documentado. Publicação do broker só em etapa externa apropriada.

Pendências anteriores permanecem: Tainacan de Paulo após reboot, validação da etapa T no seu servidor e implantação do broker. Não são resolvidas pela instalação DSpace. Não realizar testes destrutivos no servidor de Paulo.

Fora do escopo: AtoM, Portal Nexus, busca unificada, SSO/Keycloak, migração automática de repositórios antigos, CRIS completo, alta disponibilidade e registro pago de identificadores. A arquitetura mantém pontos de integração sem implementar essas frentes agora.

## 16. Fontes rastreáveis

* [koha.nexus na base analisada](https://github.com/PauloFBaldiFH/koha.nexus/tree/1d34ee8)
* [Motor de backup e adaptadores](https://github.com/PauloFBaldiFH/koha.nexus/blob/1d34ee8/installer#L14618)
* [Formato conjunto atualmente restrito a Koha/Tainacan](https://github.com/PauloFBaldiFH/koha.nexus/blob/1d34ee8/installer#L15574)
* [Central de backups](https://github.com/PauloFBaldiFH/koha.nexus/blob/1d34ee8/panel/kei_panel/backup_center.py)
* [Agendamentos](https://github.com/PauloFBaldiFH/koha.nexus/blob/1d34ee8/panel/kei_panel/schedules.py)
* [Assistente](https://github.com/PauloFBaldiFH/koha.nexus/blob/1d34ee8/panel/kei_panel/routines/setup.py)
* [Código DSpace 10.1](https://github.com/DSpace/DSpace/tree/a1f5969b3a6a1ac324328bbe2f1d0df8567df9f3)
* [Advertência Docker upstream](https://github.com/DSpace/DSpace/blob/a1f5969b3a6a1ac324328bbe2f1d0df8567df9f3/dspace/src/main/docker/README.md)
* [Compose upstream](https://github.com/DSpace/DSpace/blob/a1f5969b3a6a1ac324328bbe2f1d0df8567df9f3/docker-compose.yml)
* [Configuração backend](https://github.com/DSpace/DSpace/blob/a1f5969b3a6a1ac324328bbe2f1d0df8567df9f3/dspace/config/local.cfg.EXAMPLE)
* [Interface DSpace 10.1](https://github.com/DSpace/dspace-angular/tree/694ed051465faadff20ebdd973720190cbd40b9f)
* [Dockerfile de produção da interface](https://github.com/DSpace/dspace-angular/blob/694ed051465faadff20ebdd973720190cbd40b9f/Dockerfile.dist)
* [Configuração UI, SSR e REST](https://github.com/DSpace/dspace-angular/blob/694ed051465faadff20ebdd973720190cbd40b9f/config/config.example.yml)

As fontes são código e documentação versionados. Nenhuma inspeção estática deste estudo equivale a homologação de runtime; resultados reais devem ser acrescentados na implementação.
