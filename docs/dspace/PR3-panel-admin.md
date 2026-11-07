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

Passaram localmente 65 testes de imagens/runtime (Python 3.9), 16 cenários de
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
