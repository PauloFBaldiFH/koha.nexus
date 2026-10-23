# 8. Agendamentos, VPN, mensagens e administração

[Índice do manual](README.md) · [Anterior: IA local](07-ia-local.md)

As ações deste capítulo afetam o funcionamento do servidor ou a comunicação com leitores. Confira o estado atual antes de alterar configurações e mantenha um backup recente. Configurar uma função não demonstra que ela funciona através da rede da biblioteca: faça a conferência correspondente depois.

## Agendamentos e cron

Abra **Tarefas agendadas e automações**, pela barra lateral ou pela tecla **s**. Cada linha tem um controle de ativação, frequência e horário. Dependendo da frequência, há dia da semana, dia do mês ou expressão personalizada.

1. Use **Recarregar** para ler a configuração atual.
2. Ative somente as tarefas necessárias e ajuste o horário no formato `HH:MM`.
3. Use **Prévia** para ler o arquivo que será gravado.
4. Use **Salvar** e confirme o resumo das mudanças.
5. Recarregue e confira os horários salvos.

O arquivo gerenciado é `/etc/cron.d/koha_tasks`. O fluxo guarda uma cópia anterior como `koha_tasks.bak`. Uma tarefa desligada fica comentada, preservando seu horário para reativação. Linhas próprias são mantidas pelo leitor.

**Padrões** coloca os valores padrão na tela; é preciso salvar para mantê-los. Entre os padrões estão backup SQL noturno às 23:00 e exportação MARC aos domingos às 03:00. Confira o fuso e o agendamento efetivo, pois a biblioteca pode tê-los alterado.

O servidor precisa estar ligado e o ambiente Linux em execução no horário agendado. No Windows, fechar ou desligar o ambiente pode impedir a execução noturna; não presuma que o agendamento ligará o computador. Os avisos próprios do Koha têm seu mecanismo de envio, distinto das tarefas adicionais gerenciadas nesta tela.

## VPN WireGuard

Abra **Central de segurança e acesso** e o cartão **WireGuard VPN**, ou use a tecla **v**. A tela pede endereço público ou nome do servidor e porta UDP.

1. Informe o endereço pelo qual os dispositivos alcançarão o servidor e confira a porta.
2. Use **Configurar a VPN** e leia as alterações de rede na confirmação. Em uma rede com roteador, a porta UDP precisa ser encaminhada ao servidor.
3. Dê um nome a cada dispositivo e use **Adicionar dispositivo**.
4. Selecione o dispositivo e abra **QR code & profile** para configurar seu cliente WireGuard.
5. Confira a conexão e o acesso à interface da equipe. O painel mostra a atividade e o tráfego dos dispositivos.

Cada dispositivo tem seu próprio perfil. Não publique o perfil nem seu QR code. **Revogar** impede que esse perfil volte a conectar; o dispositivo precisará de um novo perfil para retornar. **Desligar** interrompe a VPN e desconecta os dispositivos, mas mantém os perfis, segundo a confirmação.

O túnel é dividido: a rede `10.66.0.0/24` passa pela VPN, enquanto a internet e o DNS do dispositivo continuam pela conexão própria. A tela informa acesso à equipe em `http://10.66.0.1:8080` quando conectado. Em WSL sem rede espelhada, o código informa que o servidor não é diretamente alcançável e mantém essa VPN desativada.

## Mensagens e interoperabilidade

Abra **Mensagens e interoperabilidade**, pela barra lateral ou pela tecla **m**. As abas atuais são **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2** e **Z39.50**, com traduções conforme o dicionário da instalação.

### E-mail

Ative o envio de e-mail do Koha pela ação da tela e confira o servidor SMTP padrão. Os botões abrem a configuração de SMTP, o endereço da biblioteca, os avisos e recibos e as regras de atraso no próprio Koha.

Ativar o envio não preenche todas as regras de circulação e destinatários. Revise o servidor, as preferências dos leitores e os modelos de aviso. Siga as instruções do provedor para autenticação, sem registrar informações privadas em relatórios públicos.

### WhatsApp, Telegram e SMS

Use **Configurar WhatsApp e Telegram** para acessar a configuração do serviço, a definição de país e código de área, o teste de mensagem, a ativação dos avisos e a conferência dos telefones. O WhatsApp depende de um gateway; o painel não transforma a instalação do Koha em um serviço independente desse gateway. O Telegram depende de sua configuração de bot e destinatários.

Envie um teste para um destinatário autorizado antes de ativar avisos de produção. Confira o formato dos telefones e os modelos de aviso do Koha. Não execute uma correção em lote de números sem ler a prévia.

A aba **SMS** encaminha à preferência `SMSSendDriver` e às preferências de mensagens dos leitores. Ela depende de um driver e serviço compatíveis; não há garantia de envio só por preencher o nome do driver.

### Alertas adicionais

A aba **Alerts** permite lembretes antes do vencimento, alertas de atraso, intervalo de repetição e resumo diário para a biblioteca. Escolha os canais e salve. **Dry run (sends nothing)** mostra a simulação sem enviar mensagens.

Quando há um alerta ativado, o fluxo habilita a tarefa correspondente nos agendamentos. Confira também o cron. Os avisos do próprio Koha podem produzir mensagens semelhantes: escolha uma política que evite dois lembretes para o mesmo evento.

### SIP2 e Z39.50

A aba **SIP2** configura porta, rede, biblioteca e permissões do equipamento de autoatendimento. Confira a opção de remover exemplos e use o botão para criar o cadastro necessário no Koha. A configuração do servidor e o cadastro do equipamento precisam corresponder, conforme a orientação da tela. Não exponha a porta a todas as redes apenas para um teste local.

A aba **Z39.50** leva à tela de servidores descrita no capítulo 5. Consultar fontes externas e disponibilizar seu catálogo para consulta são operações diferentes.

## Segurança e acesso remoto

A Central de segurança e acesso também reúne Cloudflare Tunnel, regras UFW, restrição da porta 8080 da equipe, HTTPS e Fail2ban. Para cada ação, leia o estado e o resumo antes de confirmar. O túnel, a VPN e o acesso direto por porta têm configurações e alcances diferentes.

A restrição da porta 8080 permite limitar o acesso direto à equipe, mantendo a estratégia de acesso remoto escolhida. Não altere as regras de um servidor remoto sem saber por qual caminho você continuará a administrá-lo.

**A confirmar:** requisitos de domínio, roteador, provedor de internet e política institucional para publicar o serviço. Não podem ser determinados apenas pelo código. Por isso este manual não fornece uma receita única de publicação para todas as redes.

## Parâmetros, idiomas e atualizações

Em **Configurações e parâmetros do Koha**, o dimensionamento ajusta memória e processos, a criação de super bibliotecário fornece uma conta com permissões amplas e a configuração de relógio permite escolher o fuso. Reserve as permissões administrativas para quem realmente precisa delas.

Em **Idiomas do Koha**, há ações diferentes para baixar e ativar, somente baixar, ativar um idioma já instalado e listar os idiomas. Baixar um pacote não significa necessariamente torná-lo o idioma ativo. Confira o resultado no painel, na equipe e no OPAC.

Na **Central de atualizações**, diferencie atualizar os pacotes do sistema e os esquemas do Koha de atualizar o próprio painel pelo GitHub. Faça backup e reserve uma janela de manutenção. A atualização do painel pode encerrar sua sessão para que a próxima abertura carregue a nova versão. Se a migração de esquema falhar, não presuma que um simples reinício tenha resolvido: consulte o erro e o diagnóstico.

## Ferramentas de administração bibliotecária

**Ferramentas da biblioteca** inclui sincronização e vinculação de autoridades, busca de autores duplicados, relatórios SQL, mudança de categoria de leitores, verificação de qualidade e rotinas de privacidade.

- Na mudança de categoria, selecione origem e destino diferentes, a regra de seleção e a biblioteca. Leia a simulação antes de confirmar a alteração com backup.
- A verificação de qualidade procura inconsistências; sua execução é de leitura e não corrige automaticamente todos os problemas apontados.
- A anonimização do histórico remove vínculos de registros antigos com os leitores conforme o fluxo do Koha. Não equivale a apagar todo o histórico bibliográfico.
- A exclusão de leitores antigos exige filtros, simulação e confirmação pela quantidade indicada. É uma ação destrutiva. Confira a política de retenção antes de aceitá-la.
- A busca de autores duplicados apresenta possíveis variantes para revisão; semelhança de nome não prova que duas autoridades representem a mesma pessoa.

As ferramentas de catalogação ocultas no menu atual não são apresentadas aqui como cartões disponíveis. Para logs e investigação de falhas, siga o próximo capítulo.

## Fontes conferidas

- [Menus](../../../panel/kei_panel/menus.py), ações visíveis e ocultas.
- [Agendamentos](../../../panel/kei_panel/views/crons.py) e [leitor cron](../../../panel/kei_panel/cron.py), prévia, padrões e gravação.
- [VPN](../../../panel/kei_panel/views/vpn.py), configuração, dispositivos, revogação e limitação no WSL.
- [Mensagens](../../../panel/kei_panel/views/hub.py), abas, alertas, SMTP, SIP2 e links para o Koha.
- [Parâmetros](../../../panel/kei_panel/routines/settings.py), [segurança](../../../panel/kei_panel/routines/security.py) e [ações gerais](../../../panel/kei_panel/routines/tools.py).
- [Instalador](../../../installer), atualização, mensagens, categorias, qualidade, privacidade e autoridades.
