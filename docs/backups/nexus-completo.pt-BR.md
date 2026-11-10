# Backup completo do Nexus

A Central de backups tem a aba **Nexus completo**. Os backups individuais e os
conjuntos existentes continuam disponíveis. O pacote completo acrescenta as
configurações do painel, a chave protegida e as imagens reais dos contêineres.

## Conteúdo e compactação

Um arquivo `knx-nexus-DATA-ID.nexus` contém:

- Todos os sistemas instalados suportados: Koha, Tainacan/WordPress com seus
  plugins e eventos, DSpace com PostgreSQL, arquivos e todos os núcleos Solr.
  A captura reutiliza o motor de cada sistema e registra sua consistência própria.
- Configurações privadas do Nexus, planos, registro de instâncias, cron do Nexus,
  conexões da nuvem, referências da infraestrutura e código do painel disponível.
- Imagens Docker por ID imutável, inclusive o WP-CLI usado pelo Tainacan.
- Manifesto com versões, requisitos, tamanho e SHA-256 de cada arquivo.
- Chave privada OpenPGP **protegida pela frase de recuperação**, sem a frase.

Gzip, Bzip2, XZ/LZMA ou sem compactação podem ser escolhidos na própria aba.
**Todas as opções mantêm a criptografia.** A compactação externa acontece depois
que as rotinas dos aplicativos devolveram os serviços ao funcionamento.

É uma cópia lógica dos aplicativos e do Nexus. Não é um disco inicializável,
exportação do WSL, cópia do Windows nem cópia do sistema operacional. Não inclui
backups anteriores, dados hospedados externamente nem pacotes Debian/venv já
instalados. As capturas são sequenciais, não uma fotografia simultânea entre
sistemas. Estado desconhecido, imagem indisponível, captura parcial ou falha de
espaço impedem publicar um arquivo como completo; a última cópia válida é mantida.

O ZIP externo tem apenas `envelope.json`, `recovery-key.asc` e `payload.gpg`.
O conteúdo, os caminhos das configurações e os dados pessoais ficam no payload
criptografado. O arquivo final tem modo 600 e é publicado por renomeação após
sincronização. Guarde uma cópia fora do servidor e a frase em outro local.

## Verificar e recuperar

**Verificar pacote** usa um chaveiro temporário isolado: basta ter o arquivo e a
frase correta, mesmo depois de perder a chave do servidor original. Verifica a
criptografia, o manifesto e todos os arquivos. Essa operação não inicia os
aplicativos; não substitui ensaiar uma restauração em uma máquina descartável.

**Recuperar** abre uma sessão privada em
`/var/lib/koha-nexus/full-recovery/session-ID` e mostra o plano antes de alterar
sistemas. Prepare instalações compatíveis no destino usando os instaladores:

1. Mesma distribuição, versão e arquitetura do sistema operacional.
2. Mesmo pacote `koha-common`, quando o backup contém Koha.
3. Mesmas imagens do Tainacan e a receita/matriz de imagens correspondente ao
   DSpace. O DSpace também exige a mesma URL; mude o endereço explicitamente
   pelo assistente depois da recuperação. Receitas antigas continuam requerendo
   seu `--release-lock` correspondente.
4. A chave do destino pode estar ausente ou ser a mesma da origem. Outra chave
   existente é preservada; o plano explica o conflito antes de qualquer importação
   ou restauração. Use um destino de recuperação limpo se ele já tiver outros backups.

As imagens do pacote podem ser importadas por **Sessões de recuperação** antes
que os aplicativos estejam prontos. A importação confere cada ID. `docker save`
por ID não garante preservar `RepoDigests`; por isso importar as imagens não
substitui preparar instalações que usem a matriz correspondente. O programa não
publica imagens, não inicia serviços nem executa código arquivado nessa etapa.
A preparação automática de uma máquina vazia e totalmente offline não faz parte
deste fluxo.

Após confirmar, cada sistema usa seu procedimento existente de restauração,
verificação e cópia de segurança. O Koha preserva a senha do banco e recebe de
volta sua `encryption_key`; o Tainacan preserva o endereço do destino. O DSpace
valida a cópia em volumes isolados antes da promoção. Os sistemas concluídos
ficam registrados; se um posterior falhar, **Sessões de recuperação** mostra o
estado e permite continuar. Não há uma transação atômica entre os três sistemas.

## Configurações do destino e revisão

O plano distingue **aplicar** de **manter como referência privada**:

- Preferências estruturadas de tema e idioma são aplicadas com cópias anteriores
  e journal de rollback. Novos planos de backup são recuperados com horário
  vazio/desativado. Planos ou cron de mesmo nome já existentes são preservados.
- O kit importa a chave sem trazer automaticamente repositórios ou destinos de
  cópia da instituição de origem. Uma chave primária diferente não é substituída.
- Contas rclone, cron da origem, registro de propriedade, túneis, regras e demais
  arquivos ficam em `session-ID/tree/settings` para revisão. Não são substituídos
  nem ativados no servidor de destino. Segredos conflitantes do Koha continuam
  seguindo a regra existente de preservação e arquivo `.from-backup`.
- Código e configurações shell arquivados não são executados nem instalados
  automaticamente. O administrador continua usando o instalador confiável atual.

As sessões contêm dados descriptografados, acessíveis somente ao root, e ocupam
espaço até a limpeza explícita. Uma sessão aberta ou concluída pode ser apagada
pelo painel; uma interrompida é preservada para revisão/retomada. A limpeza não
apaga o pacote criptografado nem as cópias de segurança dos aplicativos.

## CLI

```bash
sudo config.sh --task nexus-full status
sudo config.sh --task nexus-full plan --compression gz
sudo config.sh --task nexus-full create /var/backups/nexus-full --compression xz --confirm
```

`verify ARQUIVO`, `open ARQUIVO` e `restore SESSAO --confirm` recebem
`KEI_BACKUP_PHRASE` somente no ambiente da tarefa; prefira digitar a frase no
campo protegido do painel, sem colocar senhas na linha de comando ou no histórico.
`restore-plan SESSAO` apenas lê a compatibilidade; `load-images SESSAO --confirm`
importa imagens; `cleanup SESSAO` limpa uma sessão elegível.

O adaptador é verificado por SHA-256 e tem cache offline explícito. A distribuição
continua funcionando com o `config.sh` isolado, sem checkout do GitHub ao lado.
