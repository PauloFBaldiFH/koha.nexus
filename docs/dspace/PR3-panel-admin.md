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

Em andamento. Registrar somente resultados efetivos, distinguindo simulação de
painel, integração real em CI e o que depende do servidor do Paulo.
