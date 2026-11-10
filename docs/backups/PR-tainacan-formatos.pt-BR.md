# Backups do Tainacan: formatos e painel — 1.5.193

A Central de backups, no filtro Tainacan, agora mostra a data do último pacote,
o tamanho local e a compactação dos novos backups. Mantém os controles de
captura manual, teste isolado, restauração, agendamento, repositório, nuvem,
verificação, retomada e kit de recuperação. Abrir a tela só consulta.

## Formatos e preservação

Gzip permanece o padrão. Pode-se escolher Bzip2, XZ ou sem compactação, usando
os codecs da biblioteca padrão do Python. Não exige instalar esses programas
na imagem WordPress. O seletor salva a preferência do Tainacan; uma falha ao
salvar mantém a escolha anterior. Não altera a compressão do Koha/DSpace,
participantes ou horários de planos, retenção, destinos ou conexão de nuvem.

A captura consistente de SQL e arquivos mantém sua janela habitual com gzip.
Quando escolhido outro formato, a conversão ocorre depois de o WordPress
retomar, sem dupla compactação: lê gzip e grava o formato selecionado em fluxo,
com uso de memória limitado. A conversão exige espaço temporário adicional;
a verificação de espaço reserva uma margem maior para esses formatos.

Cada pacote guarda a opção original. Uma preferência nova não reinterpreta
backup antigo nem uma captura interrompida. A conversão usa arquivos `.part`,
checksums e diário; só remove o gzip de origem depois de guardar o destino e
registrar seu checksum. Em falha, mantém a captura para retomar e não aplica
retenção de um backup bem-sucedido.

Pacotes gzip continuam no formato 2; os demais usam formato 3, com campo
`compression`. O leitor mantém suporte aos formatos anteriores. Os pacotes
novos precisam desta versão ou posterior para leitura dos formatos adicionais.
A restauração detecta e valida os dados do pacote, independentemente da
preferência atual. Verifica checksums, limites de expansão, espaço e entradas
inseguras antes do teste isolado. O host descompacta os dados para o contêiner.

Conjuntos Koha/Tainacan/DSpace e o leitor de arquivos Tainacan reconhecem os
novos membros. Não muda o formato do SQL do Koha ou dos arquivos DSpace.

## Restic e criptografia

Em modo restic, a seleção se aplica ao SQL que fica no pacote; os arquivos
continuam no snapshot do repositório. O restic controla sua própria compactação.
O tamanho mostrado é o pacote local, sem somar os arquivos do snapshot.
Esses pacotes continuam dependendo do repositório para recuperar os arquivos.

Compactação não é criptografia. Mantém as regras existentes: o banco deste
formato é legível por root, a configuração só fica cifrada quando a chave está
configurada, e o restic cifra seus dados. Não anuncia cifragem integral do pacote
individual nem muda a proteção das cópias de nuvem.

## Validação

A rodada completa do painel, menus e documentação passou com 296 testes.
Após o ajuste final de recarregamento e cartões, nove testes focados passaram
novamente, sem os avisos de corrotinas de leitura abandonadas. A CI executa
a suíte completa da versão final.

- 53 testes Bats aprovados (motor, conjuntos e controles de agendamento),
  com GnuPG, restic e rclone reais em Debian descartável. A aplicação nesses
  testes é uma plataforma de teste: quatro codecs, conteúdo
  SQL/arquivos, permissões, falha/crash durante conversão, retomada com preferência
  atual diferente, conteúdo alterado, arquivos inseguros e integração restic.
- Conjuntos reais sobre dados de teste: membros Tainacan nos três formatos novos
  entram, são inspecionados e saem para recuperação separada. Leitores de gzip
  e pacotes antigos continuam cobertos.
- Nove verificações finais de recarregamento e seleção do painel passaram,
  sem corrotinas de leitura abandonadas. Painel em 80×24 e 160×48: abrir não captura, alteração persistida, atualização
  da tela e falha ao salvar sem perder a escolha anterior.
- CI Tainacan com WordPress/plugin/navegador reais ampliada para capturar e testar
  recuperação isolada nos quatro formatos. Seu resultado deve ser conferido no
  PR. Os testes locais com plataforma de teste não substituem essa validação.

Esta entrega não é a imagem completa do servidor nem o motor de múltiplas
instâncias. O backup completo do Nexus continua uma etapa separada, com seu
manifesto, dependências e procedimento de recuperação a validar.

Capturas em `capturas/` são do modo de demonstração, com dados simulados.
Não representam backups ou validação do servidor de Paulo.
