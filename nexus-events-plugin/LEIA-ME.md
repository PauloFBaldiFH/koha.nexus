# Nexus Eventos para Tainacan 0.1.1

Extensão gratuita para WordPress, construída para funcionar ao lado do Tainacan. Usa o Events Manager gratuito como motor de eventos e reservas, preservando seu código e seu caminho normal de atualização.

## Instalação

1. Faça backup do WordPress e teste primeiro em uma cópia do site.
2. Instale o Events Manager gratuito (7.4.13 ou mais novo) a partir do diretório oficial do WordPress, em Plugins, Adicionar novo. No Koha.Nexus, `config.sh --task tainacan-events enable confirm` faz isso: baixa a versão fixada, confere cada arquivo contra as somas publicadas pelo wordpress.org e instala. Um Events Manager já instalado é preservado.
3. Instale o pacote de produção (pasta `nexus-eventos/`, gerada por `tools/nexus-eventos-package.py`) e ative Nexus Eventos para Tainacan em Plugins. Não copie a pasta `nexus-events-plugin` do repositório: ela tem `development/` e `bundled/`, que não vão para produção.
4. Acesse a área de eventos do Events Manager para concluir sua configuração de reservas, permissões, política de privacidade e e-mails.
5. O menu Nexus Eventos reúne os atalhos, a identificação da instituição e a presença. Tainacan ativo habilita os vínculos com coleções.

O WordPress mantém dois plugins separados: Events Manager e Nexus Eventos. Isso é intencional: correções e atualizações da base não dependem de um fork. A pasta `bundled/events-manager/` do repositório guarda os arquivos usados na análise e não faz parte do pacote de produção.

Tainacan não é instalado automaticamente. Não há arquivos compactados nesta pasta do repositório. Não é necessário instalar Event Tickets ou The Events Calendar. Esta extensão não exige edições Pro para suas próprias funções.

Requisitos: WordPress 6.5 ou superior; PHP 8.1 ou superior com mbstring e random_bytes; banco MySQL/MariaDB com GET_LOCK. Events Manager 7.4.13 ou superior. A combinação efetivamente testada está no relatório de validação, não em uma promessa de compatibilidade com toda versão futura.

## O que está disponível

Da base Events Manager gratuita, pelos mecanismos originais: criação e edição de eventos, locais, categorias, recorrência, calendário, reservas, limites de vagas, aprovação, participantes e mensagens. Esses recursos continuam sendo configurados no Events Manager. Sua disponibilidade e comportamento seguem a versão instalada; não foram reimplementados pelo Nexus.

Na extensão Nexus:

- Agenda em cartões, pesquisa, categoria, período e paginação.
- Links para inscrição e exportação iCal da base.
- Vínculo de evento com coleções públicas do Tainacan. Nenhum item ou arquivo do acervo é duplicado.
- Área do participante autenticado, com acesso aos passes das suas reservas individuais aprovadas.
- Link do passe acrescentado à mensagem nativa de confirmação para reservas elegíveis.
- Passe imprimível com QR gerado localmente, sem serviço externo de imagens.
- Registro de presença pela equipe autorizada, com operação explícita e proteção contra repetição.
- Comprovante de participação após o evento, com código aleatório verificável, carga horária declarada e cópia dos dados da emissão.
- Revogação e desfazimento de presença. Desfazer presença revoga o comprovante correspondente.
- Impressão e salvamento em PDF pelo navegador, sem biblioteca de PDF no servidor.
- Exportação CSV de participantes e presença por evento, com proteção contra fórmulas de planilha.
- Integração à exportação e ao apagamento de dados pessoais do WordPress para os dados próprios da extensão, incluindo convidados.
- Preservação dos dados ao desativar ou remover o plugin, por padrão.

## Páginas públicas

Crie páginas no WordPress e insira um bloco Shortcode com um destes textos:

`[nexus_eventos]`

Agenda pública. Aceita `limite`, de 1 a 48, e `colecao`, com o ID de uma coleção pública:

`[nexus_eventos limite="12" colecao="123"]`

`[nexus_minhas_inscricoes]`

Área de inscrições do usuário autenticado. Convidados sem conta usam o link recebido na confirmação. Cancelamentos e alterações continuam na área de reservas do Events Manager.

`[nexus_validar_comprovante]`

Formulário de verificação pública. O QR do comprovante também leva diretamente à consulta.

Use uma agenda por página para manter os filtros simples. A agenda acompanha o significado de período do Events Manager, inclusive eventos do dia atual.

## Integração ao acervo

No editor de um evento, a caixa “Nexus: acervo e participação” permite selecionar coleções públicas e habilitar o comprovante. O seletor lista até 200 coleções. Vínculos que deixarem de ser públicos não são apresentados aos visitantes.

O bloco de coleções é acrescentado ao conteúdo do evento. O bloco de eventos da coleção é acrescentado quando o tema renderiza a coleção pelo filtro `the_content`. Temas ou telas do Tainacan que usam renderização própria podem não passar por esse filtro; nesse caso, use o shortcode com `colecao` numa página pública e ligue-a à coleção pelo menu do site. Não alteramos templates internos do Tainacan.

A integração atual é no nível de coleção. Não cria automaticamente itens a partir de inscrições, fotos ou certificados e não importa participantes para o acervo.

## Presença, passes e comprovantes

1. Crie o evento e um tipo de inscrição gratuita na base. Para passe nominal, configure uma vaga por reserva.
2. No evento, habilite o comprovante e preencha a carga horária, se aplicável.
3. Uma reserva aprovada de uma pessoa recebe acesso ao passe. O link contém uma credencial de acesso: não o publique nem compartilhe capturas do QR.
4. A equipe abre o passe ou a lista do evento em Nexus Eventos. Abrir ou escanear o QR não altera nada. Para confirmar presença, é necessário login autorizado e envio do formulário.
5. A presença pode ser registrada a partir de 24 horas antes do início, e depois dele. Isso é registro administrativo, não prova de identidade ou de permanência durante toda a atividade.
6. Após o horário de encerramento, o participante ou a equipe pode solicitar a emissão. O nome é o cadastro da reserva; cabe à organização verificá-lo antes de emitir.
7. Dados de comprovantes emitidos não mudam quando título, carga horária ou identificação da instituição mudam. Uma emissão revogada não é reemitida automaticamente.

Reservas de grupo e reservas de horários fracionados (timeslots) continuam possíveis na base, mas não são elegíveis às funções nominais Nexus desta versão. Não presumimos que o nome do responsável identifique todos os presentes.

O comprovante é HTML imprimível. “Salvar como PDF” depende da opção de impressão do navegador. O código permite verificar o estado atual do registro, mas não equivale a assinatura ICP-Brasil, identidade verificada ou certificação acadêmica. A consulta pública não exibe nome nem e-mail do participante.

Não há lista de espera, campos adicionais de inscrição, bilheteria paga, assinatura digital, leitura de câmera embutida, emissão em lote ou automações de mensagens implementadas pela extensão. Não são desbloqueadas funções comerciais. Inscrição online e QR exigem conexão para validar a situação atual.

## Segurança e privacidade

Acesso ao passe exige usuário proprietário, equipe autorizada do evento ou token derivado do UUID aleatório da reserva e do segredo do site. Trocar os salts do WordPress invalida os links antigos dos passes. Guarde a configuração necessária no backup protegido e tenha procedimento para reenviar confirmações.

Presença, desfazimento e emissão exigem POST e nonce. A leitura de QR sozinha não autoriza presença. Emissões e presenças são idempotentes e as mutações Nexus são serializadas por reserva no banco. Isso não muda os mecanismos de concorrência da base Events Manager.

Os documentos e a área de inscrições recebem cabeçalhos contra cache. Configure qualquer CDN ou cache anterior ao WordPress para excluir as URLs com `nxev_pass`, `nxev_verify` e a página de inscrições. Documentos usam scripts locais e não carregam o tema nem ferramentas externas de análise.

Os links de passe podem aparecer nos logs de acesso do servidor. Restrinja esses logs, aplique retenção adequada e remova os parâmetros sensíveis de diagnósticos compartilhados.

Coleções privadas, protegidas por senha ou não publicadas são recusadas nos vínculos públicos. A extensão não concede acesso aos metadados ou arquivos privados do Tainacan.

Os dados de inscrição originais são administrados pelo Events Manager. A ferramenta de privacidade Nexus remove presença, anonimiza e revoga seus comprovantes e remove o histórico vinculado. Ela não substitui as ferramentas de privacidade da base. Ao anonimizar, o código revogado pode permanecer como registro sem o nome/e-mail. A instituição deve definir sua política de retenção.

No momento, não suportamos ativação em rede nem o modo de tabelas globais do Events Manager em WordPress multisite. Use ativação individual com eventos locais.

## Backup, atualização e remoção

Inclua o banco inteiro do WordPress, wp-content, os dois plugins e a configuração protegida do site no procedimento de backup. As tabelas próprias têm os sufixos `nxev_attendance`, `nxev_certificates` e `nxev_log`; os vínculos com coleções ficam nos metadados dos eventos.

Atualize Events Manager pelo procedimento normal de plugins, após backup e teste em cópia. Não reinstale uma versão antiga da base para tentar fazer downgrade. A extensão não muda a política de atualização automática do servidor.

Desativar ou excluir Nexus Eventos preserva seus registros. Para apagamento definitivo, o administrador pode definir `NXEV_DELETE_DATA` como `true` na configuração do WordPress e então excluir o plugin. Isso remove somente as tabelas/opções/metadados Nexus, não eventos, reservas ou acervos. A remoção destrutiva não é executada em multisite.

## Licença e estágio

Nexus Eventos: GPL-3.0-or-later. A base Events Manager é um plugin separado, sob sua própria licença GPL-2.0-or-later, e não vai no pacote de produção. A biblioteca QR local é MIT. Consulte THIRD-PARTY-NOTICES.md e os textos das licenças.

Esta é a versão 0.1.1 para piloto e revisão. VALIDACAO.md descreve a validação da 0.1.0. A 0.1.1 é testada também no conjunto de versões do instalador do Koha.Nexus (tests/tainacan_events_system.bats na raiz do repositório). Um servidor de produção com Koha real ainda não foi testado.
