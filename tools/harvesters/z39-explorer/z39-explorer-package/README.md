# Z39.50 Explorer 1.0

Busca alvos **publicamente publicados** em Z-BRARY, Koha wiki, o registro IRSpy via SRU (quando acessível) e `seeds.tsv`. Verifica o protocolo com YAZ, testa três buscas comuns, pede no máximo um registro por consulta e classifica autoridades/bibliografia **somente quando recupera ISO2709 válido**. Não executa varredura de redes/IPs arbitrários, não altera o Koha e não importa registros automaticamente.

## Instalação (Ubuntu 22.04+/Debian 12+)

```bash
unzip z39-explorer.zip
cd z39-explorer-package
chmod +x install.sh
sudo ./install.sh
sudo systemctl start --no-block z39-explorer.service
```

A execução é uma unidade `systemd` independente de SSH: **continua após desconectar**. Não é ativada automaticamente no boot. Para **retomar após reiniciar a VPS**, ative com `sudo systemctl enable z39-explorer.service` (a unidade então executará a varredura novamente a cada boot, mas pulará alvos verificados recentemente). Para repetir manualmente após encerrar: `sudo systemctl start --no-block z39-explorer.service`. Os resultados são confirmados no SQLite após cada servidor; se interromper e reiniciar, somente alvos pendentes ou com verificação antiga são processados.

## Acompanhamento

```bash
sudo systemctl status z39-explorer --no-pager
sudo journalctl -u z39-explorer -f
sudo find /var/lib/z39-explorer/reports -maxdepth 1 -type f
sudo cat /var/lib/z39-explorer/reports/resumo.json
sudo systemctl stop z39-explorer  # somente se quiser interromper
```

Para criar um relatório atualizado (como usuário do serviço):

```bash
sudo -u z39explorer python3 /opt/z39-explorer/z39_explorer.py report
```

Para ver a listagem por CSV, leia os relatórios em `/var/lib/z39-explorer/reports/` ou copie-os com `sudo cp` para a sua pasta. Não são necessários `tmux`, `nohup` ou SSH conectado.

## Resultados

- `candidates.sqlite3`: estado incremental durável; inclui endpoints documentados e credenciais guest que os proprietários publicaram explicitamente (proteger arquivo).
- `reports/todos_candidatos.csv`: inventário completo, com status, origem e diagnóstico resumido.
- `reports/bibliograficos_confirmados.csv`: registro MARC recuperado com líder bibliográfico.
- `reports/autoridades_confirmadas.csv`: registro MARC recuperado com líder/06 `z`.
- `reports/pesquisa_sem_marc.csv`: inicialização/busca funcionaram, mas MARC não foi confirmado.
- `reports/nao_validados.csv`: falha/timeout sem inferir que a instituição está definitivamente offline.
- `reports/koha_para_revisao.csv`: candidatos para inserção **manual** no Koha; revisar codificação MARC-8/UTF-8 e permissões antes do uso em produção.
- `reports/resumo.json`: totais.

## Ajustes

O serviço limita-se a **6 trabalhadores simultâneos** (máximo do script: 16), **um alvo de cada vez por host**, intervalo de **3 segundos** entre probes para o mesmo host, até **22 segundos** por alvo e uma quantidade finita de candidatos. Pode reduzir o paralelismo alterando `ExecStart` na unit e executando `sudo systemctl daemon-reload` (não precisa reinstalar o script).

O modo `discover` busca fontes, monta a base e gera CSV, **sem conectar em servidores Z39.50**:

```bash
sudo -u z39explorer python3 /opt/z39-explorer/z39_explorer.py discover
```

O modo `--no-web` usa somente os alvos TSV fornecidos. Insira bibliotecas brasileiras que forneçam host, porta e base em `seeds.tsv`, sem inventar nomes de bases. Nunca inclua credenciais privadas num arquivo que vá publicar; as duas credenciais incluídas no pacote são *guest* divulgadas pela Biblioteca Nacional da Argentina.

## Limitações importantes

- Sem acesso da ferramenta ao seu SSH/VPS, a execução efetiva acontece **quando você executar os comandos acima**.
- Muitos diretórios históricos contêm servidores obsoletos. Um TCP aberto **não** garante protocolo Z39.50 ou recuperação MARC; por isso há validação de protocolo.
- Não presume que uma base bibliográfica sirva autoridades; o tipo é determinado pelo registro MARC obtido.
- Testa apenas três consultas curtas. Uma base funcional pode devolver zero resultados, usar atributos locais, MARCXML/UNIMARC ou exigir autenticação. Esses casos exigem revisão, não significam indisponibilidade definitiva.
- O acesso experimental ao IRSpy usa o serviço SRU documentado na porta 8018. Essa porta pode estar bloqueada por firewall. Caso falhe, o script registra um aviso e prossegue com as demais fontes.
- Os nomes `UTF-8` em catálogos são apenas indícios; o script não valida a codificação dos campos MARC.
- Não use as descobertas para copiar bases completas nem para acesso fora das condições de uso das bibliotecas.

## Fontes

- Library of Congress: https://www.loc.gov/standards/z3950/lcserver.html
- Koha community: https://wiki.koha-community.org/wiki/Koha_Open_Z39.50_Sources
- Z-BRARY: https://www.z-brary.com/
- IRSpy SRU: https://metacpan.org/dist/ZOOM-IRSpy/view/lib/ZOOM/IRSpy/WebService.pod
- UFSC: https://decti.bu.ufsc.br/catalogacao/dados-abertos/
- BNE: https://www.bne.es/es/perfiles/bibliotecarios/suministro-registros/descarga-z3950
- Biblioteca Nacional Argentina: https://www.bn.gov.ar/noticias/actualizacion-en-el-acceso-a-bases-de-datos-bibliograficas-y-de-autoridades-de-la-biblioteca-nacional
- YAZ: https://software.indexdata.com/yaz/doc/yaz-client.html

## Validação local do pacote

Execute `python3 test_offline.py` na pasta do pacote para verificar parsing ISO2709, classificação MARC e exportação SQLite/CSV sem fazer conexões remotas. Este teste **não substitui** a validação ao vivo a partir da VPS.
