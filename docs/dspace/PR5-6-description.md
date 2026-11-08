Integra as operações do DSpace às centrais existentes do koha.nexus (1.5.184). Agora há planos individuais e conjuntos explícitos com Koha/Tainacan, cópia cifrada na nuvem, retenção e restauração seletiva, preservando o formato e os participantes dos planos antigos.

Reúne as etapas previstas para PR5 e PR6: endereço/HTTPS, extensão opcional do broker, atualização controlada da receita 3 para 4 do DSpace 10.1 e remoção com dados mantidos por padrão. Operações destrutivas exigem confirmação e salvaguardas; serviços e credenciais compartilhados são preservados.

Validação local: 137 testes Python, 131 de painel/documentação, 37 Bash; broker com 72 testes unitários e 30 checks e2e locais. A CI acrescenta serviços DSpace reais, GPG/rclone e uma atualização com imagens históricas reais. Conferir os resultados do commit atual antes de mesclar.

Limites: DSpace experimental, amd64; sem teste no servidor do usuário ou reboot de VM. HTTPS usa certificado existente/proxy externo; OAI-PMH não é publicado pelo proxy gerenciado nesta etapa. Broker, migração remota e imagens não foram publicados. Detalhes, recuperação e pendências em `docs/dspace/PR5-6-operations.md`.

## Revisão e correção da CI (08/11/2026)

Commit de código validado: `ca99aa6`; todos os checks verdes em pull_request e push (push após reexecutar dois jobs que falharam por infraestrutura: reinício do Docker no runner e download do wordpress.org). `publish` pulado por desenho (só `workflow_dispatch` na main).

Causas corrigidas: (1) resultados do `--task` lidos de stdout em vez de stderr: o aceite falhava com `KeyError: 'complete'` e todo plano agendado conjunto com DSpace teria falhado; (2) recibo do guarda de esquema amarrado à imagem: a receita 4 nunca iniciava após atualizar, agora regravado com rollback do recibo anterior; (3) cron gravado para `config.sh` inexistente: agora recusado antes de gravar. Agendamentos passam a mostrar última execução e status dos planos DSpace. Limitação avisada na confirmação: após atualizar, pacotes da receita 3 não são restauráveis nesta instalação.

Detalhes, testes reais × simulados e pendências: `docs/dspace/CONTINUIDADE-PR5-6.md`.
