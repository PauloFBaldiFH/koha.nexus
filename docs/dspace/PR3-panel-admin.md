# PR 3 — painel e acesso administrativo do DSpace

Base: #352 mesclado, versão 1.5.181. Entrega proposta: 1.5.182.

Escopo: grupo DSpace com instalação/retomada e manutenção; resumo somente na aba
DSpace do Painel de Controle; criação de administrador ou senha nova, por entrada
protegida; primeiros passos agora/depois e idioma da conta. Reaproveita tarefas,
confirmações, componentes e navegação existentes, sem tocar no Koha/Tainacan.

O catálogo de imagens revisado continua obrigatório. Antes dele, o painel explica
a indisponibilidade e não instala dependências. Docker e Apache têm consentimentos
próprios. O URL é explícito; domínio gratuito e HTTPS gerido ficam no PR 6.

A receita 3 acrescenta um adaptador Java que usa os serviços oficiais de EPerson
 e Group do DSpace, após o guard de esquema. Criação recusa qualquer e-mail já
existente; troca de senha aceita apenas administrador habilitado. A senha é
capturada duas vezes no painel, chega ao Python no ambiente de uma única tarefa
e é removida desse ambiente antes de chamar Docker; Java só a recebe em stdin.
Não se usam argumentos de senha, SQL de hash próprio ou contas padrão.

Backups/restauração individuais pertencem ao PR 4, conjuntos/agendas ao PR 5 e
endereço/atualizações ao PR 6. O assistente informa essas limitações e mantém os
menus permanentes. Nenhuma publicação de imagens, broker ou produção é automática.

## Validação

Em andamento. As imagens da receita 3 passaram build/smoke nos três serviços.
O primeiro teste administrativo real foi recusado; o adaptador passa agora a usar
o bootstrap oficial de `ScriptLauncher` (`DSpaceKernelInit`, `start` e `destroy`),
além do guard de esquema anterior. A correção passou pela conta real: leitura de administradores, criação, recusa de
conta duplicada, nova senha e login no Chromium. A rodada
[42388469231](https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42388469231)
parou no formulário por uma etapa padrão do upstream: aceitar o termo de uso no
primeiro acesso. O roteiro passa a aceitar esse termo pela UI **somente** para a
conta descartável da CI; nada é aceito pelo instalador em nome de uma pessoa real.
Depósito, download e privacidade ainda aguardam a rodada completa.

Passaram localmente 66 testes de imagens/runtime (Python 3.9), 16 cenários de
navegação (oito combinações de plataformas, nas duas larguras) e 16 casos de
confirmação/conta/protocolo. A seleção existente do painel encontrou expectativas
antigas de dois grupos/cartões: atualizadas para incluir DSpace, mantendo as
asserções de Koha/Tainacan. Manual e traduções: 27 testes passaram.

As cinco capturas em `pr3-captures/` são simulações explícitas do painel,
em português; não são prova de instalação real. Em 80 colunas, o resumo do
DSpace usa uma coluna para preservar os botões Abrir/Copiar. O estado não é
repetido na tela de ferramentas.

O teste integrado usa contas/documentos descartáveis, login e depósito pelo
Chromium, download com SHA-256 e acesso anônimo negado após restrição. Não salva
traces, cookies, armazenamento do navegador ou senha. Só a conclusão efetiva da
CI pode ser registrada como aprovação desse fluxo.


A rodada [42389864883](https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42389864883)
chegou ao formulário com o arquivo enviado. O roteiro deixa de exigir um clique
em Salvar quando não há alterações pendentes, mas continua exigindo que a API
confirme o título editado no navegador antes do depósito. Também identifica cada
fase do navegador e os estados dos botões, sem registrar valores dos campos.
As operações administrativas recusam configuração privada alterada antes de
iniciar qualquer contêiner ou transmitir a senha; teste negativo específico passou.

## Resultado comprovado na CI (commit 1cf365b, 2026-11-07)

O job `installation` passou nas execuções
[42415203648](https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42415203648) (push) e
[42415207935](https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42415207935) (pull request),
com serviços reais e Chromium real em um runner descartável:
instalação, ausência de administrador padrão, criação do administrador pelos serviços
oficiais, troca de senha (a antiga é recusada), senha ausente de `db-password`,
`last-error.log`, `local.cfg`, `state.json` e `compose.json`, login no navegador,
aceite do termo pela conta descartável (confirmado pela API), edição de metadados
persistida, upload, depósito pelo navegador com item arquivado, download anônimo com
SHA-256 igual ao original, página pública, restrição das políticas, download do
administrador com o mesmo SHA-256, API e página anônimas sem o item restrito e
descoberta anônima sem o item.

Na mesma cabeça passaram as regressões de Koha, Tainacan e infraestrutura
compartilhada: `koha-set`, `tainacan`, `events`, `apache`, `system` e `engine`
(Debian 12/13, Ubuntu 24.04), painel em Python 3.9 e 3.13 e o navegador do Tainacan.

Correções desta rodada:
- O termo de uso é aberto em `/info/end-user-agreement` e aceito pela caixa oculta do
  upstream; a decisão pelo endereço ou pela visibilidade disputava o redirecionamento.
- O depósito espera o rodapé liberar o botão; se continuar ocupado, recarrega o mesmo
  item salvo e exige o arquivo e o botão disponíveis.
- **Correção de privacidade:** a UI guardava páginas renderizadas no servidor para
  robôs (navegadores sem interface entram nesse grupo) por até um dia; um item
  restrito depois de visitado continuava legível nesse HTML. Os caches SSR de robôs e
  anônimos ficam desligados no compose gerado, com teste unitário.
- Os diálogos do painel não falham mais quando respondidos antes do foco inicial
  (corrida que derrubava testes da central de backup em Python 3.9/3.13).

Limites: tudo acima é CI em runner descartável, sem reinício de máquina; nada foi
testado no servidor do Paulo. Desligar o cache SSR troca desempenho por privacidade
em acervos muito visitados. Nenhuma imagem ou serviço foi publicado.
