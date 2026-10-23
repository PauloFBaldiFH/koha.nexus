# Manual do usuário do Koha.Nexus

Este manual explica como operar o instalador e o painel do Koha.Nexus. Os procedimentos foram conferidos no código do repositório, na revisão `c9d9fa5`. Ele não substitui o manual do próprio Koha para catalogação, circulação e administração bibliotecária.

O manual é entregue em lotes de até três seções para revisão:

1. [Instalação no Windows, Debian e Ubuntu](01-instalacao.md).
2. [Primeiros passos e uso do painel](02-painel.md).
3. [Backup e restauração](03-backup-restauracao.md).
4. [Importação mágica](04-importacao-magica.md).
5. [Enriquecimento e Z39.50/SRU](05-enriquecimento.md).
6. [Aparência do OPAC e da equipe](06-aparencia.md).

As seções de IA local, administração e solução de problemas serão entregues no próximo lote. A versão em inglês será preparada depois da aprovação do texto em português.

Os nomes das ações abaixo seguem o português brasileiro dos dicionários do painel. Algumas mensagens podem aparecer em inglês conforme a versão instalada e a cobertura das traduções. Não use os números de opção de um menu antigo como referência para localizar ações no painel atual.

## Como ler os avisos

- **Ação destrutiva:** a operação pode substituir ou apagar dados. Leia a confirmação da tela antes de continuar.
- **A confirmar:** o código consultado não permite garantir a afirmação, ou existe divergência com a documentação anterior. Esses pontos estão identificados na seção correspondente.
- **Fonte:** referência ao arquivo e à função que sustentam a orientação. A conferência foi por leitura do código; ela não equivale a um teste de instalação em um computador real.

## Pendências deste lote

- **A confirmar:** disponibilidade pública e endereço da listagem na Microsoft Store. O repositório tem suporte de empacotamento para a Store, mas isso não comprova que uma publicação esteja disponível.
- **A confirmar:** mínimo oficial de RAM para Debian/Ubuntu fora do Windows. O guia de instalação recomenda 4 GB para servidor dedicado, com 8 GB recomendados, mas a pré-validação Linux atual não impõe esse corte numérico.
- **A confirmar:** funcionamento ponta a ponta do pacote MSIX em Windows ARM64. O manifesto gerado declara arquitetura x64; este manual não promete compatibilidade ARM64 do pacote.
