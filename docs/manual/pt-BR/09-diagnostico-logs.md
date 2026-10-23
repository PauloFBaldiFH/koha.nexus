# 9. Solução de problemas e logs

[Índice do manual](README.md) · [Anterior: administração](08-administracao.md)

Registre a ação executada, o horário, o texto completo do erro e o que ainda funciona. Uma página que abre, um serviço ativo e uma busca funcionando são verificações diferentes. Não reinstale nem restaure a base como primeira tentativa para qualquer erro.

## Começar pelo painel

1. Consulte o **Painel de Controle** e atualize o estado.
2. Em **Central de diagnóstico e manutenção**, abra **Status detalhado do servidor e do Koha** para ver serviços, busca, máquina e backup.
3. Execute **Verificação completa do sistema** e leia o resumo e o relatório.
4. Abra **Ver o último relatório de validação** para consultar os detalhes depois.
5. Se precisar de suporte, use **Exportar diagnósticos**, disponível no Painel de Controle. Guarde o caminho informado.

O exportador aplica ocultação de senhas, tokens e chaves. Ainda assim, confira o material antes de compartilhar: informações sobre leitores, nomes de arquivos e endereços da infraestrutura podem ser sensíveis. Não copie indiscriminadamente a pasta inteira de uma instalação.

Se o painel Textual não conseguir abrir, o iniciador tem um modo clássico de contingência. Isso não significa que uma operação iniciada antes tenha sido desfeita. Guarde a mensagem e o log do painel.

## Onde procurar os logs

| Local | O que investigar |
| --- | --- |
| `/var/log/koha-easy-install/` | Diretório dos logs do instalador e das rotinas Linux. |
| `apt.log`, nesse diretório | Instalação de pacotes e saídas de etapas que usam esse log. |
| `validacao-*.log`, nesse diretório | Relatórios de validação, separados por data e horário. |
| `new-panel.log`, nesse diretório | Erros do painel Textual, inclusive traceback quando há falha de execução. |
| `backup_sql.log` e `backup_marc.log`, nesse diretório | Resultado das rotinas de backup SQL e exportação MARC. |
| `restore.log` e `restore-import.log`, nesse diretório | Etapas de restauração e importação do SQL. |
| `zebra-rebuild.log` e `search-engine.log`, nesse diretório | Reconstrução e diagnóstico do mecanismo de busca. |
| `/var/log/koha-easy-install/tools/` | Logs das ferramentas, como importação e operações bibliográficas. |
| Diretório `logs` da instalação Windows | Logs da parte Windows; o diretório padrão atual é `C:\Koha\logs`, com compatibilidade para instalações antigas em `C:\KohaEasy\logs`. |

Os nomes com `*` representam vários arquivos com nomes datados; não são um nome literal a ser criado. Um log pode não existir antes da primeira execução da rotina. Para uma operação de ferramenta, prefira o caminho exato apresentado no resumo ou no erro.

Os logs de ferramentas podem conter dados pessoais e são criados com acesso restrito. Abra **Ver logs das ferramentas** em Ferramentas da biblioteca para selecionar uma execução, começando pela data e pela rotina correta.

## Ler um relatório de validação

O relatório apresenta contexto, data, versão do painel e resultados. As marcações diferenciam itens OK, avisos, falhas e informação. Leia a mensagem de cada falha; o total final não explica sozinho a causa.

**Nenhuma falha crítica** pode vir acompanhado de avisos. Um aviso de backup antigo pede uma providência diferente de uma falha de banco ou de busca. Depois de corrigir o problema, execute a validação novamente e compare com o relatório anterior.

## Consultar os erros do OPAC ou da equipe

Na Central de diagnóstico, abra **Auditoria de logs do Apache em tempo real** e escolha equipe/intranet ou OPAC. O painel procura o arquivo correspondente e usa caminhos alternativos para instalações antigas.

Na tela Textual, **Pausar** ou a tecla **p** interrompe a atualização da visualização, sem parar o Apache. **Continuar** retoma. **Voltar** ou **Esc** fecha a visualização. O painel clássico usa outro fluxo, com `Ctrl+C` para sair do acompanhamento; não transfira esse atalho para toda operação do painel.

Procure mensagens próximas ao horário do erro. Linhas com `error`, `fatal`, `denied` ou `fail` recebem destaque, mas uma palavra destacada não basta para identificar a causa. Copie contexto suficiente, removendo dados pessoais antes de enviar a alguém.

## Procedimentos por sintoma

### OPAC ou equipe não abre

Confira os estados de Apache, MariaDB, Plack e cache no status detalhado. Verifique se o endereço é local, de rede, de VPN ou de túnel e se o problema acontece em ambos os lados. `localhost` aponta para o computador em que o navegador está sendo usado; não é um endereço universal do servidor remoto.

Use **Reiniciar / reparar os serviços do Koha** quando o diagnóstico apontar problema nos serviços. A operação pode interromper o atendimento por alguns instantes. Confira a mensagem final e faça nova validação; não considere um reparo bem-sucedido apenas porque o botão terminou.

### Registro existe, mas a pesquisa não encontra

Confira o mecanismo de busca, a fila e a relação entre índice e banco no status detalhado. Em **Busca e indexação**, há uma ação para reparar ou reconstruir a indexação. Leia as perguntas sobre reconstrução antes de confirmar e aguarde o término. Trocar Zebra por Elasticsearch não é o primeiro passo obrigatório de investigação.

### Backup não apareceu

Confira o horário da última execução, seu resultado e o espaço livre. Verifique se o computador e o Linux estavam ativos no horário do cron. Um arquivo `.part` ainda em gravação não é um backup concluído. Consulte `backup_sql.log` e a Central de Backup antes de repetir operações simultâneas.

Use a verificação de integridade para testar um backup existente. Se precisar de uma cópia imediata, use o backup manual e confira o resultado. Não apague o último backup válido para liberar espaço antes de manter outra cópia segura.

### Importação falhou ou trouxe contagens inesperadas

Guarde os logs da importação mágica e da etapa MARC indicada no erro. Compare contagens de entrada, preparação e importação efetiva. Confira modo, códigos de biblioteca e tipo de item, barcodes, registros rejeitados e política para duplicados.

Uma prévia pequena correta não comprova a validade do arquivo inteiro. Use a validação completa do mapeamento. Se a execução já chegou à gravação, verifique quais etapas terminaram antes de tentar de novo, para não duplicar registros ou leitores.

### Restauração terminou com erro

Leia a etapa que falhou e os logs de restore. Uma falha de indexação depois da importação não é igual a uma falha antes de substituir a base. O mecanismo pode tentar recuperar o estado anterior em algumas falhas, mas o rollback também pode falhar. Não declare recuperação completa sem conferir banco, buscas e validação.

### IA ou enriquecimento demora

Para IA, confira o estado do Ollama, a escolha salva e a memória carregada. Para enriquecimento, consulte o trabalho, os servidores e os limites de consulta. Não repita tarefas grandes apenas porque a tela não trouxe um resultado imediato. Uma falha de serviço externo exige investigação diferente de falta de RAM local.

### Ícone ou bandeja do Windows não funciona

O repositório fornece um diagnóstico específico. Execute no PowerShell do usuário conectado, **sem abrir como administrador**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Esse script não é apenas uma leitura: ele confere e pode recriar atalhos e reiniciar a bandeja. A saída é gravada como `diagnose-<data>.txt` no diretório `logs` da instalação detectada. Guarde o caminho exibido e os detalhes do erro. Este procedimento é diferente da instalação inicial pelo PowerShell administrativo.

## Manutenção não substitui investigação

**Otimização profunda do banco e limpeza de logs** faz operações de manutenção e reinicia serviços. Não a execute apenas para esconder uma mensagem de erro: ela pode remover histórico de logs que ajudaria na investigação. Preserve os diagnósticos relevantes antes e escolha uma janela de manutenção.

## Informações para pedir ajuda

Informe a versão instalada, Windows/WSL ou distribuição Linux, ação realizada, horário, sintoma e mensagem completa. Diga se OPAC, equipe e busca funcionam e se houve importação, restauração ou atualização imediatamente antes. Acrescente os trechos pertinentes do diagnóstico, depois de conferir a privacidade.

**A confirmar:** a causa de uma falha sem mensagem completa e sem o log da execução. Este manual oferece uma sequência de investigação; não atribui automaticamente todo erro à rede ou à instalação.

## Fontes conferidas

- [Diagnóstico](../../../panel/kei_panel/routines/diagnostics.py), status, validação, Apache e exportação.
- [Visualizador de logs](../../../panel/kei_panel/screens/logtail.py), botões e atalhos Textual.
- [Busca](../../../panel/kei_panel/routines/search.py), reparo e troca de mecanismo.
- [Instalador](../../../installer), diretórios e nomes de logs, validação, contingência do painel, status e manutenção.
- [Diagnóstico Windows](../../../windows/diagnose.ps1) e [caminhos Windows](../../../windows/KohaEasy.Core.psm1).
