# Continuidade do PR4 DSpace

PR aberto: https://github.com/PauloFBaldiFH/koha.nexus/pull/354
Branch: feat/dspace-backup-restore. Base: 9a1da55 (#353).
Versão: 1.5.183. Código funcional atual: 96c8256; depois, apenas documentação.
A nova imagem de receita 4 ainda precisa passar no build e no navegador real.
Não mesclar antes da CI. Nenhuma imagem/serviço foi publicado ou mesclado.

## Entrega

Backup individual integralmente cifrado com a chave GPG existente: dump custom
PostgreSQL, configuração privada, documentos e todos os cores Solr. Captura
coordenada, diário, retomada, teste em volumes independentes sem rede externa,
conferência dos registros e arquivos, plano antes de restaurar e cópia de
segurança. Volumes antigos e candidatos expostos à produção são preservados.
O painel reutiliza a Central de backups, com frase mascarada e cancelamento.
O conjunto antigo continua significando Koha + Tainacan. Operação e comandos:
[PR4-backup-recovery.md](PR4-backup-recovery.md).

## Falha real identificada na UI upstream

Na execução 42430099560, o aceite único foi confirmado, mas uma recarga fez o
campo perder o valor. Os PATCHes seguintes não eram novas aceitações. A fonte
mostrou a causa: BrowserOrejimeService mantém um clone de EPerson e chama
createPatchFromCache para salvar cookies. DSOChangeAnalyzer compara todos os
metadados com o cache atual, gerando remoção do aceite e reversão de outros
campos que não pertencem às preferências de cookies.

Esperar o cliente e refazer o login não corrigiam essa perda. A receita 4 aplica
ui-cookie-metadata.patch, fixado por SHA-256, no checkout verificado antes da
exportação. O fluxo de cookies filtra operações pelo campo exato e descendentes
de dspace.agreements.cookies. Não muda o mecanismo de aceite, não o desativa e
não grava termos por API. O teste Node do build usa o fast-json-patch e o
TypeScript da própria UI; o controle sem filtro reproduz a perda, e a variante
corrigida preserva aceite e demais campos ao adicionar, alterar e remover cookies.

O navegador aguarda o marcador exclusivo do cliente ds-social e a rede estável,
confere uma única gravação de aceite e três recargas. Depois deposita na mesma
sessão autenticada. Nenhuma asserção que revelou a falha foi removida.

## Compatibilidade e imagens

Novas instalações usam receita 4. release-r3.json preserva os bytes e o hash
72c8cec876cbc1ae991c07f19253d2d5bddfe62123e0cfc5572b57480149d608 da receita 3.
O instalador verifica esse quarto arquivo antes de executar ou guardar o
adaptador. Estado confiável de receita 3 seleciona a mesma matriz para operações
e backup; não troca contêineres, arquivos privados nem faz migração. A interface
antiga só receberá a correção numa atualização deliberada (etapa posterior).

Um destino vazio de recuperação pode selecionar o lock antigo explicitamente,
com as imagens e o catálogo imutáveis originais:

    sudo config.sh --task dspace-panel --release-lock 72c8cec876cbc1ae991c07f19253d2d5bddfe62123e0cfc5572b57480149d608 --catalog /caminho/catalogo-r3.json plan --url URL_ORIGINAL

Depois, install com os mesmos parâmetros e --confirm, após revisar. A seleção
não autoriza sobrepor dados de outra matriz. Backup 3 exige destino 3; backup 4
exige destino 4. Não há atualização/downgrade implícitos.

## Comprovado e pendente

- 108 testes stdlib locais aprovados; incluem hashes, preservação da receita
  anterior, recusa de troca sobre dados existentes e nenhuma mutação na seleção.
- Controle Node reproduziu a perda upstream; código corrigido preservou os
  demais metadados. Preparação completa das fontes fixadas passou localmente.
- 88 testes locais anteriores de painel/manual/traduções passaram; o Textual
  emitiu oito avisos de coroutine não aguardada no encerramento. Painel passou
  na CI em Python 3.9/3.13. A nova CI repetirá regressões da cabeça atual.
- Receita 3, d5b9f4d: uma execução completa passou (42426430208), com PostgreSQL,
  Solr, GPG e Chromium reais, depósito, público/privado, SHA-256, restauração
  ativa de ambos, isolamento e histórico Solr não vazio. É prova histórica da
  receita 3; a execução seguinte do PR falhou no aceite e levou à correção atual.
- Receita 4: build Angular completo, navegador e recuperação reais ainda
  pendentes. Não substituir esse aceite pelo teste Node ou pelos doubles.

Paulo prefere abrir/revisar o PR pelo link; não pedir liberação de API novamente
nem abrir outro PR. A API GitHub continua bloqueada no ambiente, mas as páginas
públicas de Actions e Git fetch/push funcionam. Não iniciar PR5 sem pedido:
conjuntos/agendas são PR5, domínios/atualizações são PR6. Sem AtoM/Portal/SSO.

## Limites e preservação

Mesmo endereço e matriz exata; destino precisa ter banco legível para a cópia de
segurança. Para perda completa, preparar outra instalação compatível. Pacote
.tar.gpg transportável; integridade GPG e inventário interno obrigatórios.
Servidor de Paulo, reboot de VM, DSpace em Debian/ARM/WSL e acervo grande continuam
pendentes. DSpace experimental. Não limpar staging após SIGKILL, rollback em
falha ou volumes por prefixo; o Compose ativo identifica os volumes em uso.

Após editar runtime.py/backup.py/release.json, atualizar os hashes no installer e
installer.sha256 antes dos testes. A mudança de matriz deve ter nova receita;
nunca trocar o conteúdo de uma imagem imutável ou afrouxar comparações de lock.
