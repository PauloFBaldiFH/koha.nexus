# Recuperação do painel e evolução para múltiplas instâncias

Plano de 08/11/2026, preparado a pedido de Paulo **antes de implementar**.
Base inspecionada: `feat/dspace-experimental-install`, commit `a175b69`, sobre
`d762182`. A versão efetivamente executada no servidor de Paulo ainda precisa
ser identificada; esta análise não pressupõe acesso a esse servidor.

Este documento complementa o estudo `plano-instancias.pt-BR.md` e substitui,
para o próximo trabalho, suas decisões sobre pós-instalação e ordem dos PRs.
O estudo anterior permanece preservado. Nesta etapa foi feita investigação
de código e uma reprodução isolada; nenhuma correção do produto foi aplicada.

## 1. Resultado que precisamos entregar

1. Painel com indicadores legíveis, atualização limitada no tempo e erro
   localizado quando uma fonte não responde.
2. DSpace acessível pelo endereço local mostrado ao usuário, incluindo a
   página de login, sem depender de configurar domínio ou nuvem.
3. Instalação que termina numa tela de conclusão, sem abrir automaticamente
   perguntas de publicação e backup. Essas funções ficam nos menus permanentes.
4. Remoção fácil de encontrar, inclusive para instalação parada ou incompleta,
   com separação clara entre manter os dados e apagá-los.
5. Idiomas disponíveis conforme cada aplicativo, sem a limitação artificial
   de três idiomas no cadastro do DSpace.
6. Navegação por instância: adicionar, acessar e administrar cada instalação.
   Duas instalações do mesmo sistema têm dados e configurações independentes.
7. Infraestrutura compartilhada com responsáveis identificados: portas,
   proxy, certificados, túnel, backups e agendamentos não se sobrescrevem.
8. Instalações, URLs, contas, backups e agendas atuais continuam aproveitáveis.

Primeiro recuperamos o funcionamento existente. Múltiplas instâncias exigem
mudanças de contrato e não devem ser usadas como tentativa de consertar os bugs
atuais. A criação experimental continua disponível pelo fluxo normal; não
reintroduzir a exigência de publicar imagens ou preparar catálogo manualmente.

## 2. Achados: o que foi confirmado e o que ainda falta provar

| Problema relatado | Evidência | Tratamento |
|---|---|---|
| Todos os cartões ficam em `...` | Reproduzido um defeito no protocolo entre instalador e painel quando existe estado do DSpace | Correção prioritária do produtor e dos leitores; recuperação visual por componente |
| DSpace mostra estado desconhecido e nenhuma ferramenta | O leitor de status falha; `ZONES['unknown']` é vazio e a tela oculta todas as ações | Manter diagnóstico, atualização e acesso à remoção identificável; ações executáveis passam por verificação própria |
| Login em `http://192.168.1.50:8100/login` fica em branco | A captura comprova o sintoma; não identifica a causa do erro web | Investigar a cadeia navegador → Apache → UI/API e reproduzir acesso por IP de rede |
| Domínio e backup são perguntados após instalar | Confirmado em `routines/setup.py` e `routines/dspace.py` | Remover a abertura automática e substituir por conclusão com atalhos |
| Não encontra botão de apagar instância | DSpace e Tainacan já têm rotinas, mas dependem da navegação/estado; Koha exige tratamento próprio | Entrada permanente de remoção e fluxo por identidade, sem exigir que a aplicação esteja saudável |
| Apenas três idiomas no DSpace | Lista fixa repetida no painel, runtime Python e helper Java | Catálogo compartilhado por versão, baseado nos idiomas efetivamente entregues |
| Mais de uma instalação do mesmo sistema | Código atual usa nomes, caminhos e membros de backup por tipo de plataforma | Registro de instâncias e adaptação completa dos recursos e tarefas |

### 2.1. Causa reproduzida do painel vazio

Caminho atual:

1. `installer`, função `kei_status_json`, incorpora `kei_platforms_json`.
2. Quando existe `state.json` do DSpace, `kei_dspace_json` usa Python e
   `print(json.dumps(...))`, que acrescenta uma quebra de linha dentro da saída
   geral. Com DSpace ausente, essa quebra não é emitida.
3. `panel/kei_panel/bridge.py`, método `Bridge.status`, seleciona apenas a
   última **linha** que começa com `{` e tenta interpretá-la como o objeto todo.
4. A saída completa é JSON válido, mas a linha isolada é incompleta.
5. `DashboardView._load` interrompe a atualização. O erro aparece no cartão de
   estado do Koha, que pode estar em outra aba; os cartões gerais permanecem
   nos valores iniciais. A coleta complementar de CPU também depende desse
   primeiro carregamento ter funcionado.
6. A tela DSpace captura a falha como `{}`. O estado se torna desconhecido e
   a política de visibilidade esconde suas ferramentas.

Reprodução em processo temporário, executando os dois serializadores reais e
o `Bridge.status` real, com respostas de serviços simuladas:

```text
Estado DSpace ausente: saída de 1 linha; JSON completo válido; Bridge.status passa.
Estado DSpace presente: saída de 2 linhas; JSON completo válido;
Bridge.status lança JSONDecodeError: Expecting ',' delimiter.
```

Isso explica de forma reproduzível a falha geral mostrada nas capturas. A
confirmação no servidor requer conferir o comando/versão que ele executa e
sua saída. Não comprova a causa da página web em branco.

Há leitores com a mesma suposição em `nexus_core/status.py` e
`windows/KohaEasy.Core.psm1`. Corrigir somente a tela Textual deixaria outros
clientes expostos ao problema.

### 2.2. Outros pontos do status que agravam o problema

- `Bridge.status` não impõe prazo total a `proc.communicate()` e descarta stderr.
- O adaptador do DSpace pode baixar arquivos durante a leitura se a cópia local
  não corresponder ao checksum esperado. A abertura do painel deve funcionar
  sem rede e sem iniciar essa preparação.
- `kei_tainacan_json` pode executar uma sondagem de saúde, apesar de ser parte
  de uma consulta geral. Uma plataforma lenta pode atrasar as demais.
- Exceções na renderização depois da consulta ficam em workers com
  `exit_on_error=False`; precisam produzir um erro visível e recuperável.
- Há coleta de saúde já separada em `health.py`. Ela pode ser reaproveitada,
  retirando a dependência de obter primeiro um status geral perfeito.

### 2.3. Acesso web do DSpace: investigação ainda necessária

O teste existente usa `repository.kei.test:8100`, resolvido para loopback, com
regras de rede do próprio navegador de teste. Isso é útil, mas não demonstra
que a instalação apresentada ao usuário funciona por IP da rede local.

Verificar, nesta ordem, sem reinstalar ou apagar dados:

1. Versões realmente executadas do painel, instalador, adaptador e imagens;
   fase registrada da instalação e operações interrompidas.
2. Estado, saúde, reinícios, OOM e logs limitados dos quatro serviços.
3. Vhost Apache e porta 8100; encaminhamento de `/` e `/server`; resposta de
   `/`, `/login` e `/server/api` com o Host usado pelo usuário.
4. JavaScript, CSS, traduções e configuração do navegador: status HTTP,
   MIME, caminhos e conteúdo; identificar arquivos ausentes ou página HTML
   devolvida no lugar de um recurso.
5. Console e requisições com falha do navegador, sem registrar senhas/tokens.
6. Correspondência entre URL canônica, URLs retornadas pela API, CORS, cookies,
   cabeçalhos do proxy, SSR e configuração pública gerada pela UI.
7. Diferença entre acessar o endereço configurado e um IP alternativo; troca
   de IP, restart, atualização e cache antigo.

Só a evidência acima decidirá se a correção será na receita da UI, endereço,
proxy, inicialização, distribuição de arquivos ou outro componente. Não
resolver às cegas aumentando timeout, desativando validação TLS ou liberando
CORS para qualquer origem.

## 3. Correções do funcionamento atual

### 3.1. Contrato de status e apresentação de falhas

- Preservar o contrato compacto, de uma linha, de `--status-json`. Separar
  mensagens humanas em stderr; não misturá-las ao payload.
- Tornar leitores tolerantes à saída completa válida e ao formato antigo com
  mensagens anteriores. Validar objeto, campos e limites; não interpretar
  qualquer fragmento de log como status.
- Retornar resultados independentes por servidor e plataforma, com hora de
  coleta, erro sanitizado e origem. Começar mantendo schema 1 compatível;
  a futura extensão por instância será versionada/aditiva.
- Estabelecer prazos: orçamento inicial de até 15 s para a atualização geral,
  sondagens simples com orçamento menor; diagnóstico profundo fica separado.
  Medir nos ambientes suportados e ajustar esses valores explicitamente.
- Em timeout, encerrar e recolher os processos de leitura iniciados pela
  consulta; não deixar subprocessos se acumularem a cada Atualizar.
- Coletar CPU, memória e disco sem depender de DSpace, Koha, Internet ou Docker.
- Após uma falha, manter o último valor conhecido com hora e marca de
  desatualizado. Sem leitura anterior, mostrar “Não foi possível consultar”
  e “Ver erro”, sem spinner ou reticências permanentes.
- Um erro na consulta de atualização do painel não esconde estado dos serviços.
- DSpace desconhecido continua oferecendo “Consultar novamente”, “Diagnóstico”,
  “Logs” e acesso ao planejamento de remoção quando a instalação é identificável.
  Estado desconhecido nunca significa ausente nem autoriza reinstalar sobre dados.
- Exibir no diagnóstico o caminho do instalador realmente chamado, sua versão,
  versão do painel e do adaptador, para detectar atualização de só uma cópia.

**Aceite:** DSpace presente, ausente, parado, estado ilegível, Docker indisponível,
sem Internet, retorno inválido e timeout não deixam a aba Geral vazia. Restaurar
a fonte de dados e clicar Atualizar recupera a tela sem reinstalação.

### 3.2. Final da instalação sem interrupções desnecessárias

O novo comportamento vale para Koha, Tainacan e DSpace:

```text
Instalação concluída — Repositório Municipal · DSpace
Endereço local: http://192.168.1.50:8100

[Abrir site] [Acesso administrativo] [Ir para a instância]
```

Se faltar administrador, a tela informa “Administrador ainda não configurado”
e oferece o botão correspondente. Não abre automaticamente outro assistente.
Tainacan mantém instalação WordPress fechada e suas credenciais geradas até
a pessoa configurar as próprias; DSpace não cria uma senha padrão conhecida.

Endereço, HTTPS, endereço gratuito, nuvem e agendamento ficam nos menus
permanentes, com os mesmos dados e rotinas que já existem. Remover os prompts
automáticos não desliga serviços ou agendas já configurados. Os registros
antigos `setup` podem ser mantidos como histórico; não devem reabrir um lembrete
automático ao atualizar, retomar instalação ou reentrar no painel.

Instalação nova sugere endereço local e porta. Domínio é uma configuração
opcional de Endereços; não precisa ser perguntado para concluir um teste local.

### 3.3. Idiomas

Separar quatro conceitos na interface:

| Configuração | Onde fica | Efeito |
|---|---|---|
| Idioma do painel Nexus | Preferências do painel | Textos e menus do painel |
| Idioma público da instância | Instância → Idiomas e aparência | Padrão e seletor público do aplicativo |
| Idioma da conta | Acesso administrativo/perfil | Preferência daquela pessoa, quando suportada |
| Idioma do conteúdo | Metadados do próprio aplicativo | Não é alterado ao trocar a interface |

- DSpace: foram encontrados **37 catálogos `.json5`** nas fontes locais da
  versão fixada, incluindo `pt-BR`, `pt-PT`, francês, alemão, italiano, árabe,
  chinês tradicional e outros. Presença do arquivo não garante tradução 100%.
- Gerar catálogo a partir da versão empacotada, com código real, nome nativo,
  idioma disponível/ativo e fallback. O seletor aceita pesquisa por nome.
- Resolver explicitamente o mapeamento entre códigos da UI e da conta, como
  `pt-BR` e `pt_BR`, conforme o contrato real do DSpace. Não adivinhar aliases.
- Retirar a lista tripla de `routines/dspace.py`, `runtime.py` e `NexusAdmin.java`.
  Validar contra a mesma capacidade publicada pela receita.
- Modificar o helper Java exige nova imagem/receita e caminho de atualização
  da instalação existente; só alterar o menu faria o backend continuar recusando.
- Koha continua usando os pacotes disponíveis para sua versão. WordPress e
  Tainacan usam os respectivos pacotes/locale. Não inventar “pacote universal”.
- Preferência escolhida para o painel não se propaga silenciosamente a todas
  as instâncias; uma nova instalação pode recebê-la apenas como sugestão.

**Aceite:** criar administrador DSpace com idioma além dos três atuais;
conferir a preferência persistida, interface, recarregamento, idioma público,
fallback e uma língua RTL. Não afirmar tradução completa de conteúdo.

### 3.4. Remoção visível e utilizável

Local único: **Instância → Manutenção → Remover instância**, também alcançável
pelo menu de ações do cabeçalho. A ação abre um plano, não apaga ao clicar.

```text
Remover “Repositório Municipal” — DSpace

(•) Remover os serviços e manter os dados para recuperação
( ) Remover os serviços e apagar os dados desta instância

Dados afetados: [...]
Backups existentes: mantidos
Recursos compartilhados: [...]
[Voltar] [Revisar remoção]
```

- Reaproveitar `Operations.remove` e `tainacan-uninstall`, corrigindo sua
  disponibilidade, estados finais e recuperação de interrupções.
- Instalação incompleta ou quebrada não pode exigir uma aplicação saudável
  apenas para mostrar o plano de remoção.
- Desligar/reconciliar as tarefas e publicações da instância. Conjunto com
  participantes fixos fica suspenso com motivo até ser editado; não alterar
  silenciosamente sua lista para excluir o membro removido.
- Apagar dados exige confirmação explícita da instância e verifica propriedade
  de cada recurso imediatamente antes de removê-lo.
- Oferecer backup prévio e manter o fluxo normal com backup verificado. Para
  dados irrecuperáveis que impeçam backup, prever uma opção avançada separada
  de exclusão sem backup, com confirmação específica; nunca um fallback
  automático após falha. Não apagar recursos cuja propriedade seja incerta.
- Preservar Docker, Apache, bancos compartilhados, certificados, túnel, nuvem,
  imagens referenciadas e backups de outras instalações.
- “Manter dados” deixa um registro recuperável visível, não uma nova instância
  vazia nem diretórios órfãos invisíveis.
- Para Koha, aproveitar a remoção da instalação nativa específica, com análise
  de dependências; nunca tratar remover uma biblioteca como desinstalar os
  pacotes e o banco do servidor inteiro.

## 4. Organização final da interface

Três níveis: servidor, instância e centrais. Cada função tem uma única fonte
de configuração, mesmo quando há dois caminhos para alcançá-la.

```text
📊 Painel geral
➕ Adicionar instância

Instâncias
  ▾ Biblioteca Central · Koha
      Visão geral e acesso
      Ferramentas da biblioteca
      Acesso administrativo
      Endereços
      Idiomas e aparência
      Backups
      Agendamentos
      Manutenção
  ▸ Museu Municipal · Tainacan
  ▸ Produção Científica · DSpace

Servidor
  Central de backups
  Central de agendamentos
  Endereços e portas
  Segurança e acesso
  Infraestrutura compartilhada
  Atualizações
  Diagnóstico do servidor
  Preferências do painel
  Sobre e suporte
  Reiniciar servidor
```

- O painel geral mostra recursos do servidor e um resumo compacto de cada
  instância: nome, aplicativo, estado, última verificação e acesso.
- O clique abre a visão detalhada da instância. Não manter simultaneamente
  uma antiga tela Plataformas e outra tela com os mesmos botões/indicadores.
- Detalhes de Koha, Tainacan e DSpace deixam de depender de três abas fixas:
  o número de instâncias é variável. No geral, resumo; na instância, detalhes.
- As ferramentas específicas do Koha continuam disponíveis, agrupadas sem
  duplicar a lateral inteira para cada biblioteca aberta.
- Tainacan mostra WordPress/acervo e Eventos quando habilitado. WordPress,
  Tainacan e Nexus Eventos da mesma instalação pertencem à mesma instância
  operacional; não transformar o plugin Eventos em outra instalação.
- DSpace reúne serviços, comunidades/coleções como acesso ao aplicativo,
  administrador, idiomas, endereços, backup, atualização e manutenção.
- Backups/agendas abertos dentro de uma instância são a central filtrada por
  seu ID. Alterações e histórico aparecem imediatamente nos dois acessos.
- A seleção sempre mostra **nome + sistema**, não apenas “DSpace”. O nome pode
  ser alterado sem renomear bancos, volumes, usuários ou diretórios.
- Atalhos como `b` e `s` levam às centrais; ferramentas específicas usam a
  instância selecionada. Sem alvo inequívoco, pedem seleção, nunca usam a primeira.
- Em 80×24, lateral recolhível, formulários verticais e botões com quebra;
  em 160×48, grade. Operação, erro e confirmação não dependem só de cor/emoji.
- Usar os componentes Textual atuais; não trocar framework ou recriar todas
  as telas para introduzir a navegação por instância.

## 5. Adicionar instância e escolher portas

Fluxo final:

1. Escolher aplicativo e nome; mostrar apenas drivers realmente disponíveis.
2. Escolher forma de instalação entre as suportadas para aquele aplicativo.
3. Verificar SO, arquitetura, disco, memória e dependências; informar custo
   adicional de compilar DSpace quando as imagens ainda não estiverem prontas.
4. Sugerir endereço local e porta(s) pública(s), mostrando disponibilidade.
5. Revisar plano com recursos e capacidade; confirmar a instalação.
6. Executar fases com progresso, registro persistente e retomada explícita.
7. Verificar aplicação e mostrar conclusão; nenhuma sequência de prompts
   de domínio, backup ou nuvem é disparada.

Modalidades iniciais:

| Aplicativo | Driver aproveitado | Escolhas que exigem trabalho posterior |
|---|---|---|
| Koha | Nativo, com instâncias do pacote Koha | Koha em Docker requer receita e ciclo de vida próprios |
| Tainacan/WordPress | Docker | Instalação nativa requer driver próprio |
| DSpace | Docker | Instalação nativa requer driver próprio |

Não apresentar “Docker ou bare metal” como uma escolha funcional para todos
antes de existir o respectivo driver. Docker é a recomendação das receitas
Tainacan/DSpace; o Koha existente continua nativo. AtoM fica para outra etapa,
aproveitando estes contratos quando for implementado.

Exemplo de porta:

```text
Porta de acesso: [8100]
Em uso por Produção Científica · DSpace
Sugestão disponível: 8101   [Usar sugestão]
```

- Porta disponível significa possibilidade de escuta, não acesso garantido
  por firewall, roteador, VPN ou Windows/WSL.
- Considerar endereço de bind, protocolo, IPv4/IPv6, wildcard, reservas do
  painel, escutas reais e publicações Docker. Não identificar dono por palpite.
- Revalidar/reservar imediatamente antes da aplicação; o erro real de bind
  também precisa ter recuperação, porque serviços externos não obedecem à trava.
- Cancelamento ou falha libera somente reservas daquela operação.
- Koha pode requerer OPAC e Staff. Tainacan tem acesso web WordPress. DSpace
  apresenta uma origem pública com `/` e `/server`; PostgreSQL e Solr continuam
  privados. Portas internas ficam em Avançado e são alocadas automaticamente.
- Diferentes domínios podem compartilhar 443 pelo proxy. Isso não equivale a
  duas aplicações independentes disputarem o mesmo bind IP:porta.
- Primeira instalação pode sugerir portas atuais (Koha 80/8080, Tainacan 8090,
  DSpace 8100), apenas se compatíveis com o que já está em execução.

## 6. Contrato técnico por instância

### 6.1. Registro e contexto

Registro versionado em diretório privado do Nexus, com um documento JSON por
instância, escrita atômica e travas. Reaproveitar armazenamento local e biblioteca
padrão; não introduzir banco ou serviço remoto apenas para cadastrar instâncias.
Índices de listagem são derivados, não uma segunda fonte de verdade.

Campos mínimos:

- `schema`, `id` imutável, `name`, `application`, `driver`;
- referências de estado/configuração existentes e modo legado/novo;
- versão instalada e identidade da receita/imagens;
- referências de recursos e endpoints;
- estado desejado, fase de operação, observação e hora;
- origem da descoberta e nível de gestão: gerenciada, legada adotada, externa;
- capacidades de operação; referências de segredos, nunca senhas em status.

Separar **existência/ciclo de vida**, **serviços** e **saúde**. “Container rodando”
não basta para “site funcional”; “consulta falhou” não significa “não instalado”.
Estados devem representar provisionamento, pronta, parada, degradada,
remoção em andamento e dados preservados.

Toda operação recebe um `InstanceContext` resolvido de ID explícito. Caminhos,
portas, bancos, namespaces de índice e nomes de projeto vêm desse contexto.
Nenhuma tarefa destrutiva pode escolher automaticamente o primeiro ID encontrado.

Comandos antigos continuam dirigidos à instalação legada designada quando isso
for inequívoco. O novo protocolo transporta o ID com validação. Evitar depender
somente de variável de ambiente: hoje o installer fixa `INSTANCE="library"`.

### 6.2. Propriedade e recursos compartilhados

| Recurso | Pertence à instância | Gestão compartilhada |
|---|---|---|
| Banco, volumes, configuração, chaves da aplicação | Sim | Inventário e operações pelo driver |
| Projeto/rede Compose e containers | Identidade própria | Docker e allocator de redes |
| Site, domínio, origem e política de acesso | Vínculo da instância | Proxy, certificados, túneis e firewall |
| Backup e retenção | Plano com participantes explícitos | Orquestração, cofre, conexões e histórico |
| Tarefa agendada | Instância ou conjunto identificado | Execução cron e inventário central |
| Pacote Koha, Apache/MariaDB do host | Pode atender várias bibliotecas | Atualização/reinício informa todo o alcance |
| Imagem Docker por versão | Pode ser reutilizada | Não remover enquanto houver usuários ou recuperação dependente |

Evoluir `owned.tsv` e suas funções com compatibilidade, associando cada
consumidor ao ID da instância. Não manter dois inventários com autoridade
conflitante. Recursos preexistentes conservam sua procedência.

Locks: plano/conjunto, depois instâncias em ordem estável de ID, depois recursos
compartilhados por períodos curtos. Coleta de status não deve esperar uma cópia
de banco terminar. Compilação e cópia não seguram uma trava global do painel.
Escrever diário de operação antes de mutações externas relevantes; reconciliar
interrupções em vez de supor que arquivos e Docker mudaram atomicamente juntos.

### 6.3. Drivers específicos

**Tainacan:** parametrizar `KEI_TAINACAN_ID`, projeto, rede, volumes, diretórios,
portas, WP-CLI, backup, credenciais e cópia de restauração. As constantes
`kn-tainacan` e `kn-tainacan-rt` não podem identificar todas as instalações.
Cada teste de restauração recebe identidade temporária própria e não dispara
e-mail, publicação, webhooks ou cron reais.

**Koha:** aproveitar a identificação de sites nativos. Auditar importação,
busca/índices, enriquecimento, aparência, mensagens, relatórios, credenciais,
agenda e restauração para eliminar alvo global implícito. Serviços/pacotes
compartilhados continuam sendo operações do servidor, com escopo visível.
Ter duas bibliotecas nativas não permite prometer duas versões independentes
do mesmo pacote Koha.

**DSpace:** remover pressupostos de singleton em `PROJECT`, `LABELS`, diretório
terminado em `dspace`, nomes de volume, catálogo, backup e restauração. Cada
instância tem PostgreSQL, Solr, backend, UI, segredos, limites e portas próprios.
Imagens da mesma receita podem ser reutilizadas. Atualização e recuperação
devem resolver a receita da instância, não apenas a versão mais recente do painel.

### 6.4. Distribuição faz parte da implementação

As alterações precisam funcionar com `config.sh` instalado isoladamente, e não
somente com o checkout inteiro ao lado. Preparar módulos/catálogos necessários
no momento adequado; status deve reutilizá-los offline.

Atualizar, quando aplicável, bundle, arquivos copiados para imagens, checksums,
versões, manifestos e adaptadores antigos. Testar o pacote extraído sem acesso
ao checkout. O arquivo `contract.json` que faltava no kit do PR #356 demonstra
por que testar apenas módulos diretamente do repositório é insuficiente.

## 7. Backups e agendamentos: uma configuração, duas entradas

- Central permite selecionar instâncias por ID, incluindo duas do mesmo tipo.
  Dentro da instância, abre com ela selecionada.
- Reutilizar captura/restauração de cada aplicativo. Criar uma fachada geral
  sobre os motores atuais; a lógica de conjuntos não deve depender da presença
  de DSpace, como ocorre em parte de `operations.py` hoje.
- Preservar leitores dos formatos 1 e 2. Introduzir manifesto novo apenas
  para a identidade por instância, com versão explícita e compatibilidade testada.
- Novo conjunto: `manifest.json` e membros separados por ID, contendo origem,
  tipo, versão/receita, intervalo de captura, checksums e exigência de segredos.
  Repetir nomes visíveis ou tipos não gera sobrescrita de arquivos.
- Detectar formato pelo conteúdo. Antes de restaurar, mostrar mapeamento de
  cada membro para uma instância existente ou nova, compatibilidade e efeito.
- Nunca restaurar silenciosamente sobre a primeira instalação do mesmo tipo.
- Manter criptografia existente e sua descrição correta. Não chamar banco
  legado em texto claro de criptografado só porque o pacote contém um segredo
  cifrado. Conjuntos novos destinados à nuvem mantêm cifragem integral.
- Lista de participantes é fixa por plano. Instalar uma quarta instância não
  muda automaticamente as agendas anteriores.
- Agendas individuais e conjuntas aparecem na mesma central e guardam fuso,
  expressão, próxima execução, resultado de captura, cópia e retenção.
- Reaproveitar cron. Gerar apenas entradas próprias, sem reescrever tarefas
  manuais ou do pacote. WP-Cron continua identificado como mecanismo interno.
- Operações incompatíveis na mesma instância se serializam; instâncias
  independentes podem operar simultaneamente conforme recursos disponíveis.
- Não podar a última cópia boa após captura parcial, falha de upload ou
  problema de conexão. Exibir resultado por membro e por fase.
- Conjunto não promete transação única entre aplicações. Falha de um membro
  não deve ser escondida como “backup completo”.
- Clonagem restaura dados com novo ID, sem reutilizar publicação/identidade do
  broker, e-mail, webhooks ou agendas da origem automaticamente.
- Documentar e testar as imagens necessárias para recuperação DSpace. Pacote
  de dados não contém automaticamente imagens locais; reutilização/transporte
  das imagens ou distribuição por digest precisa ter caminho funcional.

## 8. Endereços, segurança e acesso web

**Dentro da instância:** endereço local, domínio próprio, endereço gratuito
quando suportado, URL canônica, visibilidade e restrições específicas.

**Na central:** mapa de portas e endpoints, hosts, certificados, túneis e seus
consumidores; VPN, firewall e Fail2ban do servidor.

- Aplicar configuração pelo gestor compartilhado com plano e validação.
  Reload do proxy mantém sites não envolvidos.
- Troca de endereço adapta o aplicativo e verifica acesso público; conservar
  configuração anterior para retorno se falhar. Não perder personalizações.
- Subdomínios são o padrão entre instalações independentes. Usar `/dspace` ou
  `/koha` exige suporte real; não impor um prefixo genérico a todas as aplicações.
- Broker atual representa serviços por tipo da instituição. Múltiplas
  instâncias exigem endpoints, armazenamento e capabilities compatíveis, com
  associação explícita de ID e hostname.
- Preservar os endereços gratuitos já existentes. Remover um vínculo não
  remove túnel ou hostname de outra instalação.
- Sem capability nova, instalações continuam funcionando localmente e com
  domínio próprio; a opção gratuita explica a indisponibilidade específica.
- Publicação do broker e migrações de produção são entregas operacionais
  separadas, documentadas. Código mesclado não comprova serviço publicado.
- Login continua próprio de cada aplicativo nesta etapa. Portal, busca
  federada e Keycloak permanecem fora deste trabalho.

## 9. Migração sem reinstalar nem mover dados

1. Inventariar o servidor real em modo somente leitura: aplicações, arquivos,
   proprietários, portas, proxy, cron, backups, versões e recursos preexistentes.
2. Comparar esse inventário com os registros atuais; apresentar adoção proposta
   de cada instalação, com conflitos explícitos.
3. Registrar IDs estáveis e referências aos nomes reais sob trava, com diário
   de migração. Não renomear volumes, bancos, usuários ou redes por estética.
4. Usar os drivers legados com contexto explícito enquanto se adapta cada tarefa.
   Objetos externos não passam a ser gerenciados apenas por terem nome parecido.
5. Preservar mapeamento das agendas, histórico e arquivos antigos. Conferir que
   cada entrada gerenciada continua apontando para a mesma instalação.
6. Reexecutar migração sem duplicar instâncias; retomar após interrupção.
7. Verificar dados e endereços antes de permitir a primeira segunda instalação.

A atualização do painel, por si só, não move dados, troca portas, refaz contas,
publica sites ou recria agendas. Registro conhecido pode ser mostrado mesmo
quando um serviço está indisponível.

Reversão do cadastro só é simples antes de usar recursos novos. Depois de criar
uma segunda instância, não prometer downgrade automático para versão que só
conhece singleton; oferecer recuperação documentada do registro/configuração.

## 10. Sequência recomendada: dez PRs com resultados verificáveis

Os números abaixo são etapas propostas, não números já abertos no GitHub.
Conferir a main e as correções ainda em PR antes de iniciar cada etapa.

| Etapa | Entrega | Critério principal |
|---|---|---|
| 1 — Status e recuperação das telas | Corrigir JSON, leitores, timeout, erros visíveis, isolamento dos cartões e ferramentas em estado desconhecido | DSpace instalado deixa de quebrar painel; falha de um coletor não apaga o restante |
| 2 — DSpace acessível | Diagnosticar/corrigir login em branco; testar IP de rede, navegador, proxy, assets e retomada | Abrir endereço local, entrar, depositar, buscar e recarregar após restart |
| 3 — Fluxo simples, idiomas e remoção | Retirar pós-instalação automático; catálogo de idiomas; entrada de remoção e tratamento de instalação quebrada | Sem prompts de domínio/nuvem; idioma adicional funciona; remoção de alvo identificado preserva outras aplicações |
| 4 — Registro e contexto | IDs, descoberta/adoção, capacidades, estados, compatibilidade CLI e migração idempotente | Instalações antigas registradas sem mudança de dados, portas, URLs ou agendas |
| 5 — Recursos por instância | Donos/consumidores, bindings, reserva de portas, proxy, redes, locks e distribuição dos módulos | Conflitos detectados e cancelamento limpo; recursos compartilhados preservados |
| 6 — Backups e agendas por ID | Seleção genérica, manifesto novo, leitores antigos, planos fixos, destino explícito, migração das tarefas | Restaurar membro no destino escolhido e editar agenda pela central ou instância dá o mesmo resultado |
| 7 — Tainacan múltiplo e navegação nova | Driver completo, Adicionar instância, lateral dinâmica, centrais filtradas e duas instalações reais | Criar, usar, recuperar e remover uma sem afetar a outra |
| 8 — Koha múltiplo | Contexto em todas as ferramentas, sites nativos, backup, endereços, índices e remoção específica | Duas bibliotecas com ferramentas/dados distintos; ações compartilhadas mostram alcance |
| 9 — DSpace múltiplo | Projetos, bancos, Solr, URLs, idiomas, recuperação e atualização por instância | Duas instalações reais independentes e recuperação/remoção seletiva |
| 10 — Publicação e consolidação | Broker multi-instância compatível, domínios seletivos, migração final, documentação e prova de coexistência/reboot | Endereços/recursos não se cruzam; rotas antigas preservadas; roteiro final reproduzível |

As etapas 1–3 entregam melhorias utilizáveis antes da arquitetura nova. As
etapas 4–6 preparam o contrato comum preservando o uso atual. A etapa 7 habilita
o primeiro fluxo completo de múltiplas instâncias; 8 e 9 reutilizam o mesmo
modelo. Não oferecer criação adicional por um driver ainda não adaptado.

Se a investigação do login mostrar uma correção pequena, ela pode acompanhar
o PR 1. Se exigir mudança de receita ou de proxy, conservar o PR 2 separado.
Não misturar a migração de registro com a correção emergencial do status.

## 11. Matriz de validação e evidências

Testes por mudança, aproveitando as suítes existentes; não exigir rodadas
repetidas sem alteração ou falha nova.

### Contrato e distribuição

- Saída real do serializador com DSpace presente → `Bridge.status`,
  `nexus_core` e leitor Windows. Incluir saída legada, ruído permitido,
  fragmentação, JSON inválido, exceção e timeout.
- Painel/instalador com versões diferentes e diagnóstico de cópia desatualizada.
- Execução a partir de pacote instalado sem checkout; cache offline e
  preparação de dependências no fluxo correto.

### Aplicações e navegador

- Servidor vazio, só uma plataforma e as combinações atuais.
- DSpace por IP da rede e por hostname; `/`, `/login`, recursos JS/CSS,
  `/server/api`, autenticação, envio de arquivo, item público/privado e busca.
- Navegador em outro cliente/namespace de rede: não validar tudo só com
  resolução/Host especiais no processo do servidor.
- Nova instalação, instalação atualizada, fase interrompida, container parado,
  Docker reiniciado, disco cheio/OOM quando relevante e mudanças de endereço.
- Idiomas do painel/aplicativo/conta com independência e código correto.

### Múltiplas instâncias e recursos

- Duas do mesmo aplicativo, não apenas uma de cada tipo.
- Enquanto A instala/para/atualiza/restaura/remove, B permanece acessível e
  seus dados, contas, jobs, URLs, regras e volumes são conferidos.
- Disputa de porta entre criação paralela e processo externo, escuta wildcard,
  IPv6, cancelamento e reservas após interrupção.
- Remoção mantendo dados, apagando dados, falha no meio e recurso preexistente
  ou compartilhado. Nada de limpeza global de Docker.
- Backup individual, conjunto com tipo repetido, formato antigo, falta de
  chave, upload falho, retenção e restauração com destino explícito.

### Interface e execução real

- 80×24 e 160×48; teclado e clique; erro recuperável; ID/nome visível em toda
  confirmação; atalhos não escolhem outra instância por acidente.
- Ubuntu 24.04, Debian 12 e Debian 13, conforme suporte declarado. Diferenciar
  teste real de aplicativo, teste simulado do painel e validação no servidor.
- Reinício real de VM separado de restart do Docker/containers. Conferir
  persistência, autostart, rede, portas, agendas e coleta de status depois do boot.
- Se WSL for usado, verificar também inicialização da distro, acesso pela rede
  Windows e firewall; não atribuir resultado de VM Linux automaticamente ao WSL.

Cada PR informa commit validado, comandos, testes executados, falhas e limites.
Capturas devem incluir telas de erro e instalação real, além de demonstração.
CI verde não equivale a teste no servidor de Paulo; o roteiro de validação final
deve permitir que ele teste quando puder, sem esconder pendências.

## 12. Informação do servidor que precisaremos na execução

Não é necessária para aprovar ou entender este plano. Para fechar a causa do
login em branco e validar a correção em uso, coletar de forma assistida:

- versão/caminho do painel e `config.sh`, comando usado para abrir e tipo de
  ambiente (Linux/VM/WSL);
- status e erro do coletor, com saída sanitizada;
- URL configurada versus URL acessada, interface de rede e listeners;
- estado/logs limitados de UI, backend, PostgreSQL, Solr e proxy;
- erros do console e requisições falhas, sem dados de login;
- resultado após restart e, separadamente, após reboot real.

Preparar um botão/roteiro de diagnóstico que reúna isso sem alterar serviços
e sem copiar configuração privada. Não exigir que o usuário saiba Docker ou
tenha que reconstruir a investigação manualmente.

## 13. Mapa dos arquivos a trabalhar

| Área | Implementação atual a reaproveitar/adaptar |
|---|---|
| Status | `installer`: `kei_status_json`, `kei_platforms_json`, `kei_dspace_json`; `panel/kei_panel/bridge.py`; `nexus_core/status.py`; `windows/KohaEasy.Core.psm1` |
| Telas e navegação | `panel/kei_panel/views/dashboard.py`, `views/platform.py`, `screens/main.py`, `platforms.py`, `menus.py`, `app.py` |
| Pós-instalação | `panel/kei_panel/routines/setup.py`, `routines/dspace.py`, chamadas de `maybe_start` e estado de setup do instalador |
| DSpace e idiomas | `platforms/dspace/runtime.py`, `operations.py`, `images/NexusAdmin.java`, `images/ui.Dockerfile`, `release.json`, `tools/dspace_images.py` |
| Recursos | `installer`: `kei_owned_*`, `kei_proxy_*`, `kei_docker_network_*`, rotinas Tainacan e variáveis de instância Koha |
| Backup e agendas | `panel/kei_panel/backup_center.py`, `schedules.py`, `routines/backup_set.py`, adaptadores do instalador e `platforms/dspace/backup.py`/`operations.py` |
| Endereço gratuito | `broker/src/api.ts`, migrações, testes e adaptador do instalador |
| Entrega verificável | `tools/dspace_build_bundle.py`, `build-inputs.zip`, checksums do instalador, suítes do painel, testes reais e workflows |

Novos módulos comuns só devem ser extraídos na medida em que eliminem os
alvos globais e permitam reutilização concreta. Manter o script de entrada e
os motores úteis existentes, sem uma reescrita total do projeto.
