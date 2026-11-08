# Continuidade do PR combinado DSpace 5 + 6

Atualizado em 08/11/2026. Branch remota: `feat/dspace-operations`, sobre
`main` no commit `1504c03` (PR #354 mesclado). Versão: **1.5.184**.
Não mesclar nem publicar automaticamente. Paulo prefere abrir o PR pelo link:

https://github.com/PauloFBaldiFH/koha.nexus/compare/main...feat/dspace-operations?expand=1

Escopo, recuperação, limitações e capturas estão em
[PR5-6-operations.md](PR5-6-operations.md). Texto sugerido para o PR:
[PR5-6-description.md](PR5-6-description.md).

## Implementado e enviado

- Backups individuais e conjuntos explícitos com DSpace, planos com participantes
  fixos, agenda, histórico, retenção e cópia integralmente cifrada usando as
  conexões rclone existentes. Planos Koha/Tainacan anteriores não são ampliados.
- Restauração seletiva pelo adaptador de cada plataforma; formato anterior
  preservado. Pacotes são verificados antes da extração, em staging privado.
- Endereço/HTTPS assistido, certificado existente ou proxy externo; preparação
  opcional do endereço gratuito pelo broker, sem implantação de produção.
- Atualização homologável somente da receita 3 para 4 do mesmo DSpace 10.1.
  Recria também Solr, verifica a matriz efetivamente em execução e guarda
  configuração/catálogo anteriores para rollback sem retroceder os dados.
- Remoção mantém dados por padrão; exclusão exige salvaguardas e propriedade.
  Diários privados permitem tratar interrupções. Agendas podem ser desligadas
  mesmo sem a conexão de nuvem ou o destino originais.

## Evidência local e limites

- 137 testes Python 3.13 aprovados; testes de propriedade de diretório executados
  com UIDs reais, fora do remapeamento da sandbox. Docker/cripto simulados nesses
  testes de falha são identificados como tais.
- 130 testes de painel/documentação aprovados, mais o novo teste de adiamento de
  publicação sem chave (131). Dez avisos de encerramento Textual/workers ficaram
  registrados na rodada; nenhum teste falhou nessa seleção.
- Broker: TypeScript, 72 unitários, 24 checks e2e existentes e seis novos checks
  DSpace aprovados com Worker/D1/DO e assinaturas reais, Cloudflare simulado.
- 37 testes Bash aprovados (20 conjuntos/cron, nove Tainacan e oito DSpace).
  Usam contêiner Debian 12 descartável como root. Adaptadores de
  captura Koha/Tainacan e respostas do cliente DSpace são simulados e declarados
  nos arquivos. Não equivalem a executar as três aplicações reais juntas.
- Capturas de interface são do modo de demonstração em 80×24 e 160×48.

## CI: acompanhar antes da mesclagem

Não interpretar testes escritos, imagens construídas ou jobs em fila como aceite.
O workflow `dspace-images.yml` inclui aplicações reais, GPG, rclone, navegador,
URL/TLS e atualização com imagens históricas reais da receita 3. As imagens
históricas vêm do export imutável `858153cc730c17d410943836d222944149c24250`.

Na rodada `42455902927`, a instalação integrada falhou na conexão rclone;
o teste foi corrigido para criar sua conexão com o mesmo arquivo de configuração
usado pelo runtime, sem depender do HOME preservado por sudo. A atualização
histórica também falhou naquela rodada. A nova rodada precisa comprovar o
resultado: foram corrigidos a recriação do Solr e a verificação da matriz, e foi
adicionada uma anotação pública com os frames da falha, sem exportar segredos.
Não afirmar que a causa histórica está resolvida sem a nova execução passar.

Consultar os checks do último commit da branch/PR, incluindo os workflows de
proxy, painel, broker e Tainacan. Corrigir a falha concreta preservando os
critérios de aceite. Não remover gates, rotular imagens novas como antigas ou
contar um teste simulado como validação real.

## Continua pendente fora da CI

Servidor de Paulo, convivência/carga real das três plataformas, reboot de VM/WSL,
domínio/túnel na conta real e matriz de aplicação completa Debian 12/13 e ARM.
DSpace permanece experimental. OAI não é publicado pelo proxy gerenciado até
homologar visibilidade e reconciliação do índice. Não há emissão ACME automática.
Broker/migração 0004/imagens não foram publicados; a opção de endereço gratuito
só funciona após promoção explícita do serviço, com o feature flag habilitado.
