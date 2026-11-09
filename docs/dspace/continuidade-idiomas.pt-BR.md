# Continuidade: retomada web e idiomas

## Branches

- `feat/dspace-start-web`: correção pontual da versão 1.5.191. O início do
  DSpace reaplica a rota web depois de remoção com dados preservados. Commit
  4ae49b1. O ciclo integrado da CI existente verifica essa retomada.
- `feat/dspace-languages`: versão 1.5.192, baseada nessa correção; 37 traduções
  na receita 5, compatibilidade de receitas 3/4, seleção no menu Idiomas e
  atualização explícita de imagens. Descrição em `PR-idiomas.pt-BR.md`.

## Revisão

Abrir o PR da correção pontual contra main e conferir a CI. Depois de mesclado,
abrir o PR de idiomas contra main. As branches estão empilhadas; o segundo
inclui a correção anterior até ela entrar na main. Nenhuma mesclagem automática
nem publicação do broker faz parte desta etapa.

## Verificações

```sh
python3 tools/dspace_images.py validate
python3 tools/dspace_build_bundle.py --check
python3 export_docs_preview.py --check
bash -n installer
sha256sum -c installer.sha256
python3 -m unittest discover -s tests -p 'test_dspace_*.py' -v
```

Os testes de arquivos protegidos devem rodar como root numa máquina ou
contêiner descartável. O teste integrado instala de verdade, só pode rodar em
runner descartável e não deve ser executado no servidor que contém o acervo.
O workflow `dspace-images.yml` executa as instalações e atualizações reais.

No servidor de Paulo, o último diagnóstico mostrou IP antigo 192.168.1.50 no
DSpace e IPv4 atual 192.168.100.56. A ação **Corrigir acesso web**, introduzida
na 1.5.190, deve ser aplicada e conferida no navegador. Não foi aplicada por
este ambiente. Não apagar banco/volumes para corrigir essa divergência.

## Trabalho posterior

Continuam fora desta etapa: completar os formatos/telas de backup individual
restantes, definir e testar recuperação completa do Nexus, implementar o motor
de múltiplas instâncias com propriedade de portas/proxy/agendas e validar
reinício real no servidor. A disponibilidade de botões não prova esses ciclos.
