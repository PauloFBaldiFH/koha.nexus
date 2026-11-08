# PR combinado 5 e 6 — operações DSpace

Base: main 1504c03, PR4 #354 mesclado, versão 1.5.183.

Objetivo: concluir a integração operacional numa única branch/PR, com blocos de mudança separados por commits. Não publicar imagens, broker, certificados ACME ou DNS em produção, nem mesclar automaticamente.

## Contratos

- Backups individuais DSpace continuam integralmente cifrados; conjuntos com DSpace usam formato 2, mantendo o leitor e o significado do formato 1. Um plano guarda sua lista explícita de participantes. Os planos antigos continuam Koha/Tainacan.
- Agendas e conexões de nuvem aparecem nas centrais compartilhadas. Cada execução registra captura, cópia e retenção separadamente; captura parcial ou cópia falha não autoriza eliminar a última cópia boa.
- Restauração seletiva usa o restaurador de cada plataforma. DSpace exige frase, versão e matriz compatíveis; sem restaurar as outras plataformas implicitamente.
- Endereço canônico, origem HTTP do proxy/túnel e TLS são conceitos separados. Alterar endereço preserva propriedades personalizadas e requer prévia, confirmação, backup e retorno ao estado anterior em falha. Não editar proxy de terceiros.
- Endereço gratuito depende de capacidade do broker implantado. Código e migração não equivalem a publicação; manter os endereços Koha/Tainacan existentes.
- Primeira atualização homologável: receita 3 para receita 4 do mesmo DSpace 10.1, sem mudar PostgreSQL/Solr nem esquema. Exigir catálogo imutável e cópia de segurança verificada. Migrações não homologadas são recusadas.
- Remoção mantém dados por padrão. Exclusão requer confirmação adicional, backup verificável e propriedade comprovada de cada recurso. Docker, Apache, túnel e credenciais compartilhados não são removidos por pertencerem também a outras plataformas.

## Validação

Testes nativos de formatos, concorrência, falhas e preservação dos contratos antigos; testes do painel e broker; provas com serviços reais na CI para captura/recuperação, agenda, URL/HTTPS, atualização e remoção. Registrar separadamente testes executados, simulados e pendentes. Não declarar homologado em servidor de Paulo, ARM, Windows/WSL ou após reboot de VM sem execução real.

## Estado

Em implementação. Este documento registra o escopo; não afirma que os critérios acima já passaram.
