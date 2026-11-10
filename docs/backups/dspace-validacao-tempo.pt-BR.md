# Validação do DSpace: divisão do teste integrado

A execução da main no [run 42851095050](https://github.com/PauloFBaldiFH/koha.nexus/actions/runs/42851095050)
atingiu o limite de 60 minutos do job `installation`. O log público comprova
progresso e verificações aprovadas durante esse período; não mostra uma instalação
parada durante uma hora.

| Parte observada no log | Duração aproximada | Resultado antes do limite |
| --- | --- | --- |
| Instalar e verificar API/interface | 1 min 20 s | Passou |
| Navegador, depósito público e restrição de acesso | 4 min 50 s | Passou |
| Recuperação nativa pública/privada em volumes independentes | 12 min | Passou |
| Pacote completo Nexus, perda do chaveiro e restauração real do DSpace | 12 min | Passou |
| Parada/recriação de contêineres e reinício do Docker | 7 min | Passou |
| Agendamento, nuvem, endereços e remoção | Mais de 20 min | Interrompido durante as verificações |

O marcador `PASS: full Nexus recovery after loss of the active source keyring:
dspace` está no log antes da interrupção. Os testes posteriores ainda precisam
terminar; o job cancelado não deve ser apresentado como aprovado.

## Alteração

A CI executa duas instalações independentes, com imagens reais e navegador real:

- `integration (lifecycle)`: instalação, depósito e acesso privado, recuperação
  nativa pública/privada, persistência, bloqueio de operações concorrentes,
  proteção de migração, reinício real do Docker, reparo web e idiomas.
- `integration (backup-operations)`: instalação, depósito e acesso privado,
  pacote completo Nexus com perda do chaveiro, conjunto, tarefa agendada real,
  cópia criptografada via rclone, falha de upload, endereços/HTTPS e remoção
  mantendo os dados.

O limite continua em 60 minutos **por job**. As duas suítes são obrigatórias;
o check `installation` mantém o nome anterior e falha se alguma for cancelada,
pular ou falhar. A publicação continua restrita à ação explícita na main, depois
das duas suítes e dos testes de atualização.

Os 33 `check`/`assert` do teste de instalação/navegador e os dez `assert` de
operações foram comparados pela AST com a main: as expressões foram preservadas.
Os tempos de parada dos serviços, as cópias de segurança e as verificações de
integridade não foram reduzidos para acelerar a CI. Não há mudança no instalador
ou nos dados de um servidor instalado.

## Diagnóstico por fase

Cada job exporta seu próprio artefato `dspace-integrated-acceptance-SUITE`, com
`dspace-phase-timings-SUITE.json`. O arquivo registra a entrada na fase **antes**
do trabalho: se o runner encerrar o processo abruptamente, a última fase aparece
como `running`, com a hora de início. No encerramento normal, há duração e estado
`passed` ou `failed`. Não são exportados argumentos, mensagens privadas de erro,
senhas ou configurações nesses recibos.

As operações têm medições separadas para conjunto/restauração, agenda/nuvem,
falha de upload, endereços/TLS e remoção. A validação final exige que todas as
fases obrigatórias da suíte tenham sido concluídas.

Uso manual, apenas em máquina descartável vazia e como root:

```bash
python3 tools/dspace_install_test.py --disposable --suite lifecycle
python3 tools/dspace_install_test.py --disposable --suite backup-operations
```

Sem `--suite`, a opção `all` continua executando a sequência completa para uso
local. As duas execuções acima precisam de máquinas independentes; o teste recusa
iniciar sobre uma instalação existente.
