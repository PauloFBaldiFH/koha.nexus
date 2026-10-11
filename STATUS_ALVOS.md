# Status dos Alvos de Catalogação — koha.nexus SRU Gateway

Data da última atualização: 11/10/2026

## 1. Alvos Nacionais e Internacionais Validados e Operacionais (15)

Todos respondem normalmente via protocolo SRU (`/sru/{id}`):

| ID | Instituição | Tipo | Destino / Parâmetros |
| :--- | :--- | :--- | :--- |
| `bn` | Fundação Biblioteca Nacional | zeus | Target Index: 0 |
| `senado` | Rede Virtual de Bibliotecas (RVBI) | zeus | Target Index: 2 |
| `usp` | Universidade de São Paulo | zeus | Target Index: 4 |
| `uerj` | Univ. do Estado do Rio de Janeiro | zeus | Target Index: 5 |
| `unicamp` | Univ. Estadual de Campinas | zeus | Target Index: 6 |
| `ufg` | Univ. Federal de Goiás | zeus | Target Index: 8 |
| `ufmg` | Univ. Federal de Minas Gerais | zeus | Target Index: 9 |
| `ufpe` | Univ. Federal de Pernambuco | zeus | Target Index: 10 |
| `ufsc` | Univ. Federal de Santa Catarina | zeus | Target Index: 11 |
| `ufscar` | Univ. Federal de São Carlos | zeus | Target Index: 12 |
| `ufu` | Univ. Federal de Uberlândia | zeus | Target Index: 14 |
| `ufrgs` | Univ. Federal do Rio Grande do Sul | zeus | Target Index: 16 |
| `uff` | Univ. Federal Fluminense | zeus | Target Index: 17 |
| `pergamum`| Rede Pergamum | pergamum| Backend dedicado Python |
| `loc` | Library of Congress (EUA) | z3950 | lx2.loc.gov:210 (db: LCDB) |

---

## 2. Alvos Internacionais Prontos para Teste de Consulta (2)

Portas de rede já testadas e abertas na VPS:

- `sbn_it`: Servizio Bibliotecario Nazionale (Itália) — `opac.sbn.it:3950`
- `swb_de`: SWB K10plus (Alemanha) — `z3950.k10plus.de:210`

---

## 3. Alvos que Necessitam de Novos Hosts / Endpoints (2)

- `bl`: British Library — porta 9909 recusada; necessário endpoint SRU/Z39.50 atual.
- `nlm`: National Library of Medicine — Voyager descontinuado; migrado para Alma.

---

## 4. Alvos Internacionais Pendentes de Parâmetros (29)

- **América do Norte:** `harvard`, `mit`, `uw_madison`, `psu`, `upenn`, `tufts`, `fsu`, `ubc`, `trent`, `sfu`, `utoronto`
- **Europa:** `oxford`, `bne`, `bcl`, `bizkaia`, `aladi`, `abes_fr`, `uhamburg`, `bn_polonia`, `slsp`, `nkc`, `rsl`, `bashkir`
- **América Latina:** `bna`, `biblored`, `pucp`, `upc_peru`
- **Outros:** `christchurch`, `juac_julac`, `monash_sa`

- **MIT (EUA)**: Operacional via SRU Alma (`01MIT_INST`) - MARCXML nativo.
- **UPenn (EUA)**: Operacional via SRU Alma (`01UPENN_INST`) - MARCXML nativo.
- **DNB (Alemanha)**: Descartado (Cluster entrega apenas RDF/XML e falha no conversor interno MARC21).
- **Yale University (EUA)**: Operacional via SRU Alma (`01YALE_INST`) - MARCXML nativo.
- **University of Michigan (EUA)**: Operacional via SRU Alma (`01UMICH_INST`) - MARCXML nativo.
- **University of Oxford (UK)**: Operacional via SRU Alma (`44OXF_INST`) - MARCXML nativo.
- **University of Cambridge (UK)**: Descartado (Código de instituição 44CAM_INST inválido no Alma).
- **University of Manchester (UK)**: Operacional via SRU Alma (`44MAN_INST`) - MARCXML nativo.

- **King's College London (UK)**: Operacional via SRU Alma (`44KCL_INST`) - MARCXML nativo.
