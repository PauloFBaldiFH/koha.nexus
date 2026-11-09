# Recupera status e logs do painel e amplia backup individual do DSpace

Com DSpace instalado, uma quebra de linha no JSON do instalador fazia os
clientes lerem um objeto incompleto: os cartões ficavam em reticências e as
ferramentas do DSpace desapareciam. A saída volta a ser compacta, os clientes
leem o objeto completo e o painel mantém indicadores locais e mensagem de erro
recuperável quando a consulta falha. Consultas têm prazo e recolhem subprocessos.

Operações silenciosas exibem início/espera e explicação no Log. Saída real
substitui a explicação. Instalações não abrem automaticamente o assistente de
publicação/backup; as configurações continuam nos menus.

O backup DSpace oferece nenhuma compactação, gzip, bzip2 e xz, mantendo cifragem,
leitores antigos, inventário e preferência persistida. Os formatos novos também
são aceitos dentro dos conjuntos de plataformas.

A lateral reúne adicionar/remover usando os drivers existentes. Instalações
presentes não são sobrescritas. Este PR ainda não permite duas instalações do
mesmo aplicativo; o cadastro por UUID é uma base testada, sem migração implícita.

Validação: testes locais de status/timeout, loader, navegação, registro,
backup/restauração de arquivos e telas; testes de conjunto em contêiner Debian
como root; sintaxe, hashes e bundle. Windows depende dos testes da CI. Não houve
teste no servidor de Paulo. Resultados finais e continuidade em
`docs/CONTINUIDADE-recuperacao-instancias.md`.

Este é o primeiro lote do plano autorizado. Idiomas DSpace ampliados, cron com
controles unificados, Tainacan com mais compactações, recuperação completa Nexus
e drivers de múltiplas instâncias permanecem em implementação futura, conforme
o documento de continuidade. Não confundir o pacote conjunto atual com imagem
integral da máquina.
