# Harvesters (ferramentas avulsas)

Scripts de coleta e diagnóstico usados para montar e testar a base de
catálogos do Koha.Nexus. Ficam no repositório só para não se perderem.

**Não fazem parte do instalador, do painel nem da suíte de testes.** Nada
aqui é chamado automaticamente; cada script roda à mão, quando alguém quiser.

Exceção: `z39-atlas-2.0/z39-atlas/z39atlas.py` (descoberta de servidores
Z39.50) tem uma cópia idêntica no painel, `panel/kei_panel/z39atlas.py`, usada
pelo botão "Descobrir novos servidores" da tela Z39.50 / SRU. Um teste do
painel compara as duas: ao mudar uma, copie para a outra.

| Script | O que faz |
| --- | --- |
| `validate_targets.py` | Lê um `targets.yaml` e confere `Identify` e `ListMetadataFormats` de cada alvo OAI-PMH. |
| `probe_z39.py` | Testa um host Z39.50 com `yaz-client` e tenta descobrir uma base que responda. |
| `normalizer.py` | Funções para extrair título, autor, ISBN, ano, CDD/CDU de MARCXML ou ISO 2709 (biblioteca, não tem `main`). |
| `harvester_zeus_ufsc.py` | Busca por termos no agregador Zeus (UFSC) e guarda os `rawRecord` ISO 2709. |
| `harvester_usp_aleph.py` | Percorre os números de registro do Dedalus (USP, Aleph) e converte para ISO 2709. |
| `harvester_ufrgs_aleph.py` | Percorre os números de registro do Sabi (UFRGS, Aleph). |
| `harvester_unesp_primo.py` | Percorre MMS IDs da UNESP no Primo/Alma e converte para ISO 2709. |
| `harvester_pergamum.py` | Busca por termos no Pergamum da PUCPR (AJAX) e guarda as referências. |
| `harvester_rede_pergamum.py` | Percorre as APIs Pergamum de UFMG, UFSCar, UFMS, UFPE, UFV e UFPel. |
| `testar_71_servidores.py` | Faz uma busca em cada um dos 71 alvos `/sru/<sigla>` do gateway e resume quem respondeu. |

## Onde os dados vão parar

Os harvesters gravam `.jsonl.zst` e um checkpoint para continuar de onde
pararam. A pasta vem, nesta ordem, de:

1. `--out-dir <pasta>`;
2. a variável `KOHA_NEXUS_HARVEST_DIR` (cada script usa a sua subpasta, por
   exemplo `$KOHA_NEXUS_HARVEST_DIR/data_aleph`);
3. a pasta atual.

Os nomes das subpastas são os mesmos de antes (`data_aleph`, `data_ufrgs`,
`data_unesp`, `data_<instituição>`, `data_harvested/...`), então rodar a partir
de `/home/ubuntu` reaproveita checkpoints antigos.

`harvester_rede_pergamum.py` e `harvester_ufrgs_aleph.py` não têm ID final:
rodam até serem interrompidos (Ctrl+C) e retomam pelo checkpoint.

O gateway testado por `testar_71_servidores.py` vem de `--gateway` ou de
`KOHA_NEXUS_GATEWAY_URL` (padrão `https://sru.koha.nexus`).

Nunca faça commit dos dados, logs, bancos, venvs ou chaves gerados por estes
scripts.

## Dependências

Python 3.10 ou mais novo e, conforme o script: `httpx`, `zstandard`,
`beautifulsoup4`, `lxml`, `PyYAML`, `requests`. `probe_z39.py` precisa do
`yaz-client` (pacote `yaz`).
