# Continuidade do PR4 DSpace

Branch: `feat/dspace-backup-restore`, base `9a1da55` (#353 mesclado).
Versão: 1.5.183. Runtime de recuperação final: `8f17a6d`.
Aceite real final: `d5b9f4d`; depois dele, apenas documentação.
Nenhuma mesclagem ou publicação de imagens/serviços foi realizada.

## Entrega

Backup individual integralmente cifrado com a chave GPG existente; dump custom
PostgreSQL, configuração privada, documentos e todos os cores Solr. Captura
coordenada, diário e retomada. Recuperação em volumes independentes sem rede
externa, conferência dos registros lógicos e arquivos, prévia antes da
restauração, cópia de segurança e volta à configuração anterior em falha.
Volumes antigos e candidatos expostos à produção são preservados.

O painel reutiliza a Central de backups, com criar/testar/restaurar e chave
existente. A frase é mascarada e não vai em argumentos. O conjunto antigo
continua significando Koha + Tainacan. Detalhes, comandos e operação estão em
[PR4-backup-recovery.md](PR4-backup-recovery.md).

## Comprovado

- 91 testes locais de imagens/runtime/formato (Python 3.12).
- 88 testes selecionados de painel/menus/manual/traduções; layouts 80×24 e
  160×48, cancelamentos, frase protegida e prévia antes da restauração. O Textual
  emitiu oito avisos de coroutine não aguardada no encerramento dos testes.
- CI do painel em Python 3.9 e 3.13:
  https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42425671507
- CI DSpace final, todas as etapas aplicáveis aprovadas em `d5b9f4d`:
  https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42426430208
  O job integrado terminou em 2026-11-08 às 00:10:50 UTC.
  PostgreSQL, Solr, GPG e Chromium reais: depósito; captura pública e privada;
  recuperação isolada; restauração ativa de ambas; download com SHA-256;
  negação do privado ao anônimo e acesso autorizado; histórico Solr não vazio
  preservado. Instalação/recriação/reinício de Docker também passaram.
- Regressões reais de Tainacan e infraestrutura compartilhada aprovadas:
  https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42425421117
  https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42425421038
- `bash -n installer`, inventário/hash do adaptador e `installer.sha256` válidos.

## Correção do roteiro de navegador

A execução 42425421060 falhou antes do backup: após o aceite pela interface,
confirmado por REST, o guard Angular voltou aos termos antes do depósito. O
upstream consulta o EPerson guardado no estado da interface. Em d5b9f4d o roteiro
confirma novamente que o aceite continua salvo após estabilizar a rede e faz
login real numa sessão limpa antes de depositar. Nenhum cookie de aceite ou
escrita de termos por API é injetado. Esse fluxo passou no navegador real da
execução final. O código de produção não foi alterado por essa correção.

## Revisão e próximos passos

Paulo escolheu abrir o PR manualmente pelo link. Não pedir novamente liberação
de API. Não há criação automática de PR confirmada neste ambiente.

https://github.com/PauloFBaldiFH/koha.nexus/compare/main...feat/dspace-backup-restore?expand=1

Título: Adiciona backup cifrado e recuperação isolada do DSpace (PR4).
Relatório/descrição: PR4-backup-recovery.md. Aguardar os checks do PR antes de
mesclar. Não iniciar PR5 sem o pedido de Paulo; conjuntos/agendas são PR5,
domínios/atualizações são PR6. Nenhum AtoM/Portal/SSO entra nesta entrega.

## Limites e preservação

Mesmo endereço canônico e matriz exata. A restauração ativa exige banco legível
no destino para a cópia de segurança; para perda/corrupção completa, preparar
outra instalação compatível. O pacote .tar.gpg é transportável; checksum externo
é adicional, integridade GPG e inventário interno continuam obrigatórios.

Servidor de Paulo, reboot completo de VM, DSpace em Debian/ARM/WSL e acervo grande
continuam pendentes. DSpace continua experimental. Staging privado após SIGKILL,
material de rollback em falha e volumes antigos são preservados para revisão:
não realizar limpeza genérica por nome/prefixo. O Compose ativo identifica os
volumes em uso. Após editar runtime.py/backup.py, atualizar seus hashes no
installer e executar `sha256sum installer > installer.sha256` antes dos testes.
