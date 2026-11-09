# Correção do acesso e validação da instalação do DSpace — 1.5.190

A instalação informava que estava pronta mesmo com a interface pública em
`/500`. O diagnóstico validava serviços internos e a presença de `<ds-app>`
no HTML, que também existe no fallback de uma interface quebrada.

## Causa do caso investigado

O endereço salvo era `http://192.168.1.50:8100`, enquanto a interface `eth1`
reportada pelo servidor tinha `192.168.100.56/24`. O endereço antigo não
respondia. A API anunciava o IP antigo em seus links públicos. O acesso por
`localhost` produzia nos logs da UI `URL with hostname "localhost" is not
allowed`, porque o upstream protege a renderização SSR pelo host canônico.

A raiz da API respondia pela porta local; isso, e os quatro contêineres
rodando, não provavam acesso pelo navegador. As mensagens antigas de
recuperação/inicialização do PostgreSQL não justificam apagar ou restaurar o
banco: o diagnóstico e a API enviados pelo servidor já respondiam.

## Mudança

- Valida IPv4 literal antes de uma instalação e de alterações do endereço.
  Confere as interfaces locais ou o IP fornecido pela integração Windows.
- No WSL, instalação nova oferece acesso só neste computador (`localhost`) ou
  endereço de rede/domínio. Retomar instalação mantém o endereço existente.
- O Apache redireciona aliases para o host canônico fixo, preservando caminho,
  consulta e método (307). Mantém as proteções de SSR e CORS do DSpace.
- Instalar/iniciar verifica API, estado anônimo de autenticação, URLs do JSON
  usado pelo navegador e formulário de senha renderizado. O proxy gerenciado
  também é verificado. Em HTTP, verifica acesso à API de autenticação pelo
  endereço canônico real. DNS/TLS externos continuam explicitamente pendentes
  de teste externo, sem declarar que foram verificados.
- O diagnóstico informa falha de acesso público mesmo com contêineres ativos.
  Os passos de espera produzem progresso e preservam a causa da última falha.
- Nova ação **DSpace → Diagnóstico e manutenção → Corrigir acesso web**.
  Oferece localhost, IPv4 atual na mesma porta ou manutenção do endereço atual.
  Apresenta plano e confirmação, salva configuração privada para rollback e
  valida o resultado. Não exige chave de backup para esta mudança de
  configuração. Domínio, TLS e mudança de porta usam o assistente existente.
- Banco, arquivos, credenciais, imagens, volumes e agendas são preservados.
  A correção também atende instalação parada nas fases de aplicação/proxy,
  depois de a migração ter concluído. Não repete migração.

## Aplicação no servidor investigado

Depois de mesclar e atualizar o painel para 1.5.190, abrir a ação de correção,
escolher o IPv4 atual e informar `http://192.168.100.56:8100`. Conferir o plano,
confirmar e abrir `http://192.168.100.56:8100/login`. Se o IP tiver mudado desde
o diagnóstico, usar a saída atual de `ip -br -4 addr`.

Para acesso apenas neste computador, a opção localhost configura UI, API e
CORS juntos. Outros computadores dependem da publicação de rede e das regras
Windows/WSL correspondentes.

Equivalente no terminal, primeiro plano, depois aplicação explícita:

```sh
printf '%s\n' '{"url":"http://192.168.100.56:8100"}' | sudo /usr/local/bin/config.sh --task dspace operations repair-web
printf '%s\n' '{"url":"http://192.168.100.56:8100"}' | sudo /usr/local/bin/config.sh --task dspace operations repair-web --confirm
sudo /usr/local/bin/config.sh --task dspace diagnose
```

Um IP pode mudar com DHCP. A correção não promete que um endereço numérico
seja permanente. Não amplia a lista de hosts permitidos para qualquer origem.

## Validação

- Regressão completa do workflow Platforms panel: 271 testes aprovados,
  sem falhas ou testes pulados (Python 3.12 local, 10 min 24 s).
- 143 testes de HTTP/reparo, runtime, operações e backups DSpace aprovados
  como root em Debian descartável; quatro Bats de endereço/Apache real
  aprovados; 19 verificações de menus, documentação e checksum aprovadas.
- Imagem real da UI 10.1-r4 e Chromium: reproduzido `/500` com API indisponível
  e acesso por host diferente. Reproduzida resposta HTTP 200 com `<ds-app>`
  que a verificação antiga aceitava. Não é um teste local do backend completo.
- Apache real em Debian descartável: redirecionamento fixo, caminho/consulta
  preservados e ausência de redirecionamento para host fornecido pelo cliente.
- Testes HTTP e de transação: API inicial saudável com autenticação quebrada,
  configuração antiga do navegador, formulário ausente, origem inacessível,
  plano/cancelamento, preservação dos recursos e rollback após falha.
- Suítes de runtime, operações e backups do DSpace executadas em contêiner
  descartável como root, incluindo recuperação de fase web sem migração.
- A CI integrada adiciona navegador entrando por localhost, reparação real da
  configuração, verificação de volumes/imagens/credenciais/Flyway e login
  real depois da correção. O resultado dessa CI deve ser conferido no PR.
- O backend completo não foi compilado neste ambiente: a política de rede
  não permite o repositório Maven de handle.net. A CI é a validação completa
  com PostgreSQL, Solr, backend e UI. O servidor de Paulo ainda deve receber
  e validar a atualização.
