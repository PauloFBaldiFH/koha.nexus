# Continuidade do PR4 DSpace

Branch: `feat/dspace-backup-restore`, base `9a1da55` (#353 mesclado).
Código atual: `d5b9f4d` (runtime de recuperação em `8f17a6d`) (versão 1.5.183). Não há mesclagem automática.

Entregas e limites estão em PR4-backup-recovery.md. A implementação ainda precisa
passar na CI integrada antes de ser considerada pronta. Abertura via gh está
bloqueada neste ambiente: api.github.com retorna Forbidden. Git fetch/push e a
página pública das Actions funcionam. Não há PR confirmado para esta branch.

## Comprovado localmente

- `python3 -m unittest discover -s tests -p 'test_dspace*.py' -q`: 91 aprovados.
  Inclui formato, falhas de captura, retomada, rollback de configuração em disco,
  preservação do material quando a volta falha, limite de saída real do GPG e
  strings SQL que parecem comentários.
- Painel/menus/manual/traduções: 88 testes selecionados aprovados (Python 3.12).
  Inclui cancelamento, prévia antes de restaurar, escopo DSpace isolado e frase
  mascarada; layout exercitado em 80×24 e 160×48. O Textual emitiu oito avisos
  de coroutine não aguardada durante o encerramento de testes. Os 21 testes de
  menus/manual/traduções passaram novamente após corrigir os avisos de ajuda.
- `bash -n installer` aprovado.

## CI integrada e próxima validação

Execução final DSpace (`d5b9f4d`), ainda em andamento:
https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42426430208
Último painel (`fff9534`), ainda em andamento:
https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42425671507

A recuperação real passou em `20e3082`: captura cifrada pública e privada,
cópia isolada, restauração ativa de ambas, SHA-256 do download, negação de
acesso anônimo ao privado e estatísticas Solr não vazias preservadas. PostgreSQL,
Solr e criptografia são reais. O job integrado terminou com sucesso em
2026-11-07 às 23:25 UTC.

Ajustes finais ainda precisam dessa mesma CI: candidatos expostos à produção
sobrevivem também a rollback, registro de propriedade antes da promoção,
fsync antes de publicar pacote/rollback, mtime preservado, hardlinks do original
serializados como arquivos comuns e readiness PostgreSQL por TCP.

## Para finalizar

1. Acompanhar a CI da cabeça atual e corrigir falhas reais, mantendo todos os
   critérios de dados/permissões. Não considerar os ajustes finais validados em runtime antes disso.
2. Depois de editar backup.py ou runtime.py, atualizar seus hashes no installer
   e executar `sha256sum installer > installer.sha256` antes dos testes.
3. Atualizar o relatório com links/resultados efetivos e limitações.
4. Abrir PR contra main para revisão. Se a API continuar bloqueada, usar a URL
   de comparação da branch e registrar a limitação. Não mesclar nem publicar.
5. Não iniciar PR5 (conjuntos/agendas), PR6 (domínios/updates) ou AtoM.

O backup cifrado é um arquivo `.tar.gpg` transportável; o checksum externo é
opcional porque a integridade GPG e o inventário interno continuam obrigatórios.
Uma máquina vazia prepara a mesma release antes de restaurar. Não há migração
entre endereços/releases ou suporte a instalações DSpace externas/adotadas.
Todos os testes em servidor de Paulo, VM reboot, Debian, ARM/WSL e acervo grande
continuam pendentes. Cópias locais de staging após SIGKILL e volumes anteriores
são preservados para revisão; não realizar limpeza genérica desses recursos.

Abertura manual, apenas se a API continuar bloqueada e não houver PR existente:
https://github.com/PauloFBaldiFH/koha.nexus/compare/main...feat/dspace-backup-restore?expand=1

Título sugerido: Adiciona backup cifrado e recuperação isolada do DSpace (PR4).
O relatório PR4-backup-recovery.md contém a descrição e as limitações para revisão.

A execução 42425421060 falhou antes do backup, no campo de título do depósito:
a conta tinha o aceite salvo via interface e confirmado por REST, mas o guard do
Angular voltou à tela dos termos. Em d5b9f4d o teste confirma novamente a
persistência após a rede estabilizar e inicia uma sessão limpa, com login real,
antes de depositar. Nenhum cookie de aceite nem escrita de termos por API é
injetado. Falta validar essa alteração no navegador real da nova execução.
