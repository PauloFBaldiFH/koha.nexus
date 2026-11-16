# Traduções do painel: espanhol, francês, alemão e italiano

As traduções foram escritas diretamente nos dicionários `lang/es.cache`,
`lang/fr.cache`, `lang/de.cache` e `lang/it.cache`, sem usar o gerador antigo.
O formato existente `base64(texto original)|base64(tradução)` foi preservado.

A cobertura verificada inclui chamadas literais a `t()`, títulos e perguntas
 das seções, rótulos e confirmações das ações, todas as descrições dos cartões
 e constantes do painel já reconhecidas pelo catálogo português (incluindo
 estados, etapas, compactação e textos de apresentação).

O teste em `panel/tests/test_i18n.py` exige entradas válidas nos quatro idiomas
para esse inventário. Marcas, nomes de programas e certas siglas permanecem
iguais intencionalmente. Textos arbitrários vindos de subprocessos, conteúdo
criado por usuários e interfaces próprias de Koha, WordPress e DSpace não são
cobertos por este trabalho. O teste não equivale a revisão linguística por
falantes nativos nem prova tradução de qualquer resposta dinâmica futura.

Validação local:

- 50 testes de tradução, menus, textos e documentação aprovados.
- Todas as entradas novas verificadas quanto às variáveis e porcentagens.
- Painel real em modo demonstração aberto com sucesso nos quatro idiomas,
  em 80×24 e 160×48 (oito execuções headless, sem instalação de aplicativos).
- Prévia da documentação regenerada e verificada.

O teste de cobertura evita que novos textos literais e metadados de menu
voltem a ser publicados sem entradas nesses idiomas. Uma nova tabela dinâmica
precisa ser acrescentada à cobertura se suas chaves não estiverem no inventário
já reconhecido.
