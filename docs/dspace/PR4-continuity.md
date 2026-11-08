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

Paulo abriu o PR manualmente: https://github.com/PauloFBaldiFH/koha.nexus/pull/354.
Não pedir novamente liberação de API nem abrir outro PR.

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

## Nova falha na execução do PR #354

A execução 42428736161 falhou antes do backup: o aceite estava verdadeiro na
primeira leitura, mas deixou de estar após os pedidos do navegador estabilizarem.
Apenas reiniciar a sessão, como no aceite anterior, não eliminou essa corrida.

O roteiro agora espera um marcador exclusivo da renderização no navegador
(`ds-social`, condicionado a browserPlatform no AppComponent upstream), além da
rede estabilizada, antes de interagir. Confere a transição aria-disabled de true
para false, clica no rótulo visível e espera especificamente o PATCH de aceite.
Confere uma única gravação, sem revogação, e três recargas com o aceite marcado.
Nenhum termo é gravado por API, nenhum cookie de aceite é injetado e a asserção
que detectou a perda permanece. O diagnóstico só extrai valores true/false do
campo exato de aceite; testes recusam incluir outros dados de perfil.

99 testes locais stdlib passaram (incluindo oito novos de diagnóstico seguro).
A validação com navegador real desta correção ainda precisa passar antes da
mesclagem. O êxito de d5b9f4d acima registra a execução anterior, não aprova esta.

O roteiro corrigido continua na mesma sessão autenticada após as três recargas;
a tentativa anterior de contornar o problema com outro login foi retirada.

## Causa confirmada: preferências de cookies alteravam outros metadados

A execução 42430099560 passou pelo aceite único, mas a verificação após recarga
falhou. O diagnóstico mostrou um PATCH de aceite true, seguido de PATCHes que
não eram novas aceitações. A fonte upstream revelou o motivo:
BrowserOrejimeService guarda um clone antigo de EPerson e calcula
createPatchFromCache desse clone para salvar cookies. DSOChangeAnalyzer compara
todos os metadados. Assim, a alteração dos cookies pode remover o campo de aceite
ou reverter outro metadado atualizado depois da captura desse clone.

A imagem corrigida usa a receita 4. A preparação aplica o patch fixado por
SHA-256 no checkout verificado, antes da exportação. O callback mantém apenas
operações do campo dspace.agreements.cookies e seus descendentes. Não desliga o
consentimento, não aceita termos por API e não remove as asserções do navegador.
Um teste Node com o fast-json-patch e o TypeScript da UI reproduz a perda no
controle antigo e prova que o filtro preserva aceite e outros metadados, inclusive
ao adicionar, alterar ou remover preferências. Ele roda também antes do build
Angular. A preparação completa das duas fontes fixadas passou localmente.

108 testes stdlib locais passaram. A imagem completa e o navegador real da
receita 4 ainda precisam passar na nova CI. Os sucessos anteriores de receita 3
não aprovam automaticamente a receita 4.

### Preservação das instalações anteriores

release-r3.json guarda os bytes e o SHA-256 exatos da receita 3. O instalador
confere esse quarto arquivo antes de executar ou guardar o adaptador. Ao encontrar
estado confiável da receita 3, o runtime conserva essa matriz para operações e
backup; não substitui contêineres, não altera arquivos privados e não migra dados.
Instalações novas usam receita 4. Atualizar uma instalação da receita 3 para 4
exige atualização deliberada (etapa posterior); a interface antiga não é trocada
por uma simples atualização do painel.

Para preparar um destino vazio da receita 3 para recuperar um pacote antigo,
com as imagens imutáveis originais e seu catálogo revisado:

    sudo config.sh --task dspace-panel --release-lock 72c8cec876cbc1ae991c07f19253d2d5bddfe62123e0cfc5572b57480149d608 --catalog /caminho/catalogo-r3.json plan --url URL_ORIGINAL

Depois, usar install com o mesmo prefixo, URL e --confirm, após revisar o plano.
Não há restauração entre matrizes: um pacote 3 exige destino 3, e um pacote 4
exige destino 4. A seleção explícita não autoriza sobrepor dados de outra matriz.
Os testes de seleção/recusa e de ausência de mutação passaram; não anunciar uma
nova instalação ou restauração real de receita 3 a partir desses doubles.
