Integra as operações do DSpace às centrais existentes do koha.nexus (1.5.184). Agora há planos individuais e conjuntos explícitos com Koha/Tainacan, cópia cifrada na nuvem, retenção e restauração seletiva, preservando o formato e os participantes dos planos antigos.

Reúne as etapas previstas para PR5 e PR6: endereço/HTTPS, extensão opcional do broker, atualização controlada da receita 3 para 4 do DSpace 10.1 e remoção com dados mantidos por padrão. Operações destrutivas exigem confirmação e salvaguardas; serviços e credenciais compartilhados são preservados.

Validação local: 136 testes Python, 130 de painel/documentação, 18 Bash; broker com 72 testes unitários e 30 checks e2e locais. A CI acrescenta serviços DSpace reais, GPG/rclone e uma atualização com imagens históricas reais. Conferir os resultados do commit atual antes de mesclar.

Limites: DSpace experimental, amd64; sem teste no servidor do usuário ou reboot de VM. HTTPS usa certificado existente/proxy externo; OAI-PMH não é publicado pelo proxy gerenciado nesta etapa. Broker, migração remota e imagens não foram publicados. Detalhes, recuperação e pendências em `docs/dspace/PR5-6-operations.md`.
